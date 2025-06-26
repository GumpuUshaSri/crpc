from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from jinja2 import Template
from datetime import datetime, timedelta
from weasyprint import HTML
from dotenv import load_dotenv
from pymongo import MongoClient
import smtplib, os, uuid, csv, io, re
from email.message import EmailMessage
import imaplib
import email
from email.header import decode_header

# Load environment variables
load_dotenv()
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
MONGO_URI = os.getenv("MONGO_URI")  # MongoDB Atlas URI

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["crpcdb"]  # Use your actual DB name here
flagged_collection = db["flagged_messages"]
crpc_collection = db["crpc_requests"]

app = FastAPI()

# Suspicious keywords
SUSPICIOUS_KEYWORDS = [
    "betting", "crypto", "money laundering", "nude", "drug", "blackmail",
    "dark web", "bitcoin", "casino", "win money", "10x returns", "double your money"
]
pattern = re.compile(r"|".join(re.escape(word) for word in SUSPICIOUS_KEYWORDS), re.IGNORECASE)

# ---------------------------- MODELS ----------------------------
class CrPCData(BaseModel):
    officer_name: str
    designation: str
    police_station: str
    contact_info: str
    case_number: str
    recipient: str
    recipient_email: str
    suspect_identifier: str
    date_range: str
    data_requested: str
    case_purpose: str

# ---------------------------- TEMPLATE ----------------------------
TEMPLATE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>CrPC 91 Notice</title>
</head>
<body>
  <p><strong>To:</strong> {{ recipient }}</p>
  <p><strong>Subject:</strong> Request under Section 91 CrPC – Case {{ case_number }}</p>
  <p>Dear Sir/Madam,</p>
  <p>I am {{ officer_name }}, {{ designation }}, {{ police_station }}.</p>
  <p>Please provide the following information related to:</p>
  <ul>
    <li><strong>Suspect:</strong> {{ suspect_identifier }}</li>
    <li><strong>Date Range:</strong> {{ date_range }}</li>
    <li><strong>Requested Info:</strong><br><pre>{{ data_requested }}</pre></li>
  </ul>
  <p>This is needed for: {{ case_purpose }}</p>
  <p>Regards,<br>{{ officer_name }}<br>{{ contact_info }}</p>
  <p><em>Generated on {{ generated_on }}</em></p>
</body>
</html>
"""

# ---------------------------- ENDPOINTS ----------------------------

@app.get("/")
def root():
    return {"message": "🚀 CrPC FastAPI server is running."}

@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    
    contents = await file.read()
    decoded = contents.decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))

    flagged = 0
    for row in reader:
        text = row.get("text", "")
        suspicion_score = len(pattern.findall(text))
        if suspicion_score >= 1:
            row["suspicion_score"] = suspicion_score
            row["flagged_at"] = datetime.utcnow()
            row["status"] = "warning_pending"
            flagged_collection.insert_one(row)
            flagged += 1
    return {"message": f"✅ Uploaded and flagged {flagged} messages."}

@app.post("/send-warnings")
def send_warnings():
    count = 0
    for user in flagged_collection.find({"status": "warning_pending"}):
        email_addr = user.get("email")
        if not email_addr:
            continue
        msg = EmailMessage()
        msg["Subject"] = "⚠ Suspicious Activity Detected"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = email_addr
        msg.set_content(f"""Dear {user.get('username','User')},

We found suspicious content in your message:
---
{text := user.get('text','')}
---

Please reply within 48 hours. If no response is received, legal action may be initiated.

Regards,
Cyber Monitoring Unit""")
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                smtp.send_message(msg)
            flagged_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"status": "warning_sent", "warning_sent_at": datetime.utcnow()}}
            )
            count += 1
        except Exception as e:
            print(f"❌ Could not send to {email_addr}: {e}")
    return {"message": f"✅ Sent warnings to {count} users."}

@app.post("/check-replies")
def check_replies():
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    imap.select("inbox")
    status, messages = imap.search(None, 'UNSEEN')
    if status != "OK":
        return {"message": "❌ No unseen messages"}

    found = 0
    for num in messages[0].split():
        _, msg_data = imap.fetch(num, "(RFC822)")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                sender = email.utils.parseaddr(msg.get("From"))[1]
                user = flagged_collection.find_one({"email": sender, "status": "warning_sent"})
                if not user:
                    continue
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            break
                else:
                    body = msg.get_payload(decode=True).decode()
                flagged_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "status": "responded",
                        "responded_at": datetime.utcnow(),
                        "reply_content": body.strip()[:1000],
                        "responded": True
                    }}
                )
                found += 1
    imap.logout()
    return {"message": f"✅ Processed {found} replies."}

@app.post("/escalate")
def escalate_and_send():
    cutoff = datetime.utcnow() - timedelta(hours=72)
    to_escalate = list(flagged_collection.find({
        "status": "warning_sent",
        "responded": {"$ne": True},
        "warning_sent_at": {"$lte": cutoff}
    }))

    count = 0
    for user in to_escalate:
        html = Template(TEMPLATE_HTML).render(
            officer_name="Inspector General",
            designation="Cyber Cell",
            police_station="Hyderabad HQ",
            contact_info="cybercell@hyderabadpolice.gov.in",
            case_number=f"CASE-{uuid.uuid4().hex[:8].upper()}",
            recipient=user.get("username", "User"),
            suspect_identifier=user.get("username", ""),
            date_range="Last 30 days",
            data_requested=f"All messages related to: {user.get('text','')}",
            case_purpose="Legal investigation of flagged cyber activity",
            generated_on=datetime.now().strftime("%Y-%m-%d %H:%M")
        )

        filename = f"crpc_{uuid.uuid4().hex}.pdf"
        filepath = os.path.join("outputs", filename)
        os.makedirs("outputs", exist_ok=True)
        HTML(string=html).write_pdf(filepath)

        send_email(
            to_address=user.get("email"),
            subject="CrPC 91 Notice",
            body="Attached is a legal notice under CrPC 91 regarding your activity.",
            attachment_path=filepath
        )

        flagged_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"status": "escalated", "escalated_at": datetime.utcnow()}}
        )

        crpc_collection.insert_one({
            "user": user.get("username"),
            "email": user.get("email"),
            "pdf": filename,
            "sent_at": datetime.utcnow()
        })
        count += 1

    return {"message": f"🚨 Escalated and sent CrPC to {count} users."}

@app.post("/generate")
def generate_pdf(data: CrPCData):
    html = Template(TEMPLATE_HTML).render(**data.dict(), generated_on=datetime.now().strftime("%Y-%m-%d %H:%M"))
    filename = f"crpc_{uuid.uuid4().hex}.pdf"
    filepath = os.path.join("outputs", filename)
    os.makedirs("outputs", exist_ok=True)
    HTML(string=html).write_pdf(filepath)
    send_email(data.recipient_email, f"CrPC Request - {data.case_number}", "See attached legal request", filepath)
    crpc_collection.insert_one({**data.dict(), "filename": filename, "sent_at": datetime.utcnow()})
    return {"message": "✅ CrPC request sent", "filename": filename}

@app.get("/download/{filename}")
def download_file(filename: str):
    path = os.path.join("outputs", filename)
    if os.path.exists(path):
        return FileResponse(path, media_type="application/pdf", filename=filename)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/list-files")
def list_files():
    return {"files": os.listdir("outputs") if os.path.exists("outputs") else []}

# ---------------------------- UTILITY ----------------------------

def send_email(to_address, subject, body, attachment_path):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_address
    msg.set_content(body)
    with open(attachment_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=os.path.basename(attachment_path))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)
