from pymongo import MongoClient
from email.message import EmailMessage
import smtplib
from dotenv import load_dotenv
import os
from datetime import datetime

# Load credentials from .env
load_dotenv()
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# ✅ Ensure credentials loaded
if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
    raise Exception("❌ EMAIL_ADDRESS or EMAIL_PASSWORD not found in .env")

# MongoDB setup
client = MongoClient("mongodb://localhost:27017")
db = client["social_monitoring"]
collection = db["flagged_messages"]

# Fetch users with pending warnings
pending = collection.find({"status": "warning_pending"})

count = 0
for user in pending:
    email = user.get("email")
    username = user.get("username", "User")
    flagged_text = user.get("text", "")

    if not email:
        print(f"⚠ Skipping user {username} — no email.")
        continue

    # Prepare the email
    subject = "⚠ Suspicious Activity Detected"
    body = f"""Dear {username},

We've detected suspicious content linked to your recent activity:
---
"{flagged_text}"
---

This violates our usage policies. Please refrain from such content.
If this was a mistake, please reply within 48 hours.

Regards,
Cyber Monitoring Unit
"""

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = email
        msg.set_content(body)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        # Mark warning sent in DB
        collection.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "status": "warning_sent",
                "warning_sent_at": datetime.utcnow()
            }}
        )

        print(f"✅ Warning email sent to {email}")
        count += 1

    except Exception as e:
        print(f"❌ Failed to send to {email}: {e}")

print(f"\n📤 Total warnings sent: {count}")