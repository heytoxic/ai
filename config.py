"""
Configuration - Edit these values!
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── TELEGRAM ────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Admin user IDs (can use /calls command etc.)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip().isdigit()]

# ─── TWILIO (for real PSTN calls) ────────────
USE_TWILIO = os.getenv("USE_TWILIO", "false").lower() == "true"
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")  # e.g., +1234567890

# ─── USERBOT (for Telegram VC forwarding) ────
# Required for pytgcalls voice chat feature
USERBOT_SESSION = os.getenv("USERBOT_SESSION", "")
USERBOT_API_ID = os.getenv("USERBOT_API_ID", "")
USERBOT_API_HASH = os.getenv("USERBOT_API_HASH", "")

# ─── RECORDING ───────────────────────────────
RECORDING_DIR = os.getenv("RECORDING_DIR", "recordings")
MAX_RECORDING_DURATION = int(os.getenv("MAX_RECORDING_DURATION", "3600"))  # seconds

# ─── CALL SETTINGS ───────────────────────────
MAX_CALL_DURATION = int(os.getenv("MAX_CALL_DURATION", "3600"))  # 1 hour
RING_TIMEOUT = int(os.getenv("RING_TIMEOUT", "60"))  # seconds before timeout
