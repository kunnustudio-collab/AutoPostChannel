"""
MedQuiz AI - Start & Help Handlers
Handles /start, /help, and authentication routing.
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import database
from utils.keyboards import get_admin_main_menu
from utils.logger import logger

ADMIN_PANEL_HEADER = """<b>╔══════════════════════╗
     🧠 MEDQUIZ AI
     ADMIN PANEL
╚══════════════════════╝</b>

Welcome to <b>MedQuiz AI</b> Control Center.
Automated, high-yield NEET & MBBS Quiz Poll generation.

Choose an option below:"""

USER_WELCOME_MSG = """Welcome to <b>MedQuiz AI</b> 🧠
Daily NEET & MBBS medical quizzes.

<i>Follow our official channels to participate in daily high-yield quizzes and test your medical concepts!</i>"""

ADMIN_HELP_MSG = """🧠 <b>MedQuiz AI - Admin Commands</b>

/start - Open Admin Control Panel
/admin - Open Admin Control Panel
/generate - Start AI Quiz Generation wizard
/schedule - Manage automated posting schedules
/channels - Manage connected channels and groups
/subjects - View & add custom subjects
/stats - View live quiz and AI analytics
/history - Browse past generated questions
/settings - Configure AI & posting settings
/test - Run diagnostics and connection checks"""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for /start and /admin."""
    if not update.effective_user or not update.effective_chat:
        return

    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Admin"

    if await database.is_admin(user_id):
        await update.effective_chat.send_message(
            text=ADMIN_PANEL_HEADER,
            reply_markup=get_admin_main_menu(),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.effective_chat.send_message(
            text=USER_WELCOME_MSG,
            parse_mode=ParseMode.HTML
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /help command."""
    if not update.effective_user or not update.effective_chat:
        return

    user_id = update.effective_user.id
    if await database.is_admin(user_id):
        await update.effective_chat.send_message(
            text=ADMIN_HELP_MSG,
            parse_mode=ParseMode.HTML
        )
    else:
        await update.effective_chat.send_message(
            text=USER_WELCOME_MSG,
            parse_mode=ParseMode.HTML
        )
