import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

EMAIL = os.getenv("EMAIL_ADDRESS")
PASSWORD = os.getenv("EMAIL_PASSWORD")

msg = EmailMessage()
msg["Subject"] = "Test Email"
msg["From"] = EMAIL
msg["To"] = "zenithjjk@gmail.com"
msg.set_content("This is a test email sent from Python via Gmail SMTP.")

try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL, PASSWORD)
        smtp.send_message(msg)
        print("✅ Email sent successfully.")
except Exception as e:
    print("❌ Failed to send email:", e)