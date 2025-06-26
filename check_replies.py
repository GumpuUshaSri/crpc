import imaplib
import email
from email.header import decode_header
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import re
from datetime import datetime

# Load environment variables
load_dotenv()
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client["social_monitoring"]
collection = db["flagged_messages"]

# Connect to Gmail via IMAP
imap = imaplib.IMAP4_SSL("imap.gmail.com")
imap.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
imap.select("inbox")

# Search for unseen messages
status, messages = imap.search(None, 'UNSEEN')
if status != "OK":
    print("❌ Could not search inbox.")
    exit()

found_any = False

for num in messages[0].split():
    status, msg_data = imap.fetch(num, "(RFC822)")
    if status != "OK":
        continue

    for part in msg_data:
        if isinstance(part, tuple):
            msg = email.message_from_bytes(part[1])
            subject, encoding = decode_header(msg["Subject"])[0]
            subject = subject.decode(encoding or "utf-8") if isinstance(subject, bytes) else subject
            sender = email.utils.parseaddr(msg.get("From"))[1]

            print(f"📨 Checking reply from: {sender} | Subject: {subject}")

            # Match user by email
            flagged_user = collection.find_one({"email": sender, "responded": {"$ne": True}})
            if not flagged_user:
                print("🚫 No matching flagged user found for this sender.")
                continue

            # Extract body
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = msg.get_payload(decode=True).decode()

            # Update MongoDB
            collection.update_one(
                {"_id": flagged_user["_id"]},
                {"$set": {
                    "status": "responded",
                    "responded_at": datetime.utcnow(),
                    "reply_content": body.strip()[:1000],
                    "responded": True
                }}
            )

            print(f"✅ Reply recorded from {sender}")
            found_any = True

if not found_any:
    print("📭 No replies matched any flagged users.")

imap.logout()