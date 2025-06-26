from pymongo import MongoClient
from email.message import EmailMessage
import smtplib
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

# Load credentials
load_dotenv()
EMAIL = os.getenv("EMAIL_ADDRESS")
PASSWORD = os.getenv("EMAIL_PASSWORD")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["social_monitoring"]
collection = db["flagged_messages"]

# Time check: 48 hours ago
now = datetime.utcnow()
threshold = now - timedelta(hours=48)

# Fetch users who were warned 48+ hours ago and haven't replied
pending = collection.find({
    "status": "warning_sent",
    "warning_sent_at": {"$lte": threshold},
    "responded": {"$ne": True}
})

count = 0
for user in pending:
    email = user.get("email")
    username = user.get("username", "User")
    flagged_text = user.get("text", "")

    if not email:
        print(f"⚠ Skipping user {username} — no email.")
        continue

    subject = "⏰ Final Warning: Suspicious Activity"
    body = f"""Dear {username},

You were previously notified about suspicious content:
---
"{flagged_text}"
---

This is a final warning. If you do not respond within 24 hours, legal action under Section 91 CrPC may be initiated.

Regards,  
Cyber Monitoring Unit
"""

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = EMAIL
        msg["To"] = email
        msg.set_content(body)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL, PASSWORD)
            smtp.send_message(msg)

        # Update DB
        collection.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "status": "followup_sent",
                "followup_sent_at": datetime.utcnow()
            }}
        )

        print(f"📨 Follow-up sent to {email}")
        count += 1

    except Exception as e:
        print(f"❌ Failed to send follow-up to {email}: {e}")

print(f"\n📤 Total follow-ups sent: {count}")