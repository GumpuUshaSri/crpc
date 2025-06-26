from fastapi import FastAPI, HTTPException
from jinja2 import Template
from datetime import datetime, timedelta
from weasyprint import HTML
import os, uuid, smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["social_monitoring"]
collection = db["flagged_messages"]

# Email credentials
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# HTML Template
TEMPLATE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Section 91 CrPC Request</title>
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }
    h2 { margin-top: 0; }
  </style>
</head>
<body>
  <p>To:<br><strong>{{ recipient }}</strong></p>
  <p><strong>Subject:</strong> Request under Section 91 CrPC – Auto Escalated</p>
  <p>Respected Sir/Madam,</p>

  <p>This is to notify you that based on prior warnings sent on suspicious activity from your account, and no reply received within the expected time window of 72 hours, we are issuing this CrPC 91 request.</p>

  <p>Suspect Details:</p>
  <ul>
    <li><strong>Username:</strong> {{ username }}</li>
    <li><strong>Email:</strong> {{ email }}</li>
    <li><strong>Flagged Text:</strong><br><pre>{{ text }}</pre></li>
  </ul>

  <p>Please consider this an official request for information under Section 91 of the CrPC.</p>
  <p>Regards,<br>Cyber Monitoring Unit</p>
  <p><em>Generated on {{ generated_on }}</em></p>
</body>
</html>
"""

app = FastAPI()

@app.post("/escalate")
def escalate_cases():
    try:
        cutoff = datetime.utcnow() - timedelta(hours=72)
        to_escalate = collection.find({
            "status": "warning_sent",
            "responded": {"$ne": True},
            "warning_sent_at": {"$lte": cutoff}
        })

        count = 0
        for user in to_escalate:
            email = user.get("email")
            username = user.get("username", "User")
            text = user.get("text", "")

            if not email:
                continue

            html = Template(TEMPLATE_HTML).render(
                recipient=email,
                username=username,
                email=email,
                text=text,
                generated_on=datetime.now().strftime("%d-%m-%Y %H:%M")
            )

            os.makedirs("outputs", exist_ok=True)
            filename = f"crpc_escalation_{uuid.uuid4().hex}.pdf"
            filepath = os.path.join("outputs", filename)
            HTML(string=html).write_pdf(filepath)

            send_email(
                to_address=email,
                subject="⚠ CrPC Escalation - No Response Received",
                body=f"Dear {username},\n\nNo reply was received within 72 hours. Attached is a CrPC 91 escalation notice.\n\nCyber Monitoring Unit",
                attachment_path=filepath
            )

            collection.update_one({"_id": user["_id"]}, {"$set": {
                "status": "escalated",
                "escalated_at": datetime.utcnow(),
                "escalation_pdf": filename
            }})
            count += 1

        return {"message": f"🔺 Total users escalated: {count}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def send_email(to_address, subject, body, attachment_path):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_address
    msg.set_content(body)

    with open(attachment_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="pdf",
            filename=os.path.basename(attachment_path)
        )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)