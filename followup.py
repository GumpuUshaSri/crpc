# followup.py

from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import smtplib
from email.message import EmailMessage

# Load env vars
load_dotenv()
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["crpc_db"]
collection = db["requests"]

# 48 hours ago
cutoff = datetime.utcnow() - timedelta(hours=1)

# Query for sent cases older than 48h and not yet followed up
pending = collection.find({
    "status": "sent",
    "sent_at": {"$lt": cutoff}
})

for case in pending:
    msg = EmailMessage()
    msg["Subject"] = f"⚠ Follow-Up: CrPC 91 Request – Case {case['case_number']}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = case["recipient_email"]
    msg.set_content(f"""
Dear {case['recipient']},

This is a reminder regarding our Section 91 CrPC request sent on {case['sent_at'].strftime('%d-%m-%Y %H:%M')} for case {case['case_number']}.
We are awaiting a response.

Kindly expedite the processing.

Regards,
Investigation Officer
""")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

    # Update MongoDB
    collection.update_one(
        {"_id": case["_id"]},
        {"$set": {
            "status": "followed_up",
            "followed_up_at": datetime.utcnow()
        }}
    )

    print(f"📨 Follow-up sent for case: {case['case_number']}")