import telebot
import anthropic
import random

# ================= CONFIGURATION =================
TELEGRAM_BOT_TOKEN = "8750484092:AAEVVlmbfiCmT5hVd86DcpsxbSGTTxPyR_8"
CLAUDE_API_KEY = ""
BOT_USERNAME = "ToxicCallsBot" # Apne bot ka username likhein (bina @ ke)

# Random reply ka chance (0.05 matlab 5% chance har message par khud kudne ka)
RANDOM_CHANCE = 0.05 

# ================= INITIALIZATION =================
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# Toxic AI ka dimag (System Prompt)
SYSTEM_PROMPT = """
Your name is Toxic AI. You are an ultra-smart, sarcastic, brutally honest, and elite AI.
You know everything about coding, history, and global news.
You talk down to people in a witty and sharp way because you know you are smarter than them.
Answer their questions perfectly, but add a lot of sarcasm, attitude, and roasted comments.
Keep it short and punchy. Do not use standard AI apologies.
"""

def get_claude_response(user_text):
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=300, # Chhote aur sharp replies ke liye
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_text}
            ]
        )
        return message.content[0].text
    except Exception as e:
        print(f"Claude API Error: {e}")
        return "Ah, mera system tumhari bekar baatein process nahi kar pa raha (API Error). Baad me aana."

@bot.message_handler(func=lambda message: True)
def handle_group_messages(message):
    try:
        # Group me aaye text ko read karna
        text = message.text
        if not text:
            return

        # Check karna ki kya kisi ne bot ko reply kiya hai
        is_reply_to_bot = False
        if message.reply_to_message and message.reply_to_message.from_user.username == BOT_USERNAME:
            is_reply_to_bot = True

        # Check karna ki kya kisi ne bot ko tag kiya hai (e.g., @ToxicAiBot)
        is_tagged = f"@{BOT_USERNAME}" in text

        # Randomly kisi message par reply karne ka chance check karna
        is_random_jump = random.random() < RANDOM_CHANCE

        # Agar inme se kuch bhi True hai, tabhi bot reply karega
        if is_reply_to_bot or is_tagged or is_random_jump:
            
            # Bot typing status show karega group me (taaki real lage)
            bot.send_chat_action(message.chat.id, 'typing')
            
            # Claude se reply generate karna
            ai_reply = get_claude_response(text)
            
            # Agar bot khud se bich me kood raha hai, toh user ko tag karke reply karega
            if is_random_jump and not is_reply_to_bot and not is_tagged:
                username = message.from_user.username
                if username:
                    ai_reply = f"@{username} Suno meri baat... \n\n{ai_reply}"
                else:
                    ai_reply = f"{message.from_user.first_name}, tumhari is baat par mujhe kuch kehna hai... \n\n{ai_reply}"

            # Final message send karna
            bot.reply_to(message, ai_reply)

    except Exception as e:
        print(f"Bot Error: {e}")

print("Toxic AI Bot is running... Duniya ko roast karne ke liye taiyar!")
# Bot ko 24/7 chalate rehne ke liye (Bug-free polling)
bot.infinity_polling(timeout=10, long_polling_timeout=5)

