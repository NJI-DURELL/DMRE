# =============================================================================
# backend/app/services/email_service.py
#
# Real SMTP email delivery — used for OTP verification and email-export
# features. There is no "console" or "mock" fallback: if SMTP is misconfigured
# or unreachable the calling endpoint returns a clean 503 and the client
# tells the user to try again later. Production deploys MUST set:
#
#   SMTP_HOST   smtp.resend.com  / smtp-relay.gmail.com / smtp.mailgun.org / ...
#   SMTP_PORT   587 (STARTTLS) or 465 (SSL)
#   SMTP_USER   provider-specific username (often the API key for Resend)
#   SMTP_PASS   provider-specific password / API secret
#   SMTP_TLS    starttls | ssl | none
#   SMTP_FROM   "DMRE <verified@yourdomain.com>"
#
# For local development the recommended setup is a real SMTP server too
# (aiosmtpd or maildev), not a stubbed transport.
# =============================================================================

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from app.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when the SMTP server is misconfigured or refuses the message.

    Routes catch this and translate it into a 503 so callers see a clean
    "could not send email" message rather than a stack trace.
    """


def _ensure_configured() -> None:
    if not settings.smtp_host:
        raise EmailDeliveryError(
            "SMTP_HOST is not configured. Set SMTP_* env vars before signing up "
            "or using email-export features."
        )


SMTP_TIMEOUT_SECONDS = 180


def _open_smtp() -> smtplib.SMTP | smtplib.SMTP_SSL:
    """Connect to the configured SMTP server using the requested TLS mode.

    Timeout is generous (180 s) because some networks add real latency to
    outbound SMTP — Gmail's full handshake (EHLO + STARTTLS + AUTH + EHLO again
    + DATA + QUIT) is more round-trips than a typical HTTPS request, and a
    home/campus connection can stretch each one out.
    """
    mode = (settings.smtp_tls or "starttls").lower()
    if mode == "ssl":
        ctx = ssl.create_default_context()
        client: smtplib.SMTP | smtplib.SMTP_SSL = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port,
            context=ctx, timeout=SMTP_TIMEOUT_SECONDS,
        )
    else:
        client = smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS,
        )
        client.ehlo()
        if mode == "starttls":
            ctx = ssl.create_default_context()
            client.starttls(context=ctx)
            client.ehlo()
    if settings.smtp_user:
        client.login(settings.smtp_user, settings.smtp_pass)
    return client


def send_email(
    *,
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> None:
    """Synchronously send a single email. Raises EmailDeliveryError on any
    failure (connection refused, auth rejected, recipient rejected, etc.)."""
    _ensure_configured()

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        with _open_smtp() as client:
            client.send_message(msg)
    except (smtplib.SMTPException, OSError, TimeoutError) as exc:
        logger.warning("SMTP delivery failed to %s: %s", to, exc)
        raise EmailDeliveryError(f"SMTP delivery failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Templates — kept inline so the service stays a single file.
# ---------------------------------------------------------------------------

def send_otp(*, to: str, username: str, code: str) -> None:
    """Send the 6-digit verification code right after signup."""
    pretty = f"{code[:3]} {code[3:]}"  # "123 456"
    text = (
        f"Hi {username},\n\n"
        f"Your DMRE verification code is: {code}\n\n"
        f"It expires in 15 minutes. If you did not request this, ignore this email.\n\n"
        f"— DMRE\n"
    )
    html = f"""<!DOCTYPE html>
<html><body style="font-family:Inter,system-ui,sans-serif;color:#0f172a;background:#f8fafc;padding:24px;">
  <table cellpadding="0" cellspacing="0" border="0" align="center"
         style="max-width:480px;background:#fff;border:1px solid #e2e8f0;
                border-radius:14px;overflow:hidden;">
    <tr><td style="background:linear-gradient(135deg,#2563eb,#1e40af);
                   padding:18px 22px;color:#fff;">
      <div style="font-size:14px;font-weight:700;">DMRE</div>
      <div style="font-size:11px;color:#dbeafe;">Digital Memory Reconstruction Engine</div>
    </td></tr>
    <tr><td style="padding:24px 22px;">
      <p style="font-size:14px;margin:0 0 12px;">Hi {username},</p>
      <p style="font-size:14px;margin:0 0 18px;color:#334155;">
        Use this code to verify your email address:
      </p>
      <div style="font-family:'JetBrains Mono',ui-monospace,monospace;
                  font-size:28px;letter-spacing:0.18em;font-weight:700;
                  color:#1e40af;background:#eff6ff;border:1px solid #bfdbfe;
                  border-radius:10px;padding:14px 0;text-align:center;">
        {pretty}
      </div>
      <p style="font-size:12px;color:#64748b;margin:18px 0 0;">
        This code expires in 15 minutes. If you did not sign up for DMRE, you can
        safely ignore this email.
      </p>
    </td></tr>
    <tr><td style="background:#f8fafc;padding:14px 22px;font-size:11px;color:#94a3b8;
                   text-align:center;border-top:1px solid #e2e8f0;">
      DMRE — your private browsing-memory engine.
    </td></tr>
  </table>
