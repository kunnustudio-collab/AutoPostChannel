"""
MedQuiz AI - Keyboard Layouts
Builds all Telegram InlineKeyboardMarkup layouts for navigation and admin operations.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import CATEGORIES, NEET_SUBJECTS, MBBS_SUBJECTS, DIFFICULTIES, LANGUAGES


def get_admin_main_menu() -> InlineKeyboardMarkup:
    """Returns the main interactive admin dashboard keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🧠 Generate Quiz (AI)", callback_data="admin:gen_start"),
            InlineKeyboardButton("✍️ Manual Quiz", callback_data="admin:manual_quiz")
        ],
        [
            InlineKeyboardButton("📚 Subjects", callback_data="admin:subjects"),
            InlineKeyboardButton("🎯 Difficulty", callback_data="admin:difficulty")
        ],
        [
            InlineKeyboardButton("🌐 Language", callback_data="admin:language"),
            InlineKeyboardButton("⏰ Auto Posting", callback_data="admin:schedules")
        ],
        [
            InlineKeyboardButton("📢 Channels", callback_data="admin:channels"),
            InlineKeyboardButton("🤖 AI Settings", callback_data="admin:ai_settings")
        ],
        [
            InlineKeyboardButton("📊 Statistics", callback_data="admin:stats"),
            InlineKeyboardButton("📝 History", callback_data="admin:history_1")
        ],
        [
            InlineKeyboardButton("⚙️ Bot Settings", callback_data="admin:bot_settings")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_category_keyboard(prefix: str = "gen_cat") -> InlineKeyboardMarkup:
    """Returns Category selection buttons (NEET / MBBS)."""
    keyboard = [
        [
            InlineKeyboardButton("🧠 NEET", callback_data=f"{prefix}:NEET"),
            InlineKeyboardButton("🩺 MBBS", callback_data=f"{prefix}:MBBS")
        ],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="admin:back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_subjects_keyboard(
    category: str,
    prefix: str = "gen_sub",
    include_random: bool = True
) -> InlineKeyboardMarkup:
    """Returns list of subjects for NEET or MBBS."""
    subjects = list(NEET_SUBJECTS.keys()) if category == "NEET" else list(MBBS_SUBJECTS.keys())

    keyboard = []
    if include_random:
        keyboard.append([InlineKeyboardButton("🎲 Any / Random Subject", callback_data=f"{prefix}:Random")])

    # Grid of 2 columns
    row = []
    for sub in subjects:
        # Shorten callback data if needed
        row.append(InlineKeyboardButton(sub, callback_data=f"{prefix}:{sub[:25]}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"{prefix}:_back")])
    return InlineKeyboardMarkup(keyboard)


def get_topics_keyboard(
    category: str,
    subject: str,
    prefix: str = "gen_top"
) -> InlineKeyboardMarkup:
    """Returns preset topics for a subject or allows Random/Custom."""
    topics = []
    if category == "NEET" and subject in NEET_SUBJECTS:
        topics = NEET_SUBJECTS[subject]
    elif category == "MBBS" and subject in MBBS_SUBJECTS:
        topics = MBBS_SUBJECTS[subject]

    keyboard = [
        [InlineKeyboardButton("🎲 Any / Random Topic", callback_data=f"{prefix}:Random")]
    ]

    for top in topics:
        keyboard.append([InlineKeyboardButton(top, callback_data=f"{prefix}:{top[:30]}")])

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"{prefix}:_back")])
    return InlineKeyboardMarkup(keyboard)


