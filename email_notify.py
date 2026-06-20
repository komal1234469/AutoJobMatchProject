"""
Email notifications.
Sends an alert when a new job scores above the user's match threshold.

Uses SMTP (works with Gmail, Outlook, etc via an app password) rather than
a paid email service - zero cost, good for a personal project.

IMPORTANT: This module only SENDS the email when called. Actually checking
for new jobs on a recurring schedule requires a scheduler (see scheduler.py)
running continuously - that part must be deployed/hosted somewhere that
stays running 24/7 (e.g. a free Render/Railway worker, or your own machine
left on with cron). It will NOT run just by having this web app open in
a browser tab.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")          # your sending email address
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")  # app password, NOT your real password


def send_match_alert(to_email, job_title, company, score, apply_url, matched_skills):
    if not SMTP_USER or not SMTP_PASSWORD:
        raise RuntimeError(
            "SMTP_USER / SMTP_PASSWORD environment variables are not set. "
            "For Gmail: enable 2FA, then create an App Password at "
            "https://myaccount.google.com/apppasswords and use that here."
        )

    subject = f"🎯 {score}% match: {job_title} at {company}"
    skills_line = ", ".join(matched_skills) if matched_skills else "your profile"

    body = f"""Hi,

A new job just matched {score}% with your profile:

{job_title} at {company}
Matched on: {skills_line}

Apply here: {apply_url}

— JobMatch
"""

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
