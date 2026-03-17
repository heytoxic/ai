"""
Telegram Call Bot - Main Bot File (Professional English Edition)
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
# KEYBOARDS (Professional UI)
# ─────────────────────────────────────────────

def get_calling_keyboard(call_id: str) -> InlineKeyboardMarkup:
    """Keyboard shown while call is ringing."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📵 Terminate", callback_data=f"end_{call_id}"),
            InlineKeyboardButton("🔇 Mute", callback_data=f"mute_{call_id}"),
        ],
        [
            InlineKeyboardButton("⏺️ Record", callback_data=f"record_{call_id}"),
            InlineKeyboardButton("👥 Join Call", callback_data=f"join_{call_id}"),
        ],
        [
            InlineKeyboardButton("📡 Bridge to VC", callback_data=f"vc_{call_id}"),
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
            InlineKeyboardButton("🎙️ Telegram VC", callback_data=f"vc_{call_id}"),
            InlineKeyboardButton("📊 Call Stats", callback_data=f"stats_{call_id}"),
        ]
    ])

def get_join_keyboard(call_id: str, join_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎙️ Join Voice Chat", url=join_link)],
        [InlineKeyboardButton("❌ Dismiss", callback_data=f"cancel_join_{call_id}")]
    ])

# ─────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command."""
    text = (
        "📞 *Enterprise Call Bridge*\n\n"
        "Welcome. This system allows you to initiate PSTN calls directly through Telegram.\n\n"
        "*Available Commands:*\n"
        "• `/call <number>` — Initiate a new call\n"
        "• `/endcall` — Terminate active session\n"
        "• `/calls` — List active sessions\n"
        "• `/help` — System documentation\n\n"
        "⚡ _Calls are automatically bridged to the Group Voice Chat._"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *User Documentation*\n\n"
        "*Dialing Protocol:*\n"
        "`/call +1234567890` — Dial with country code\n\n"
        "*In-Call Management:*\n"
        "• *Terminate:* Immediately ends the PSTN link.\n"
        "• *Mute:* Disables your local audio input.\n"
        "• *Record:* Captures the session in `.ogg` format.\n"
        "• *VC Bridge:* Forwards audio to the Telegram Voice Chat.\n\n"
        "*Notes:*\n"
        "• Ensure international format for global numbers.\n"
        "• Recordings are processed and sent upon session completion.\n"
        "• Bot must be an Administrator in groups for VC bridging."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def call_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /call <number> command."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text(
            "❌ *Missing Parameter!*\n\nPlease specify a number: `/call +1234567890`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    number = context.args[0].strip()

    # Basic number validation
    cleaned = number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not cleaned.lstrip("+").isdigit() or len(cleaned) < 7:
        await update.message.reply_text(
            "❌ *Invalid Number Format!*\n\nPlease use: `+ [Country Code] [Number]`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Check if user already has active call
    if call_manager.get_user_call(user_id):
        await update.message.reply_text(
            "⚠️ *Active Session Detected!*\n"
            "Please terminate your current call using `/endcall` first.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Initial Dialing state
    ringing_text = (
        f"📲 *Initiating Request...*\n\n"
        f"📞 Destination: `{number}`\n"
        f"⏱️ Status: 🔔 *Ringing...*\n\n"
        f"_Establishing connection with carrier..._"
    )

    msg = await update.message.reply_text(
        ringing_text,
        parse_mode=ParseMode.MARKDOWN
    )

    # Initiate call via manager
    call_id = await call_manager.initiate_call(
        user_id=user_id,
        chat_id=chat_id,
        number=number,
        message_id=msg.message_id
    )

    if not call_id:
        await msg.edit_text(
            "❌ *Connection Failed!*\n\nUnable to reach the destination carrier.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Update with control dashboard
    await msg.edit_text(
        f"📲 *Dialing Outbound...*\n\n"
        f"📞 Destination: `{number}`\n"
        f"🆔 Session ID: `{call_id[:8]}`\n"
        f"⏱️ Status: 🔔 *Ringing...*\n\n"
        f"_Awaiting subscriber response..._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_calling_keyboard(call_id)
    )

    context.bot_data[f"call_msg_{call_id}"] = {
        "chat_id": chat_id,
        "message_id": msg.message_id
    }

    asyncio.create_task(
        monitor_call_status(context, call_id, number, chat_id, msg.message_id)
    )


async def endcall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /endcall command."""
    user_id = update.effective_user.id
    call_id = call_manager.get_user_call(user_id)

    if not call_id:
        await update.message.reply_text("❌ No active session found for your ID.")
        return

    result = await call_manager.end_call(call_id)
    duration = result.get("duration", 0)
    mins, secs = divmod(duration, 60)

    await update.message.reply_text(
        f"📵 *Call Terminated*\n\n"
        f"⏱️ Total Duration: `{mins}m {secs}s`\n"
        f"📋 Status: Session ended by initiator",
        parse_mode=ParseMode.MARKDOWN
    )


async def active_calls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active calls."""
    calls = call_manager.get_all_active_calls()
    if not calls:
        await update.message.reply_text("📭 No active sessions currently on the bridge.")
        return

    text = "📞 *Live Session Monitor:*\n\n"
    for c in calls:
        text += (
            f"• `{c['call_id'][:8]}` → `{c['number']}`\n"
            f"  ⏱️ {c['duration']}s | 👤 User: {c['user_id']}\n\n"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─────────────────────────────────────────────
# CALLBACK HANDLERS
# ─────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query: CallbackQuery = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split("_", 1)
    action, call_id = parts[0], parts[1] if len(parts) > 1 else None

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
        await query.edit_message_text("❌ Session has already expired.")
        return

    result = await call_manager.end_call(call_id)
    duration = result.get("duration", 0)
    mins, secs = divmod(duration, 60)

    rec_info = f"\n⏺️ Archive: `{result['recording_file']}`" if result.get("recording_file") else ""

    await query.edit_message_text(
        f"📵 *Call Completed*\n\n"
        f"📞 Destination: `{call['number']}`\n"
        f"⏱️ Total Duration: `{mins}m {secs}s`\n"
        f"📊 Final Status: Disconnected{rec_info}",
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_mute(query: CallbackQuery, context, call_id: str):
    call = call_manager.get_call(call_id)
    if not call:
        await query.answer("Session not found", show_alert=True)
        return

    is_muted = await call_manager.toggle_mute(call_id)
    await query.answer("Microphone Muted" if is_muted else "Microphone Active")

    is_recording = call_manager.is_recording(call_id)
    await query.edit_message_reply_markup(
        reply_markup=get_active_call_keyboard(call_id, is_recording, is_muted)
    )


async def handle_record(query: CallbackQuery, context, call_id: str):
    call = call_manager.get_call(call_id)
    if not call:
        await query.answer("Session not found", show_alert=True)
        return

    is_recording = call_manager.is_recording(call_id)

    if is_recording:
        rec_file = await call_manager.stop_recording(call_id)
        await query.answer("Recording Terminated")

        if rec_file and os.path.exists(rec_file):
            try:
                with open(rec_file, "rb") as f:
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id,
                        audio=f,
                        title=f"Call Log - {call['number']}",
                        caption=f"⏺️ *Call Recording Data*\n📞 Destination: {call['number']}",
                        parse_mode=ParseMode.MARKDOWN
                    )
            except Exception as e:
                logger.error(f"Transfer Error: {e}")
    else:
        await call_manager.start_recording(call_id)
        await query.answer("Recording Commenced")

    is_muted = call_manager.is_muted(call_id)
    is_recording_now = call_manager.is_recording(call_id)
    await query.edit_message_reply_markup(
        reply_markup=get_active_call_keyboard(call_id, is_recording_now, is_muted)
    )


async def handle_join(query: CallbackQuery, context, call_id: str):
    call = call_manager.get_call(call_id)
    if not call:
        await query.answer("Session expired", show_alert=True)
        return

    join_link = await call_manager.get_join_link(call_id)
    if not join_link:
        await query.answer("Join Link Unavailable", show_alert=True)
        return

    await query.answer("Access Link Generated")
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"👥 *Join In-Progress Session*\n\n"
            f"📞 Destination: `{call['number']}`\n"
            f"Use the secure link below to participate:"
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_join_keyboard(call_id, join_link)
    )


async def handle_vc_forward(query: CallbackQuery, context, call_id: str):
    call = call_manager.get_call(call_id)
    if not call:
        await query.answer("Session expired", show_alert=True)
        return

    await query.answer("Bridging to Telegram VC...")

    success = await call_manager.forward_to_voice_chat(
        call_id=call_id,
        chat_id=query.message.chat_id
    )

    if success:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                f"🎙️ *Live VC Bridge Active!*\n\n"
                f"The call with `{call['number']}` is now live in this group's Voice Chat.\n\n"
                f"_Members can listen and participate._ 👥"
            ),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                "❌ *VC Bridge Failure*\n\n"
                "Please verify:\n"
                "• Bot has Admin Permissions\n"
                "• Voice Chat is currently active\n"
                "• Group ID is registered"
            ),
            parse_mode=ParseMode.MARKDOWN
        )


async def handle_stats(query: CallbackQuery, context, call_id: str):
    stats = call_manager.get_call_stats(call_id)
    if not stats:
        await query.answer("Telemetry data unavailable", show_alert=True)
        return

    text = (
        f"📊 *Session Telemetry*\n\n"
        f"📞 Destination: `{stats['number']}`\n"
        f"⏱️ Duration: `{stats['duration']}s`\n"
        f"📶 Quality: `{stats['quality']}`\n"
        f"🔊 Codec: `{stats['audio_codec']}`\n"
        f"📡 Latency: `{stats['latency']}ms`\n"
        f"⏺️ Archive: `{'Enabled' if stats['is_recording'] else 'Disabled'}`\n"
        f"📲 VC Bridge: `{'Live' if stats['vc_forward'] else 'Offline'}`"
    )
    await query.answer()
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN
    )


