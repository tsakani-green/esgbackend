import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class EmailSendError(Exception):
    pass

def _get_smtp_config():
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "").strip()
    from_email = (os.getenv("FROM_EMAIL", "") or user).strip()

    if not host or not user or not password or not from_email:
        raise EmailSendError("Missing SMTP_HOST/SMTP_USER/SMTP_PASS/FROM_EMAIL configuration")

    return host, port, user, password, from_email

def send_email(to_email: str, subject: str, html_body: str):
    host, port, user, password, from_email = _get_smtp_config()

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(user, password)
            server.sendmail(from_email, [to_email], msg.as_string())

        logger.info(f"Email sent to {to_email} subject={subject}")

    except Exception as e:
        logger.exception(f"Failed sending email to {to_email}: {e}")
        raise EmailSendError(str(e))

def send_activation_email(to_email: str, full_name: str, activation_link: str):
    subject = "Activate your GreenBDG account"
    html = f"""
    <div style="font-family:Arial,sans-serif; line-height:1.5">
      <h2>Hi {full_name},</h2>
      <p>Welcome to GreenBDG. Please activate your account using the link below:</p>
      <p><a href="{activation_link}" target="_blank">{activation_link}</a></p>
      <p>If you did not request this, you can ignore this email.</p>
      <br/>
      <p>— GreenBDG Team</p>
    </div>
    """
    send_email(to_email, subject, html)
