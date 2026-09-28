"""
MedQuiz AI - Helper Functions
Provides hashing, similarity computation, text truncation, and message formatting.
"""

import re
import hashlib
from difflib import SequenceMatcher
from typing import Sequence

OPTION_LETTERS = ["A", "B", "C", "D"]


def normalize_text(text: str) -> str:
    """Normalizes text by lowercasing, removing non-alphanumeric chars, and stripping whitespace."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def generate_question_hash(question: str, options: Sequence[str]) -> str:
    """
    Computes a deterministic SHA-256 hash from normalized question and sorted options.
    Ensures identical questions with reordered options are flagged as duplicates.
    """
    norm_q = normalize_text(question)
    norm_opts = sorted([normalize_text(opt) for opt in options])
    combined = f"{norm_q}:::{'|'.join(norm_opts)}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculates string similarity ratio between 0.0 and 1.0."""
    return SequenceMatcher(None, normalize_text(text1), normalize_text(text2)).ratio()


def truncate_text(text: str, max_len: int = 300) -> str:
    """Safely truncates text to fit within maximum allowed character limit."""
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def format_header_message(
    category: str,
    subject: str,
    topic: str,
    difficulty: str,
    quiz_number: int = 1
) -> str:
    """Formats the introductory banner message sent right before the quiz poll."""
    topic_str = f" | {topic}" if topic and topic != "Random" else ""
    return (
        f"🧠 <b>{category} DAILY QUIZ #{quiz_number:03d}</b>\n"
        f"📚 <b>{subject}</b>{topic_str}\n"
        f"🔥 Difficulty: <b>{difficulty}</b>"
    )


def format_explanation_message(explanation: str, correct_letter: str = "", correct_text: str = "") -> str:
    """Formats the educational explanation sent after users or as an accompaniment."""
    correct_info = f"<b>Answer:</b> {correct_letter}) {correct_text}\n\n" if correct_letter and correct_text else ""
    return (
        f"📖 <b>Explanation:</b>\n"
        f"{correct_info}"
        f"{explanation.strip()}"
    )


def format_preview_message(
    category: str,
    subject: str,
    topic: str,
    difficulty: str,
    language: str,
    question: str,
    options: list[str],
    correct_option: int,
    explanation: str
) -> str:
    """Formats a full preview for manual admin review before broadcasting."""
    correct_letter = OPTION_LETTERS[correct_option] if 0 <= correct_option < 4 else "?"

    opts_str = "\n".join([
        f"  <b>{OPTION_LETTERS[i]})</b> {opt}{'  ✅' if i == correct_option else ''}"
        for i, opt in enumerate(options)
    ])

    return (
        f"🧠 <b>QUIZ PREVIEW</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 <b>Category:</b> {category} | <b>Subject:</b> {subject}\n"
        f"📌 <b>Topic:</b> {topic}\n"
        f"🎯 <b>Difficulty:</b> {difficulty} | 🌐 <b>Language:</b> {language}\n\n"
        f"❓ <b>Question:</b>\n{question}\n\n"
        f"<b>Options:</b>\n{opts_str}\n\n"
        f"✅ <b>Correct Answer:</b> Option {correct_letter}\n\n"
        f"📖 <b>Explanation:</b>\n{explanation}\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
