# backend/app/services/email_service.py
import os
import smtplib
import ssl
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_bool(name: str, default: str = "false") -> bool:
    val = _env(name, default).lower()
    return val in ("1", "true", "yes", "y", "on")


def can_send_email() -> bool:
    """
    Returns True only if SMTP is configured well enough to attempt sending.
    """
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "FROM_EMAIL"]
    return all(_env(k) for k in required)


def send_activation_email(to_email: str, to_name: str, activation_link: str) -> None:
    """
    Sends an activation email using SMTP.

    IMPORTANT:
    - This function raises exceptions if SMTP is not configured or sending fails.
    - Caller (signup endpoint) should NOT fall back to returning activation_link.
    """
    if not can_send_email():
        raise RuntimeError("SMTP not configured (missing SMTP_* or FROM_EMAIL env vars)")

    smtp_host = _env("SMTP_HOST")
    smtp_port = int(_env("SMTP_PORT", "587"))
    smtp_user = _env("SMTP_USER")
    smtp_pass = _env("SMTP_PASS")
    from_email = _env("FROM_EMAIL")
    from_name = _env("FROM_NAME", "AfricaESG.AI")
    timeout = float(_env("SMTP_TIMEOUT", "20"))

    # Most providers:
    # - Port 587 => STARTTLS (default)
    # - Port 465 => implicit TLS/SSL
    use_ssl = _env_bool("SMTP_SSL", "true" if smtp_port == 465 else "false")

    subject = "Activate your AfricaESG.AI account"

    safe_name = (to_name or "").strip() or "there"

    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #111827;">
      <h2 style="margin: 0 0 12px 0;">Hi {safe_name},</h2>
      <p style="margin: 0 0 12px 0;">Thanks for signing up for AfricaESG.AI.</p>
      <p style="margin: 0 0 12px 0;">Please activate your account by clicking the button below:</p>
      <p style="margin: 16px 0;">
        <a href="{activation_link}"
           style="display: inline-block; background: #10B981; color: white; text-decoration: none;
                  padding: 10px 16px; border-radius: 8px; font-weight: 600;">
          Activate my account
        </a>
      </p>
      <p style="margin: 0 0 8px 0;">
        Or copy and paste this link into your browser:
      </p>
      <p style="word-break: break-all; margin: 0 0 12px 0;">
        <a href="{activation_link}">{activation_link}</a>
      </p>
      <p style="margin: 0 0 12px 0;">If you didn’t request this, you can ignore this email.</p>
      <p style="margin: 0;">
        <small>This link expires in 24 hours.</small>
      </p>
    </div>
    """

    text = (
        f"Hi {safe_name},\n\n"
        "Thanks for signing up for AfricaESG.AI.\n"
        "Please activate your account using the link below:\n\n"
        f"{activation_link}\n\n"
        "If you didn’t request this, you can ignore this email.\n"
        "This link expires in 24 hours.\n"
    )

    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    context = ssl.create_default_context()

    # Helpful pre-flight DNS error will raise quickly instead of hanging:
    try:
        socket.getaddrinfo(smtp_host, smtp_port)
    except Exception as e:
        raise RuntimeError(f"SMTP host resolution failed for {smtp_host}:{smtp_port} ({e})") from e

    if use_ssl:
        # Implicit TLS (usually port 465)
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout, context=context) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())
    else:
        # STARTTLS (usually port 587)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())
