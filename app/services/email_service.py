# backend/app/services/email_service.py

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    pass


def _smtp_settings():
    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int((os.getenv("SMTP_PORT") or "587").strip())
    user = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASS") or "").strip()
    from_email = (os.getenv("FROM_EMAIL") or user).strip()

    if not host or not user or not password or not from_email:
        raise EmailSendError("Missing SMTP_HOST/SMTP_USER/SMTP_PASS/FROM_EMAIL environment variables")

    return host, port, user, password, from_email


def send_email(to_email: str, subject: str, html_body: str, text_body: str = ""):
    """
    Generic email sender (sync).
    Works with Gmail SMTP + App Password.
    """
    host, port, user, password, from_email = _smtp_settings()

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        server = smtplib.SMTP(host, port, timeout=20)
        server.ehlo()
        server.starttls()
        server.login(user, password)
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        logger.info(f"Email sent to {to_email} subject='{subject}'")
    except Exception as e:
        logger.exception(f"Failed to send email to {to_email}: {e}")
        raise EmailSendError(str(e))


def send_activation_email(to_email: str, full_name: str, activation_link: str):
    subject = "Activate your GreenBDG account"
    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.5;">
      <h2>Hello {full_name or ""},</h2>
      <p>Thanks for signing up. Please activate your account by clicking the button below:</p>
      <p>
        <a href="{activation_link}"
           style="display:inline-block;padding:12px 18px;background:#2e7d32;color:white;text-decoration:none;border-radius:6px;">
           Activate Account
        </a>
      </p>
      <p>If the button doesn’t work, copy and paste this link:</p>
      <p>{activation_link}</p>
      <p>— GreenBDG</p>
    </div>
    """
    text = f"Activate your account: {activation_link}"
    send_email(to_email, subject, html, text)
