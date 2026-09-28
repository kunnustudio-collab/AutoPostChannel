# 🧠 MedQuiz AI — Production Telegram Bot

**MedQuiz AI** is a production-grade Telegram bot engineered for medical entrance exam aspirants and medical students. It automatically generates, factually audits, and broadcasts high-yield **NEET** and **MBBS** multiple-choice questions directly to Telegram channels and groups as **native Telegram Quiz Polls**.

---

## 🌟 Key Features

- 🧠 **Dual Curriculum Support:**
  - **NEET UG:** High-yield NCERT Biology, Physics, and Chemistry.
  - **MBBS (NEXT / FMGE / NEET-PG):** Clinical vignettes across 19 medical subjects (Anatomy, Pathology, Pharmacology, Surgery, Medicine, etc.).
- 📊 **Native Telegram Quiz Polls:**
  - 4 distinct options with exactly one correct answer.
  - Anonymous quiz polls (`is_anonymous=True`).
  - Pre-poll announcement banner and post-quiz educational explanation.
- 🔬 **Two-Stage Medical Verification:**
  - AI prompt engine strictly outputs structured JSON.
  - Automated second-pass verification audits question accuracy and flags ambiguous keys.
  - Automatic retries (up to 3 attempts) if questions are invalid.
- 🛡 **Duplicate Prevention:**
  - Deterministic SHA-256 normalized question and option hashing.
  - Fuzzy lexical similarity detection (>85% matching threshold) to avoid repetitive questions.
- ⏰ **Automated Scheduling Engine:**
  - Powered by APScheduler with timezone support (`Asia/Kolkata` IST).
  - Multi-schedule support (e.g. 09:00 NEET Biology, 13:00 NEET Chemistry, 18:00 MBBS Anatomy).
  - Pause, resume, edit, or delete schedules anytime via Telegram inline buttons.
- 📢 **Channel & Group Management:**
  - Automatic permission verification before saving destinations.
  - One-click diagnostic test broadcasts.
- ✍️ **Manual Quiz Creator:**
  - Create and publish custom questions without invoking AI.
- 🌐 **Multi-Language Support:**
  - English, Hindi, and Hinglish (conversational medical Hinglish).
- 📈 **Admin Analytics Dashboard:**
  - Live counts of generated questions, success rates, API usage, and destinations.

---

## 🏗 Project Architecture

```
NEET TG BOT/
├── bot.py                     # Main application entrypoint & handler wiring
├── config.py                  # Environment config & subject definitions
├── database.py                # Asynchronous SQLite database layer (aiosqlite)
├── scheduler.py               # APScheduler background posting engine
├── requirements.txt           # Project dependencies
├── .env.example               # Environment variables template
├── test_medquiz.py            # Comprehensive 20-point test suite
├── README.md                  # Complete documentation
│
├── ai/
│   ├── __init__.py
│   ├── base.py                # Abstract AIProvider interface
│   ├── openrouter.py          # OpenRouter & OpenAI client with fallback
│   └── validator.py           # Pydantic models & JSON extractor
│
├── handlers/
│   ├── __init__.py
│   ├── start.py               # /start, /help and authorization routing
│   ├── admin.py               # Admin dashboard, stats & question history
│   ├── quiz.py                # Interactive 5-step AI quiz wizard
│   ├── manual_quiz.py         # Step-by-step manual quiz builder
│   ├── channels.py            # Channel & group registration and tests
│   ├── schedules.py           # Auto-posting schedules management
│   └── settings.py            # AI model, temperature & formatting settings
│
├── services/
│   ├── __init__.py
│   ├── question_generator.py  # Prompt engine & generation retry loops
│   ├── question_validator.py  # Validation and 2nd-pass audit logic
│   ├── duplicate_checker.py   # Hash and similarity duplicate prevention
│   └── telegram_publisher.py  # Native Telegram Quiz Poll broadcaster
│
├── utils/
│   ├── __init__.py
│   ├── helpers.py             # Normalization, hashing & message formatters
│   ├── keyboards.py           # Telegram InlineKeyboardMarkup layouts
│   └── logger.py              # Rotating file (10MB) & console logger
│
├── data/                      # SQLite database storage (medquiz.db)
└── logs/                      # Application log files (bot.log)
```

---