# ─────────────────────────────────────────────
# STATUS MONITORS
# ─────────────────────────────────────────────

async def monitor_call_status(context, call_id: str, number: str, chat_id: int, message_id: int):
    """Monitor call status and update message accordingly."""
    max_wait = 60 
    elapsed = 0
    dots = [".", "..", "..."]

    while elapsed < max_wait:
        await asyncio.sleep(2)
        elapsed += 2

        call = call_manager.get_call(call_id)
        if not call: break

        status = call.get("status", "ringing")

        if status == "connected":
            asyncio.create_task(track_call_duration(context, call_id, number, chat_id, message_id))
            return

        elif status == "failed":
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ *Connection Error*\n\nDestination: `{number}`\nReason: Carrier Refusal",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        elif status == "busy":
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"📵 *Subscriber Busy*\n\nDestination `{number}` is currently occupied.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        elif status == "no_answer":
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"🔕 *No Response*\n\nThe subscriber at `{number}` did not answer.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        dot = dots[(elapsed // 2) % 3]
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"📲 *Dialing Outbound{dot}*\n\n"
                    f"📞 Destination: `{number}`\n"
                    f"🆔 Session ID: `{call_id[:8]}`\n"
                    f"⏱️ Status: 🔔 *Ringing{dot}*\n\n"
                    f"_Waiting for response..._"
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_calling_keyboard(call_id)
            )
        except Exception: pass

    await call_manager.end_call(call_id)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"⏰ *Session Timeout*\n\nNo response received from `{number}` within 60s.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception: pass


