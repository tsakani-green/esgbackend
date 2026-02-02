# backend/app/services/email_service.py
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def can_send_email() -> bool:
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "FROM_EMAIL"]
    return all(_env(k) for k in required)


def send_activation_email(to_email: str, to_name: str, activation_link: str) -> None:
    """
    Sends an activation email using SMTP.
    If SMTP is not configured, raise RuntimeError so caller can fallback to returning activation_link.
    """
    if not can_send_email():
        raise RuntimeError("SMTP not configured")

    smtp_host = _env("SMTP_HOST")
    smtp_port = int(_env("SMTP_PORT", "587"))
    smtp_user = _env("SMTP_USER")
    smtp_pass = _env("SMTP_PASS")
    from_email = _env("FROM_EMAIL")

    subject = "Activate your AfricaESG.AI account"

    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.5;">
      <h2>Hi {to_name or "there"},</h2>
      <p>Thanks for signing up for AfricaESG.AI.</p>
      <p>Please activate your account by clicking the link below:</p>
      <p><a href="{activation_link}">Activate my account</a></p>
      <p>If you didn’t request this, you can ignore this email.</p>
      <p><small>This link expires in 24 hours.</small></p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.as_string())
