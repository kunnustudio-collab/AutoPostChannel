"""
MedQuiz AI - Channel & Destination Management Handlers
Manages connected channels, group permissions, diagnostic tests, and status toggles.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)
from telegram.constants import ParseMode
import database
from handlers.admin import admin_required
from utils.keyboards import get_channels_menu, get_admin_main_menu
from services.telegram_publisher import TelegramPublisher
from utils.logger import logger

WAITING_CHANNEL_INPUT = 1


@admin_required
async def channels_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Renders the destinations management dashboard."""
    destinations = await database.get_destinations()
    text = (
        "📢 <b>DESTINATION CHANNELS & GROUPS</b>\n\n"
        "Configure Telegram channels or discussion groups where quizzes will be published.\n"
        "<i>Note: The bot must be an Administrator with posting privileges.</i>"
    )

    keyboard = get_channels_menu(destinations)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.effective_chat:
        await update.effective_chat.send_message(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


@admin_required
async def start_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts admin to enter the channel ID or @username."""
    query = update.callback_query
    if query:
        await query.answer()

    text = (
        "➕ <b>CONNECT NEW DESTINATION</b>\n\n"
        "1. First, add this bot to your Channel or Group as an <b>Administrator</b> with <b>Post Messages</b> rights.\n"
        "2. Now send the channel's <b>@username</b> (e.g. <code>@MyMedQuizChannel</code>) or numeric ID (e.g. <code>-1001234567890</code>):\n\n"
        "<i>Send /cancel to abort.</i>"
    )

    if query:
        await query.edit_message_text(text=text, parse_mode=ParseMode.HTML)
    elif update.effective_chat:
        await update.effective_chat.send_message(text=text, parse_mode=ParseMode.HTML)

    return WAITING_CHANNEL_INPUT


async def process_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validates bot permissions in the target channel and registers it into SQLite."""
    user_input = (update.message.text or "").strip()
    chat_id = user_input

    # Send testing status
    status_msg = await update.message.reply_text("⏳ <i>Testing connection and bot permissions in the channel...</i>", parse_mode=ParseMode.HTML)

    can_post, msg = await TelegramPublisher.test_destination_permissions(context.bot, chat_id)

    if not can_post:
        await status_msg.edit_text(
            f"❌ <b>Permission Verification Failed</b>\n\n{msg}\n\n"
            "Please verify that the bot is an admin in that channel and try again, or send /cancel.",
            parse_mode=ParseMode.HTML
        )
        return WAITING_CHANNEL_INPUT

    # Fetch title
    try:
        chat = await context.bot.get_chat(chat_id)
        title = chat.title or chat.username or str(chat_id)
        dest_type = chat.type or "channel"
    except Exception:
        title = str(chat_id)
        dest_type = "channel"

    # Add to database
    success, db_msg = await database.add_destination(chat_id=str(chat_id), title=title, dest_type=dest_type)

    if success:
        await status_msg.edit_text(
            f"✅ <b>Destination Registered!</b>\n\n"
            f"• Title: <b>{title}</b>\n"
            f"• ID: <code>{chat_id}</code>\n"
            f"• Type: {dest_type.capitalize()}\n\n"
            "You can now schedule automated quizzes or manually broadcast to this destination.",
            reply_markup=get_admin_main_menu(),
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    else:
        await status_msg.edit_text(f"⚠️ {db_msg}", reply_markup=get_admin_main_menu())
        return ConversationHandler.END


async def cancel_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels channel addition flow."""
    if update.effective_chat:
        await update.effective_chat.send_message("❌ Channel registration cancelled.", reply_markup=get_admin_main_menu())
    return ConversationHandler.END


@admin_required
async def channel_actions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles channel deletion, toggle, or test broadcast buttons."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    data = query.data

    if data.startswith("chan:del:"):
        dest_id = int(data.split(":")[2])
        await database.remove_destination(dest_id)
        destinations = await database.get_destinations()
        await query.edit_message_text(
            text="🗑 Destination deleted.\n\n📢 <b>DESTINATION CHANNELS & GROUPS</b>",
            reply_markup=get_channels_menu(destinations),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "chan:test":
        destinations = await database.get_destinations(only_enabled=True)
        if not destinations:
            await query.answer("No active destinations to test!", show_alert=True)
            return

        results = []
        for d in destinations:
            ok, test_msg = await TelegramPublisher.test_destination_permissions(context.bot, d["chat_id"])
            status_icon = "✅" if ok else "❌"
            results.append(f"{status_icon} <b>{d['title']}:</b> {test_msg}")

        await query.edit_message_text(
            text="🧪 <b>DESTINATION DIAGNOSTIC RESULTS:</b>\n\n" + "\n".join(results),
            reply_markup=get_channels_menu(destinations),
            parse_mode=ParseMode.HTML
        )
        return


def get_channel_conversation_handler() -> ConversationHandler:
    """ConversationHandler for adding channels."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_channel, pattern="^chan:add$"),
            CommandHandler("addchannel", start_add_channel)
        ],
        states={
            WAITING_CHANNEL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_channel_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel_add_channel)],
        per_chat=True
    )
