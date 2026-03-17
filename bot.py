"""
Telegram Call Bot - Main Bot File
Uses: python-telegram-bot, pytgcalls, pjsua2/Twilio for actual PSTN calls
"""

import asyncio
import logging
import os
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode
from call_manager import CallManager
from config import BOT_TOKEN, ADMIN_IDS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)
logger = logging.getLogger(__name__)

# Global call manager
call_manager = CallManager()

# ─────────────────────────────────────────────
# KEYBOARDS
# ─────────────────────────────────────────────

def get_calling_keyboard(call_id: str) -> InlineKeyboardMarkup:
    """Keyboard shown while call is ringing."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📵 End Call", callback_data=f"end_{call_id}"),
            InlineKeyboardButton("🔇 Mute", callback_data=f"mute_{call_id}"),
        ],
        [
            InlineKeyboardButton("⏺️ Record Call", callback_data=f"record_{call_id}"),
            InlineKeyboardButton("👥 Join Call", callback_data=f"join_{call_id}"),
        ],
        [
            InlineKeyboardButton("📞 Live VC Forward", callback_data=f"vc_{call_id}"),
        ]
    ])

def get_active_call_keyboard(call_id: str, is_recording: bool = False, is_muted: bool = False) -> InlineKeyboardMarkup:
    """Keyboard shown during active call."""
    rec_text = "⏹️ Stop Recording" if is_recording else "⏺️ Start Recording"
    mute_text = "🔊 Unmute" if is_muted else "🔇 Mute"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📵 End Call", callback_data=f"end_{call_id}"),
            InlineKeyboardButton(mute_text, callback_data=f"mute_{call_id}"),
        ],
        [
            InlineKeyboardButton(rec_text, callback_data=f"record_{call_id}"),
            InlineKeyboardButton("👥 Join Call", callback_data=f"join_{call_id}"),
        ],
        [
            InlineKeyboardButton("📞 Telegram VC", callback_data=f"vc_{call_id}"),
            InlineKeyboardButton("📊 Call Stats", callback_data=f"stats_{call_id}"),
        ]
    ])

def get_join_keyboard(call_id: str, join_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎙️ Join Voice Chat", url=join_link)],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_join_{call_id}")]
    ])

# ─────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command."""
    text = (
        "📞 *Call Bot*\n\n"
        "Yeh bot aapko Telegram se seedha phone calls karne deta hai!\n\n"
        "*Commands:*\n"
        "• `/call +91XXXXXXXXXX` — Call karo\n"
        "• `/endcall` — Active call band karo\n"
        "• `/calls` — Active calls dekho\n"
        "• `/help` — Help dekho\n\n"
        "⚡ _Call karte hi Telegram VC pe forward ho jaayegi!_"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Bot Help*\n\n"
        "*Calling:*\n"
        "`/call +91XXXXXXXXXX` — Number pe call karo\n"
        "`/call +1-800-123-4567` — US number\n\n"
        "*During Call:*\n"
        "• 📵 End Call — Call band karo\n"
        "• 🔇 Mute — Apna mic band karo\n"
        "• ⏺️ Record — Call record karo\n"
        "• 👥 Join — Link se join karo\n"
        "• 📞 Telegram VC — Voice chat pe le jao\n\n"
        "*Notes:*\n"
        "• International numbers ke liye country code lagao\n"
        "• Recording `.ogg` format mein milegi\n"
        "• VC forward ke liye group mein bot add karo"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def call_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /call <number> command."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text(
            "❌ Number daalo!\n\nExample: `/call +911234567890`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    number = context.args[0].strip()

    # Basic number validation
    cleaned = number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not cleaned.lstrip("+").isdigit() or len(cleaned) < 7:
        await update.message.reply_text(
            "❌ *Invalid number!*\n\nSahi format: `+91XXXXXXXXXX`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Check if user already has active call
    if call_manager.get_user_call(user_id):
        await update.message.reply_text(
            "⚠️ Aapki pehle se ek call chal rahi hai!\n"
            "Pehle `/endcall` karo.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Send ringing message
    ringing_text = (
        f"📲 *Calling...*\n\n"
        f"📞 Number: `{number}`\n"
        f"⏱️ Status: 🔔 *Ringing...*\n\n"
        f"_Kripya wait karo..._"
    )

    msg = await update.message.reply_text(
        ringing_text,
        parse_mode=ParseMode.MARKDOWN
    )

    # Initiate call
    call_id = await call_manager.initiate_call(
        user_id=user_id,
        chat_id=chat_id,
        number=number,
        message_id=msg.message_id
    )

    if not call_id:
        await msg.edit_text(
            "❌ *Call failed!*\n\nNumber se connect nahi ho saka.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Update message with ringing keyboard
    await msg.edit_text(
        f"📲 *Calling...*\n\n"
        f"📞 Number: `{number}`\n"
        f"🆔 Call ID: `{call_id[:8]}...`\n"
        f"⏱️ Status: 🔔 *Ringing...*\n\n"
        f"_Receive hone ka wait kar raha hoon..._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_calling_keyboard(call_id)
    )

    # Store message for later updates
    context.bot_data[f"call_msg_{call_id}"] = {
        "chat_id": chat_id,
        "message_id": msg.message_id
    }

    # Start call status monitor
    asyncio.create_task(
        monitor_call_status(context, call_id, number, chat_id, msg.message_id)
    )


async def endcall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /endcall command."""
    user_id = update.effective_user.id
    call_id = call_manager.get_user_call(user_id)

    if not call_id:
        await update.message.reply_text("❌ Koi active call nahi hai.")
        return

    result = await call_manager.end_call(call_id)
    duration = result.get("duration", 0)
    mins = duration // 60
    secs = duration % 60

    await update.message.reply_text(
        f"📵 *Call Ended*\n\n"
        f"⏱️ Duration: `{mins}m {secs}s`\n"
        f"📋 Status: Ended by user",
        parse_mode=ParseMode.MARKDOWN
    )


async def active_calls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active calls."""
    calls = call_manager.get_all_active_calls()
    if not calls:
        await update.message.reply_text("📭 Koi active call nahi hai.")
        return

    text = "📞 *Active Calls:*\n\n"
    for c in calls:
        text += (
            f"• `{c['call_id'][:8]}...` → `{c['number']}`\n"
            f"  ⏱️ {c['duration']}s | 👤 User: {c['user_id']}\n\n"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─────────────────────────────────────────────
# CALLBACK HANDLERS
# ─────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline button presses."""
    query: CallbackQuery = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split("_", 1)
    action = parts[0]
    call_id = parts[1] if len(parts) > 1 else None

    if action == "end":
        await handle_end_call(query, context, call_id)
    elif action == "mute":
        await handle_mute(query, context, call_id)
    elif action == "record":
        await handle_record(query, context, call_id)
    elif action == "join":
        await handle_join(query, context, call_id)
    elif action == "vc":
        await handle_vc_forward(query, context, call_id)
    elif action == "stats":
        await handle_stats(query, context, call_id)
    elif action == "cancel":
        await query.edit_message_reply_markup(reply_markup=None)


async def handle_end_call(query: CallbackQuery, context, call_id: str):
    call = call_manager.get_call(call_id)
    if not call:
        await query.edit_message_text("❌ Call already ended.")
        return

    result = await call_manager.end_call(call_id)
    duration = result.get("duration", 0)
    mins = duration // 60
    secs = duration % 60

    rec_info = ""
    if result.get("recording_file"):
        rec_info = f"\n⏺️ Recording: `{result['recording_file']}`"

    await query.edit_message_text(
        f"📵 *Call Ended*\n\n"
        f"📞 Number: `{call['number']}`\n"
        f"⏱️ Duration: `{mins}m {secs}s`\n"
        f"📊 Status: Completed{rec_info}",
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_mute(query: CallbackQuery, context, call_id: str):
    call = call_manager.get_call(call_id)
    if not call:
        await query.answer("Call nahi mili!", show_alert=True)
        return

    is_muted = await call_manager.toggle_mute(call_id)
    status = "🔇 Muted" if is_muted else "🔊 Unmuted"
    await query.answer(status)

    # Update keyboard
    is_recording = call_manager.is_recording(call_id)
    await query.edit_message_reply_markup(
        reply_markup=get_active_call_keyboard(call_id, is_recording, is_muted)
    )


async def handle_record(query: CallbackQuery, context, call_id: str):
    call = call_manager.get_call(call_id)
    if not call:
        await query.answer("Call nahi mili!", show_alert=True)
        return

    is_recording = call_manager.is_recording(call_id)

    if is_recording:
        rec_file = await call_manager.stop_recording(call_id)
        await query.answer("⏹️ Recording ruk gayi!")

        # Send recording file
        if rec_file and os.path.exists(rec_file):
            try:
                with open(rec_file, "rb") as f:
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id,
                        audio=f,
                        title=f"Call Recording - {call['number']}",
                        caption=f"⏺️ Call recording\n📞 {call['number']}"
                    )
            except Exception as e:
                logger.error(f"Error sending recording: {e}")
    else:
        await call_manager.start_recording(call_id)
        await query.answer("⏺️ Recording shuru ho gayi!")

    is_muted = call_manager.is_muted(call_id)
    is_recording_now = call_manager.is_recording(call_id)
    await query.edit_message_reply_markup(
        reply_markup=get_active_call_keyboard(call_id, is_recording_now, is_muted)
    )


async def handle_join(query: CallbackQuery, context, call_id: str):
    call = call_manager.get_call(call_id)
    if not call:
        await query.answer("Call nahi mili!", show_alert=True)
        return

    join_link = await call_manager.get_join_link(call_id)
    if not join_link:
        await query.answer("Join link available nahi hai!", show_alert=True)
        return

    await query.answer("Join link generate ho gayi!")
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"👥 *Call Join Karo*\n\n"
            f"📞 Number: `{call['number']}`\n"
            f"🔗 Link se join karo:"
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_join_keyboard(call_id, join_link)
    )


async def handle_vc_forward(query: CallbackQuery, context, call_id: str):
    call = call_manager.get_call(call_id)
    if not call:
        await query.answer("Call nahi mili!", show_alert=True)
        return

    await query.answer("⏳ Telegram VC pe forward ho raha hai...")

    success = await call_manager.forward_to_voice_chat(
        call_id=call_id,
        chat_id=query.message.chat_id
    )

    if success:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                f"🎙️ *Live VC Forward Active!*\n\n"
                f"📞 `{call['number']}` ki call ab Telegram Voice Chat pe live hai!\n\n"
                f"_Sabhi group members sun sakte hain_ 👥"
            ),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                "❌ *VC Forward failed!*\n\n"
                "Ensure karo ki:\n"
                "• Bot group mein admin hai\n"
                "• Group mein Voice Chat active hai\n"
                "• `/setvoicechat` command use karo"
            ),
            parse_mode=ParseMode.MARKDOWN
        )


async def handle_stats(query: CallbackQuery, context, call_id: str):
    stats = call_manager.get_call_stats(call_id)
    if not stats:
        await query.answer("Stats available nahi hain!", show_alert=True)
        return

    text = (
        f"📊 *Call Statistics*\n\n"
        f"📞 Number: `{stats['number']}`\n"
        f"⏱️ Duration: `{stats['duration']}s`\n"
        f"📶 Quality: `{stats['quality']}`\n"
        f"🔊 Audio: `{stats['audio_codec']}`\n"
        f"📡 Latency: `{stats['latency']}ms`\n"
        f"⏺️ Recording: `{'Active' if stats['is_recording'] else 'Off'}`\n"
        f"📲 VC Forward: `{'Active' if stats['vc_forward'] else 'Off'}`"
    )
    await query.answer()
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN
    )