## 🚀 Setup & Installation (Windows 10 / 11)

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.10 and 3.11).
- Make sure Python is added to your Windows PATH during installation.

### 2. Create Virtual Environment
Open PowerShell or Command Prompt inside the `NEET TG BOT` folder:

```powershell
# Create virtual environment
python -m venv venv

# Activate on Windows PowerShell:
.\venv\Scripts\Activate.ps1

# (Or in standard Command Prompt cmd.exe):
venv\Scripts\activate.bat
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

---

## ⚙️ Configuration (.env)

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Open `.env` in any text editor and fill in your credentials:

```ini
# Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz

# OpenRouter / OpenAI API Key (from https://openrouter.ai/keys)
AI_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxx

# Base URL (default is OpenRouter)
AI_BASE_URL=https://openrouter.ai/api/v1

# Preferred AI Model (supports free models!)
AI_MODEL=meta-llama/llama-3.1-8b-instruct:free

# Optional Fallback Model
AI_FALLBACK_MODEL=google/gemini-2.0-flash-lite:free

# Your numeric Telegram user ID (from @userinfobot)
ADMIN_IDS=123456789

# Default Preferences
DEFAULT_LANGUAGE=English
DEFAULT_DIFFICULTY=Medium
ENABLE_VERIFICATION=true
SEND_HEADER_POST=true
SEND_EXPLANATION_POST=true
```

### How to get credentials:
1. **Telegram Bot Token:**
   - Message `@BotFather` on Telegram.
   - Send `/newbot`, choose a name and username ending in `bot`.
   - Copy the HTTP API token.
2. **Numeric Telegram Admin ID:**
   - Message `@userinfobot` on Telegram.
   - It will reply with your numeric `Id` (e.g. `987654321`). Put this in `ADMIN_IDS`.
3. **OpenRouter API Key (Free models):**
   - Register at [OpenRouter.ai](https://openrouter.ai).
   - Go to **Keys** and create a key.
   - Free models like `meta-llama/llama-3.1-8b-instruct:free` or `google/gemini-2.0-flash-lite:free` require zero deposit.

---

## 🧪 Running the Tests

Verify all 20 subsystems with the automated test suite:

```powershell
python test_medquiz.py
```

---

## 🏃 Running the Bot

Start MedQuiz AI:

```powershell
python bot.py
```

You will see:
```
2026-09-28 05:25:00 | INFO | Database initialized successfully.
2026-09-28 05:25:01 | INFO | Loaded 0 schedules into background scheduler.
2026-09-28 05:25:01 | INFO | Quiz scheduler engine started.
🚀 MedQuiz AI is running! Press Ctrl+C to terminate.
```

---

## 📢 Connecting Channels & Groups

1. Add your bot to your target Telegram Channel or Group.
2. Promote the bot to **Administrator** with at least:
   - **Post Messages** (for channels) / **Send Polls** (for groups)
   - **Delete Messages** (optional, used for test verification cleanup)
3. In private chat with your bot, send `/admin` or `/channels`.
4. Click **➕ Add Channel / Group** and enter the channel username (e.g. `@MyMedQuizChannel`) or chat ID.
5. The bot will run an automated test post to verify permissions and register it.

---

## ⏰ Setting up Daily Auto-Posting

1. In the admin menu, click **⏰ Auto Posting**.
2. Click **➕ Add New Schedule**.
3. Follow the interactive wizard:
   - Select destination channel.
   - Select curriculum (`NEET` or `MBBS`).
   - Select subject (e.g. `Biology`, `Pathology`, or `Random`).
   - Select difficulty and language.
   - Enter post time in 24-hr IST (e.g. `09:00`, `13:00`, `18:00`).
4. The bot will automatically generate and broadcast quizzes at the specified time every day.

---

## 🛡 Security & Reliability

- **Admin Only:** Only numeric user IDs listed in `ADMIN_IDS` can generate quizzes, alter schedules, or configure destinations. Normal users receive a generic welcoming message.
- **Fail-Safe Scheduling:** Network timeouts or AI provider hiccups are caught gracefully, logged to `logs/bot.log`, and will never crash the bot or disrupt subsequent scheduled posts.
- **Rotating Logs:** Kept in `logs/bot.log` up to 10MB each with 5 automated backups.