</body></html>"""
    send_email(to=to, subject="Your DMRE verification code", text=text, html=html)


def send_search_export(
    *, to: str, username: str, query: str, results: list[dict]
) -> None:
    """Email a snapshot of search results to the user."""
    if not results:
        rows_html = "<p style='color:#64748b;font-size:13px;'>No results.</p>"
        rows_text = "(no results)\n"
    else:
        rows_html = "".join(
            f"""<tr><td style="padding:10px 0;border-top:1px solid #e2e8f0;">
                <a href="{r['url']}" style="color:#1d4ed8;font-weight:600;
                  font-size:14px;text-decoration:none;">{_h(r['title']) or '(untitled)'}</a>
                <div style="font-size:11px;color:#64748b;">{_h(r['url'])}</div>
                <div style="font-size:12px;color:#334155;margin-top:4px;">
                  {_h((r.get('snippet') or '')[:280])}…
                </div></td></tr>"""
            for r in results
        )
        rows_text = "\n\n".join(
            f"{r['title']}\n  {r['url']}\n  {(r.get('snippet') or '')[:280]}…"
            for r in results
        )
    html = f"""<!DOCTYPE html><html><body style="font-family:Inter,system-ui,sans-serif;
        color:#0f172a;background:#f8fafc;padding:24px;">
      <table cellpadding="0" cellspacing="0" border="0" align="center"
             style="max-width:560px;background:#fff;border:1px solid #e2e8f0;
                    border-radius:14px;overflow:hidden;">
        <tr><td style="background:linear-gradient(135deg,#2563eb,#1e40af);
                       padding:18px 22px;color:#fff;">
          <div style="font-size:14px;font-weight:700;">DMRE — search export</div>
          <div style="font-size:12px;color:#dbeafe;">"{_h(query)}"</div>
        </td></tr>
        <tr><td style="padding:18px 22px;">
          <p style="font-size:13px;color:#334155;margin:0 0 8px;">
            Hi {username}, here is the snapshot you requested:
          </p>
          <table style="width:100%;border-collapse:collapse;">{rows_html}</table>
        </td></tr></table></body></html>"""
    text = (
        f"Hi {username},\n\n"
        f"Search results for: {query}\n\n{rows_text}\n\n— DMRE\n"
    )
    send_email(to=to, subject=f"Your DMRE search: {query[:60]}", text=text, html=html)


def send_activity_export(
    *, to: str, username: str, captures: list[dict], queries: list[dict]
) -> None:
    """Email a digest of the user's recent activity (captures + searches)."""
    cap_rows = "".join(
        f"""<tr><td style="padding:8px 0;border-top:1px solid #e2e8f0;">
            <a href="{_h(c['url'])}" style="color:#1d4ed8;font-weight:600;
              font-size:13px;text-decoration:none;">{_h(c['title']) or '(untitled)'}</a>
            <div style="font-size:11px;color:#64748b;">{_h(c['url'])}</div>
            <div style="font-size:11px;color:#94a3b8;">visited {_h(str(c['visited_at'])[:19])}</div>
            </td></tr>"""
        for c in captures
    ) or "<tr><td style='color:#64748b;font-size:12px;'>(no captures yet)</td></tr>"

    q_rows = "".join(
        f"""<tr><td style="padding:6px 0;border-top:1px solid #e2e8f0;font-size:12px;color:#334155;">
            "{_h(q['query_text'])}" <span style="color:#94a3b8;">
            — {q['query_type']} · {q['result_count']} result(s) · {_h(str(q['created_at'])[:16])}</span>
            </td></tr>"""
        for q in queries
    ) or "<tr><td style='color:#64748b;font-size:12px;'>(no searches yet)</td></tr>"

    html = f"""<!DOCTYPE html><html><body style="font-family:Inter,system-ui,sans-serif;
        color:#0f172a;background:#f8fafc;padding:24px;">
      <table cellpadding="0" cellspacing="0" border="0" align="center"
             style="max-width:560px;background:#fff;border:1px solid #e2e8f0;
                    border-radius:14px;overflow:hidden;">
        <tr><td style="background:linear-gradient(135deg,#2563eb,#1e40af);
                       padding:18px 22px;color:#fff;">
          <div style="font-size:14px;font-weight:700;">DMRE — activity export</div>
        </td></tr>
        <tr><td style="padding:18px 22px;">
          <p style="font-size:13px;color:#334155;margin:0 0 12px;">
            Hi {username}, here is your DMRE activity snapshot.
          </p>
          <h3 style="font-size:13px;color:#1e40af;margin:14px 0 4px;">
            Recent captures ({len(captures)})</h3>
          <table style="width:100%;border-collapse:collapse;">{cap_rows}</table>
          <h3 style="font-size:13px;color:#1e40af;margin:18px 0 4px;">
            Recent searches ({len(queries)})</h3>
          <table style="width:100%;border-collapse:collapse;">{q_rows}</table>
        </td></tr></table></body></html>"""
    text = (
        f"Hi {username},\n\nYour DMRE activity snapshot:\n\n"
        f"Recent captures: {len(captures)}\n"
        + "\n".join(f"  - {c['title']} | {c['url']}" for c in captures)
        + f"\n\nRecent searches: {len(queries)}\n"
        + "\n".join(f"  - \"{q['query_text']}\" ({q['result_count']} results)" for q in queries)
        + "\n\n— DMRE\n"
    )
    send_email(to=to, subject="Your DMRE activity export", text=text, html=html)


def _h(s: str | None) -> str:
    """Tiny HTML escape for embedded user content."""
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


__all__ = [
    "EmailDeliveryError",
    "send_email",
    "send_otp",
    "send_search_export",
    "send_activity_export",
]
