# 📞 Telegram Call Bot

Ek powerful Telegram bot jo aapko seedha Telegram se phone calls karne deta hai!

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| `/call +91XXXXXXXXXX` | Kisi bhi number pe call karo |
| 🔔 Ringing Alerts | Call ringing ka live status |
| 📵 End Call | Button se call band karo |
| 🔇 Mute/Unmute | Mic toggle |
| ⏺️ Record Call | Call record karo, auto-download |
| 👥 Join Call | Link se koi bhi join kar sake |
| 📡 Live VC Forward | Call audio ko Telegram Voice Chat pe broadcast karo |
| 📊 Call Stats | Duration, quality, latency stats |

---

## 🚀 Setup Guide

### Step 1: Bot Token Lo

1. Telegram mein [@BotFather](https://t.me/BotFather) ko message karo
2. `/newbot` likho
3. Naam aur username do
4. **Token copy karo** (iska format: `1234567890:ABCdef...`)

### Step 2: Twilio Account Banao (Real Calls ke liye)

1. [twilio.com](https://twilio.com) pe free account banao
2. Console se lo:
   - `Account SID`
   - `Auth Token`  
   - Ek phone number kharido (Trial mein free milta hai)

### Step 3: Bot Install Karo

```bash
# Files download karo
git clone <repo> telegram_call_bot
cd telegram_call_bot

# Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Dependencies install karo
pip install -r requirements.txt

# Config setup
cp .env.example .env
nano .env  # Apni values daalo
```

### Step 4: .env File Edit Karo

```env
BOT_TOKEN=aapka_bot_token
USE_TWILIO=true
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_PHONE_NUMBER=+1234567890
```

### Step 5: Bot Run Karo

```bash
python bot.py
```

---

## 📡 Telegram VC Forward Setup

Voice Chat forward feature ke liye **userbot** chahiye:

### Step 1: API Keys Lo
1. [my.telegram.org](https://my.telegram.org) pe jao
2. "API Development Tools" mein `api_id` aur `api_hash` lo

### Step 2: Session String Generate Karo

```python
from pyrogram import Client

app = Client("session", api_id=YOUR_API_ID, api_hash="YOUR_API_HASH")
app.start()
print(app.export_session_string())
app.stop()
```

### Step 3: .env mein add karo

```env
USERBOT_API_ID=12345678
USERBOT_API_HASH=abcdef...
USERBOT_SESSION=BQANxxxxxx...
```

---

## 💬 Bot Commands

```
/start       - Bot shuru karo
/call <num>  - Call karo (e.g., /call +911234567890)
/endcall     - Active call band karo
/calls       - Sab active calls dekho
/help        - Help dekho
```

---

## 🏗️ Architecture

```
bot.py              ← Main bot, commands, callbacks
call_manager.py     ← Call sessions, Twilio integration
config.py           ← Settings loader
.env                ← Secrets (yahan se edit karo)
recordings/         ← Call recordings save hoti hain yahan
```

---

## ⚙️ Call Flow

```
User: /call +91XXXXXXXXXX
       ↓
Bot sends "Ringing..." message with inline buttons
       ↓
Twilio dials the number
       ↓
Number receives? → Status: "Connected" 
       ↓
Duration counter starts (updates every 5s)
       ↓
User presses End Call → Call terminates
       ↓
Summary: duration + recording link
```

---

## 🔧 Troubleshooting

**Bot respond nahi kar raha?**
- Token sahi hai? `.env` check karo
- `python bot.py` run karo aur errors dekho

**Call nahi lag rahi?**
- Twilio credentials sahi hain?
- Trial account mein sirf verified numbers pe call ho sakti hai
- `USE_TWILIO=true` set hai?

**VC Forward kaam nahi kar raha?**
- Group mein bot ko admin banao
- Group mein Voice Chat active karo
- Userbot session valid hai?

---

## 📝 Notes

- **Simulation Mode**: Twilio credentials ke bina bot demo mode mein chalega (actual call nahi lagegi)
- **Trial Twilio**: Free trial mein sirf apne verified numbers pe call lagti hai
- **Recording Format**: `.ogg` format mein save hoti hai

---

## 🛡️ Legal Notice

Yeh bot sirf authorized use ke liye hai. Call recording laws aapke desh mein alag ho sakti hain. Responsible use karo.
