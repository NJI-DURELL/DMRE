"""
dev_smtp.py — Tiny RFC-5321 SMTP server for local development.

Listens on 127.0.0.1:1025 and prints every received email to stdout. This is
NOT a mock or stub — it speaks real SMTP, so the production email_service.py
(which uses stdlib smtplib) talks to it exactly the way it talks to Resend,
Mailgun, SendGrid, or Gmail. Use it locally so you can complete the OTP
flow end-to-end without an external provider.

Usage:
    python dev_smtp.py                # 127.0.0.1:1025
    python dev_smtp.py --port 2525    # custom port
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from email import message_from_bytes


HOST_DEFAULT = "127.0.0.1"
PORT_DEFAULT = 1025


def _print_email(raw: bytes) -> None:
    msg = message_from_bytes(raw)
    print("\n" + "=" * 72)
    print(f"From:    {msg.get('From')}")
    print(f"To:      {msg.get('To')}")
    print(f"Subject: {msg.get('Subject')}")
    print(f"Date:    {msg.get('Date')}")
    print("-" * 72)
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                print(payload.decode("utf-8", errors="replace"))
                break
    else:
        payload = msg.get_payload(decode=True) or b""
        print(payload.decode("utf-8", errors="replace"))
    print("=" * 72 + "\n", flush=True)

    # Convenience: highlight 6-digit OTP codes so they're easy to grep / copy.
    text = (
        msg.get_payload(decode=True) or b""
        if not msg.is_multipart()
        else b"".join(
            (p.get_payload(decode=True) or b"") for p in msg.walk()
            if p.get_content_type() == "text/plain"
        )
    )
    m = re.search(rb"\b(\d{6})\b", text)
    if m:
        print(f">>> OTP code: {m.group(1).decode()} <<<\n", flush=True)


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    peer = writer.get_extra_info("peername")
    writer.write(b"220 dmre-dev-smtp ESMTP\r\n")
    await writer.drain()

    in_data = False
    body_lines: list[bytes] = []

    while True:
        line = await reader.readline()
        if not line:
            break

        if in_data:
            if line == b".\r\n" or line == b".\n":
                _print_email(b"".join(body_lines))
                writer.write(b"250 OK message accepted\r\n")
                await writer.drain()
                in_data = False
                body_lines = []
                continue
            # RFC 5321 §4.5.2: dot-stuffing — leading dot in a line is doubled.
            if line.startswith(b"..") :
                line = line[1:]
            body_lines.append(line)
            continue

        cmd = line.strip()
        upper = cmd.upper()

        if upper.startswith(b"HELO") or upper.startswith(b"EHLO"):
            writer.write(b"250-dmre-dev-smtp\r\n250-AUTH PLAIN LOGIN\r\n250 8BITMIME\r\n")
        elif upper.startswith(b"AUTH"):
            # Accept any credentials in dev. Real providers enforce.
            writer.write(b"235 auth ok\r\n")
        elif upper.startswith(b"MAIL FROM") or upper.startswith(b"RCPT TO"):
            writer.write(b"250 OK\r\n")
        elif upper == b"DATA":
            writer.write(b"354 end with <CR><LF>.<CR><LF>\r\n")
            in_data = True
        elif upper == b"RSET":
            body_lines = []
            writer.write(b"250 OK\r\n")
        elif upper == b"NOOP":
            writer.write(b"250 OK\r\n")
        elif upper == b"QUIT":
            writer.write(b"221 bye\r\n")
            await writer.drain()
            break
        else:
            writer.write(b"502 unrecognized\r\n")
        await writer.drain()

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


async def _main(host: str, port: int) -> None:
    server = await asyncio.start_server(_handle, host, port)
    print(f"[dev_smtp] listening on {host}:{port}  (set SMTP_HOST={host} SMTP_PORT={port} SMTP_TLS=none)")
    print(f"[dev_smtp] every email is printed below; OTP codes are highlighted.\n", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=HOST_DEFAULT)
    ap.add_argument("--port", type=int, default=PORT_DEFAULT)
    args = ap.parse_args()
    try:
        asyncio.run(_main(args.host, args.port))
    except KeyboardInterrupt:
        sys.exit(0)