def get_difficulty_keyboard(prefix: str = "gen_diff") -> InlineKeyboardMarkup:
    """Returns Difficulty selection buttons."""
    keyboard = [
        [
            InlineKeyboardButton("🟢 Easy", callback_data=f"{prefix}:Easy"),
            InlineKeyboardButton("🟡 Medium", callback_data=f"{prefix}:Medium")
        ],
        [
            InlineKeyboardButton("🔴 Hard", callback_data=f"{prefix}:Hard"),
            InlineKeyboardButton("🎲 Random", callback_data=f"{prefix}:Random")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data=f"{prefix}:_back")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_language_keyboard(prefix: str = "gen_lang") -> InlineKeyboardMarkup:
    """Returns Language selection buttons."""
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data=f"{prefix}:English")],
        [InlineKeyboardButton("🇮🇳 Hindi", callback_data=f"{prefix}:Hindi")],
        [InlineKeyboardButton("🇮🇳 Hinglish", callback_data=f"{prefix}:Hinglish")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"{prefix}:_back")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_quiz_preview_keyboard(question_id: int) -> InlineKeyboardMarkup:
    """Buttons displayed under question preview for publishing decisions."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Publish Now", callback_data=f"publish_sel:{question_id}"),
            InlineKeyboardButton("🔄 Regenerate", callback_data=f"regen:{question_id}")
        ],
        [
            InlineKeyboardButton("❌ Discard", callback_data=f"discard:{question_id}"),
            InlineKeyboardButton("🔙 Admin Menu", callback_data="admin:back_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_destination_select_keyboard(
    destinations: list[dict],
    question_id: int
) -> InlineKeyboardMarkup:
    """Allows admin to select which destination to broadcast to."""
    keyboard = []
    if len(destinations) > 1:
        keyboard.append([
            InlineKeyboardButton("📢 All Active Destinations", callback_data=f"send_to:all:{question_id}")
        ])

    for d in destinations:
        icon = "📢" if d["type"] == "channel" else "👥"
        keyboard.append([
            InlineKeyboardButton(f"{icon} {d['title']}", callback_data=f"send_to:{d['id']}:{question_id}")
        ])

    keyboard.append([InlineKeyboardButton("🔙 Back to Preview", callback_data=f"preview_back:{question_id}")])
    return InlineKeyboardMarkup(keyboard)


def get_channels_menu(destinations: list[dict]) -> InlineKeyboardMarkup:
    """Management view for channels/groups."""
    keyboard = [
        [InlineKeyboardButton("➕ Add Channel / Group", callback_data="chan:add")],
        [InlineKeyboardButton("🧪 Test Broadcast", callback_data="chan:test")]
    ]

    for d in destinations:
        state_icon = "🟢" if d["enabled"] else "🔴"
        dest_icon = "📢" if d["type"] == "channel" else "👥"
        title = d["title"][:20]
        keyboard.append([
            InlineKeyboardButton(f"{state_icon} {dest_icon} {title}", callback_data=f"chan:view:{d['id']}"),
            InlineKeyboardButton("🗑 Remove", callback_data=f"chan:del:{d['id']}")
        ])

    keyboard.append([InlineKeyboardButton("🔙 Back to Admin", callback_data="admin:back_main")])
    return InlineKeyboardMarkup(keyboard)


def get_schedules_menu(schedules: list[dict]) -> InlineKeyboardMarkup:
    """Management view for schedules."""
    keyboard = [
        [InlineKeyboardButton("➕ Add New Schedule", callback_data="sched:add")]
    ]

    for s in schedules:
        state_icon = "▶️" if s["enabled"] else "⏸"
        toggle_label = "Pause" if s["enabled"] else "Resume"
        time_str = s["post_time"]
        cat_str = s["category"]
        sub_str = s["subject"][:12]
        keyboard.append([
            InlineKeyboardButton(f"{state_icon} {time_str} - {cat_str} {sub_str}", callback_data=f"sched:view:{s['id']}"),
            InlineKeyboardButton(f"{toggle_label}", callback_data=f"sched:toggle:{s['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"sched:del:{s['id']}")
        ])

    keyboard.append([InlineKeyboardButton("🔙 Back to Admin", callback_data="admin:back_main")])
    return InlineKeyboardMarkup(keyboard)


def get_ai_settings_keyboard(
    current_model: str,
    current_temp: str,
    verification: str
) -> InlineKeyboardMarkup:
    """Inline settings for AI engine."""
    v_icon = "✅ Enabled" if verification == "true" else "❌ Disabled"
    keyboard = [
        [InlineKeyboardButton(f"🤖 Model: {current_model[:22]}", callback_data="ai_set:model")],
        [InlineKeyboardButton(f"🌡 Temperature: {current_temp}", callback_data="ai_set:temp")],
        [InlineKeyboardButton(f"🔬 2nd Pass Verification: {v_icon}", callback_data="ai_set:toggle_verif")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="admin:back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_bot_settings_keyboard(
    send_header: str,
    send_explanation: str,
    default_lang: str,
    default_diff: str
) -> InlineKeyboardMarkup:
    """Inline settings for Bot messaging behaviors."""
    h_icon = "✅" if send_header == "true" else "❌"
    e_icon = "✅" if send_explanation == "true" else "❌"
    keyboard = [
        [InlineKeyboardButton(f"Header Banner: {h_icon}", callback_data="bot_set:toggle_header")],
        [InlineKeyboardButton(f"Post-Quiz Explanation: {e_icon}", callback_data="bot_set:toggle_expl")],
        [InlineKeyboardButton(f"🌐 Default Lang: {default_lang}", callback_data="bot_set:lang")],
        [InlineKeyboardButton(f"🎯 Default Diff: {default_diff}", callback_data="bot_set:diff")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="admin:back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_history_pagination_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Pagination buttons for browsing question history."""
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"admin:history_{page - 1}"))
    buttons.append(InlineKeyboardButton(f"{page}/{max(1, total_pages)}", callback_data="noop"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"admin:history_{page + 1}"))

    keyboard = [
        buttons,
        [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin:back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)