async def track_call_duration(context, call_id: str, number: str, chat_id: int, message_id: int):
    """Track and display live call duration."""
    start_time = asyncio.get_event_loop().time()

    while True:
        await asyncio.sleep(5)

        call = call_manager.get_call(call_id)
        if not call or call.get("status") != "connected":
            break

        elapsed = int(asyncio.get_event_loop().time() - start_time)
        mins, secs = divmod(elapsed, 60)

        is_recording = call_manager.is_recording(call_id)
        is_muted = call_manager.is_muted(call_id)
        vc_active = call.get("vc_forward", False)

        rec_tag = " ⏺️ REC" if is_recording else ""
        mute_tag = " 🔇" if is_muted else ""
        vc_tag = " 📡 VC" if vc_active else ""

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"📞 *Session Active*{rec_tag}{mute_tag}{vc_tag}\n\n"
                    f"📱 Destination: `{number}`\n"
                    f"⏱️ Duration: `{mins:02d}:{secs:02d}`\n"
                    f"📶 Status: ✅ *Connected*\n\n"
                    f"_Use the dashboard below to control the session._"
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_active_call_keyboard(call_id, is_recording, is_muted)
            )
        except Exception: pass

# ─────────────────────────────────────────────
# MAIN EXECUTION
# ─────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        logger.error("CRITICAL: BOT_TOKEN is missing!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("call", call_command))
    app.add_handler(CommandHandler("end", endcall_command))
    app.add_handler(CommandHandler("calls", active_calls_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Service Online. Awaiting requests...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
        
