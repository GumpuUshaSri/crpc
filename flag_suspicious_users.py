from datetime import datetime, timezone
import re
from dotenv import load_dotenv
import os

# Load .env
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client["social_monitoring"]
source_collection = db["messages_telegram"]
flagged_collection = db["flagged_messages"]

# Define suspicious keywords
SUSPICIOUS_KEYWORDS = [
    "betting", "crypto", "money laundering", "nude", "drug", "blackmail",
    "dark web", "bitcoin", "casino", "win money", "10x returns", "double your money"
]

# Compile regex for performance
pattern = re.compile(r"|".join([re.escape(word) for word in SUSPICIOUS_KEYWORDS]), re.IGNORECASE)

# Threshold to consider someone suspicious (e.g., must match 2+ keywords)
SUSPICION_THRESHOLD = 1

flagged_count = 0

# Process messages
for msg in source_collection.find():
    text = str(msg.get("text", ""))
    suspicion_matches = pattern.findall(text)
    suspicion_count = len(suspicion_matches)

    if suspicion_count >= SUSPICION_THRESHOLD:
        msg["suspicion_score"] = suspicion_count
        msg["flagged_at"] = datetime.now(timezone.utc)
        msg["status"] = "warning_pending"

        # Prevent duplicate insert by checking _id
        if not flagged_collection.find_one({"_id": msg["_id"]}):
            flagged_collection.insert_one(msg)
            flagged_count += 1

print(f"✅ Flagged {flagged_count} suspicious messages.")