# ─────────────────────────────────────────────
# CALL STATUS MONITOR
# ─────────────────────────────────────────────

async def monitor_call_status(context, call_id: str, number: str, chat_id: int, message_id: int):
    """Monitor call status and update message accordingly."""
    max_wait = 60  # 60 seconds ring timeout
    elapsed = 0
    dots = [".", "..", "..."]

    while elapsed < max_wait:
        await asyncio.sleep(2)
        elapsed += 2

        call = call_manager.get_call(call_id)
        if not call:
            break

        status = call.get("status", "ringing")

        if status == "connected":
            duration_tracker = asyncio.create_task(
                track_call_duration(context, call_id, number, chat_id, message_id)
            )
            return

        elif status == "failed":
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"❌ *Call Failed*\n\n"
                    f"📞 Number: `{number}`\n"
                    f"❗ Could not connect"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            return

        elif status == "busy":
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"📵 *Number Busy*\n\n"
                    f"📞 `{number}` abhi busy hai\n"
                    f"_Baad mein try karo_"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            return

        elif status == "no_answer":
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"🔕 *No Answer*\n\n"
                    f"📞 `{number}` ne receive nahi kiya"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # Still ringing - update dots animation
        dot = dots[(elapsed // 2) % 3]
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"📲 *Calling{dot}*\n\n"
                    f"📞 Number: `{number}`\n"
                    f"🆔 Call ID: `{call_id[:8]}...`\n"
                    f"⏱️ Status: 🔔 *Ringing{dot}*\n\n"
                    f"_Receive hone ka wait kar raha hoon..._"
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_calling_keyboard(call_id)
            )
        except Exception:
            pass

    # Timeout
    await call_manager.end_call(call_id)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=(
                f"⏰ *Call Timeout*\n\n"
                f"📞 `{number}` ne 60 seconds mein receive nahi kiya"
            ),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass


async def track_call_duration(context, call_id: str, number: str, chat_id: int, message_id: int):
    """Track and display call duration."""
    start_time = asyncio.get_event_loop().time()

    while True:
        await asyncio.sleep(5)

        call = call_manager.get_call(call_id)
        if not call or call.get("status") != "connected":
            break

        elapsed = int(asyncio.get_event_loop().time() - start_time)
        mins = elapsed // 60
        secs = elapsed % 60

        is_recording = call_manager.is_recording(call_id)
        is_muted = call_manager.is_muted(call_id)
        vc_active = call.get("vc_forward", False)

        rec_indicator = " ⏺️ REC" if is_recording else ""
        mute_indicator = " 🔇" if is_muted else ""
        vc_indicator = " 📡 VC" if vc_active else ""

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"📞 *Call Active*{rec_indicator}{mute_indicator}{vc_indicator}\n\n"
                    f"📱 Number: `{number}`\n"
                    f"⏱️ Duration: `{mins:02d}:{secs:02d}`\n"
                    f"📶 Status: ✅ *Connected*\n\n"
                    f"_Buttons se call control karo_ 👇"
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_active_call_keyboard(call_id, is_recording, is_muted)
            )
        except Exception:
            pass


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set in config.py or .env!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("call", call_command))
    app.add_handler(CommandHandler("endcall", endcall_command))
    app.add_handler(CommandHandler("calls", active_calls_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
