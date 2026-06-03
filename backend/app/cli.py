# =============================================================================
# backend/app/cli.py
# Tiny operations CLI. Only one command today (grant-admin); add more here
# rather than scattering management scripts across the repo.
#
# Usage:
#     cd backend
#     .venv\Scripts\python.exe -m app.cli grant-admin you@example.com
#     .venv\Scripts\python.exe -m app.cli revoke-admin you@example.com
#     .venv\Scripts\python.exe -m app.cli list-admins
# =============================================================================

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User


async def _set_admin(email: str, value: bool) -> int:
    email = email.lower().strip()
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            print(f"No user with email {email!r}.", file=sys.stderr)
            return 1
        if user.is_admin == value:
            print(f"{email}: already is_admin={value}; nothing changed.")
            return 0
        user.is_admin = value
        await db.commit()
        print(f"{email}: is_admin -> {value}")
        return 0


async def _list_admins() -> int:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(User).where(User.is_admin == True))).scalars().all()
        if not rows:
            print("No admin users.")
            return 0
        print(f"{len(rows)} admin user(s):")
        for u in rows:
            print(f"  - {u.email}  (id={u.id}, joined={u.created_at:%Y-%m-%d})")
        return 0


async def _verify_email(email: str | None) -> int:
    """Mark an account's email as verified without going through the OTP flow.

    Local-dev convenience for when SMTP is flaky or you're testing the
    extension against an account that hasn't completed the dashboard OTP yet.
    Pass --all to verify every account in the database.
    """
    async with AsyncSessionLocal() as db:
        if email == "--all":
            rows = (await db.execute(select(User).where(User.email_verified == False))).scalars().all()
            if not rows:
                print("All accounts are already verified.")
                return 0
            for u in rows:
                u.email_verified = True
            await db.commit()
            print(f"Verified {len(rows)} account(s):")
            for u in rows:
                print(f"  - {u.email}")
            return 0

        normalized = (email or "").lower().strip()
        if not normalized:
            print("usage: verify-email EMAIL  |  verify-email --all", file=sys.stderr)
            return 2
        user = (await db.execute(select(User).where(User.email == normalized))).scalar_one_or_none()
        if user is None:
            print(f"No user with email {normalized!r}.", file=sys.stderr)
            return 1
        if user.email_verified:
            print(f"{normalized}: already verified; nothing changed.")
            return 0
        user.email_verified = True
        await db.commit()
        print(f"{normalized}: email_verified -> True")
        return 0


def _test_smtp(to: str) -> int:
    """Send a one-off test email to confirm SMTP credentials work."""
    from app.config import settings
    from app.services.email_service import EmailDeliveryError, send_email

    print(f"SMTP_HOST={settings.smtp_host!r}  port={settings.smtp_port}  tls={settings.smtp_tls!r}")
    print(f"SMTP_USER={settings.smtp_user!r}  from={settings.smtp_from!r}")
    print(f"Sending a test email to {to} ...")
    try:
        send_email(
            to=to,
            subject="DMRE SMTP test",
            text=(
                "If you can read this, DMRE's SMTP transport is working.\n\n"
                "Now try signing up at the dashboard — the OTP code will arrive here.\n"
            ),
            html=(
                "<p>If you can read this, DMRE's SMTP transport is working.</p>"
                "<p>Now sign up at the dashboard — the OTP code will arrive here.</p>"
            ),
        )
    except EmailDeliveryError as exc:
        print(f"  FAILED: {exc}")
        return 1
    print("  OK — check the recipient inbox (Gmail's Spam folder if you don't see it).")
    return 0


def _print_usage() -> int:
    print(__doc__ or "")
    print("\nCommands:")
    print("  grant-admin EMAIL")
    print("  revoke-admin EMAIL")
    print("  list-admins")
    print("  verify-email EMAIL       # mark one account's email as verified")
    print("  verify-email --all       # verify every unverified account (dev only)")
    print("  test-smtp EMAIL          # send a one-off test email to confirm SMTP works")
    return 2


def main() -> int:
    args = sys.argv[1:]
    if not args:
        return _print_usage()

    cmd = args[0]
    if cmd == "grant-admin" and len(args) == 2:
        return asyncio.run(_set_admin(args[1], True))
    if cmd == "revoke-admin" and len(args) == 2:
        return asyncio.run(_set_admin(args[1], False))
    if cmd == "list-admins" and len(args) == 1:
        return asyncio.run(_list_admins())
    if cmd == "verify-email" and len(args) == 2:
        return asyncio.run(_verify_email(args[1]))
    if cmd == "test-smtp" and len(args) == 2:
        return _test_smtp(args[1])
    return _print_usage()


if __name__ == "__main__":
    sys.exit(main())
