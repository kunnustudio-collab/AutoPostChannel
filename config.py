"""
MedQuiz AI - Configuration Module
Loads configuration from environment variables and defines application constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory paths
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Bot & Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "meta-llama/llama-3.1-8b-instruct:free").strip()
AI_FALLBACK_MODEL = os.getenv("AI_FALLBACK_MODEL", "").strip()

# AI Parameters
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.7"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "1000"))

# Admin IDs (Numeric Telegram User IDs)
_raw_admins = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS: list[int] = []
if _raw_admins:
    for aid in _raw_admins.split(","):
        aid = aid.strip()
        if aid.isdigit():
            ADMIN_IDS.append(int(aid))

# Default Quiz Settings
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "English").strip()
DEFAULT_DIFFICULTY = os.getenv("DEFAULT_DIFFICULTY", "Medium").strip()

# Feature Flags
ENABLE_VERIFICATION = os.getenv("ENABLE_VERIFICATION", "true").lower() in ("true", "1", "yes")
SEND_HEADER_POST = os.getenv("SEND_HEADER_POST", "true").lower() in ("true", "1", "yes")
SEND_EXPLANATION_POST = os.getenv("SEND_EXPLANATION_POST", "true").lower() in ("true", "1", "yes")

# Rate Limits
MAX_GENERATIONS_PER_HOUR = int(os.getenv("MAX_GENERATIONS_PER_HOUR", "60"))
MAX_GENERATIONS_PER_DAY = int(os.getenv("MAX_GENERATIONS_PER_DAY", "500"))

# Database & Logging paths
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "medquiz.db"

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "bot.log"

# Supported Categories & Standard Subject Presets
CATEGORIES = ["NEET", "MBBS"]

NEET_SUBJECTS: dict[str, list[str]] = {
    "Biology": [
        "Human Physiology",
        "Genetics & Evolution",
        "Cell Biology & Division",
        "Plant Physiology",
        "Ecology & Environment",
        "Biotechnology & Applications",
        "Human Reproduction & Health",
        "Structural Organisation in Animals & Plants",
        "Diversity in Living World"
    ],
    "Physics": [
        "Mechanics & Kinematics",
        "Laws of Motion & Gravitation",
        "Thermodynamics & Kinetic Theory",
        "Electrodynamics & Magnetism",
        "Optics & Wave Optics",
        "Modern Physics & Nuclear",
        "Oscillations & Waves",
        "Current Electricity"
    ],
    "Chemistry": [
        "Organic Chemistry - Reactions & Mechanisms",
        "Inorganic Chemistry - Chemical Bonding",
        "Physical Chemistry - Thermodynamics",
        "Equilibrium & Solutions",
        "Coordination Compounds",
        "Biomolecules & Polymers",
        "Electrochemistry & Kinetics",
        "Periodic Classification"
    ]
}

MBBS_SUBJECTS: dict[str, list[str]] = {
    "Anatomy": ["Gross Anatomy", "Embryology", "Histology", "Neuroanatomy"],
    "Physiology": ["Cardiovascular", "Respiratory", "Neurophysiology", "Endocrinology", "Renal"],
    "Biochemistry": ["Metabolism", "Molecular Biology", "Clinical Enzymology", "Vitamins & Minerals"],
    "Pathology": ["General Pathology", "Hematology", "Systemic Pathology", "Neoplasia"],
    "Pharmacology": ["Autonomic", "Cardiovascular", "Antimicrobials", "CNS Drugs", "Chemotherapy"],
    "Microbiology": ["Bacteriology", "Virology", "Parasitology", "Mycology", "Immunology"],
    "Forensic Medicine": ["Thanatology", "Toxicology", "Medical Jurisprudence"],
    "Community Medicine": ["Epidemiology", "Biostatistics", "Maternal & Child Health", "Nutrition"],
    "General Medicine": ["Cardiology", "Pulmonology", "Neurology", "Gastroenterology", "Infectious Diseases"],
    "General Surgery": ["Trauma & Critical Care", "GI Surgery", "Surgical Oncology", "Urology"],
    "Pediatrics": ["Neonatology", "Developmental Milestones", "Pediatric Infections", "Immunization"],
    "Obstetrics & Gynecology": ["Antenatal Care", "Labor & Delivery", "Gynecological Oncology", "Contraception"],
    "Orthopedics": ["Fractures & Dislocations", "Joint Diseases", "Bone Tumors", "Spine Disorders"],
    "ENT": ["Otology", "Rhinology", "Laryngology", "Head & Neck"],
    "Ophthalmology": ["Cataract & Glaucoma", "Retina & Vitreous", "Cornea", "Neuro-ophthalmology"],
    "Psychiatry": ["Mood Disorders", "Schizophrenia & Psychosis", "Substance Abuse", "Child Psychiatry"],
    "Dermatology": ["Infectious Dermatoses", "Papulosquamous Disorders", "Sexually Transmitted Infections"],
    "Radiology": ["X-Ray Interpretation", "CT & MRI Imaging", "Ultrasound", "Interventional Radiology"],
    "Anesthesiology": ["General Anesthesia", "Local & Regional Blocks", "Airway Management", "Resuscitation"]
}

DIFFICULTIES = ["🟢 Easy", "🟡 Medium", "🔴 Hard", "🎲 Random"]
DIFFICULTY_CLEAN_MAP = {
    "🟢 Easy": "Easy",
    "🟡 Medium": "Medium",
    "🔴 Hard": "Hard",
    "🎲 Random": "Random"
}

LANGUAGES = ["🇬🇧 English", "🇮🇳 Hindi", "🇮🇳 Hinglish"]
LANGUAGE_CLEAN_MAP = {
    "🇬🇧 English": "English",
    "🇮🇳 Hindi": "Hindi",
    "🇮🇳 Hinglish": "Hinglish"
}


def validate_config() -> tuple[bool, list[str]]:
    """Validates core configuration and returns status with missing items."""
    missing = []
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        missing.append("TELEGRAM_BOT_TOKEN is not configured in .env")
    if not AI_API_KEY or AI_API_KEY == "your_ai_api_key_here":
        missing.append("AI_API_KEY is not configured in .env")
    if not ADMIN_IDS:
        missing.append("ADMIN_IDS is empty. Add your numeric Telegram ID in .env")
    return len(missing) == 0, missing
