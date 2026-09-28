"""
MedQuiz AI - Duplicate Prevention Service
Checks exact question hash and lexical similarity against existing questions in the database.
"""

from typing import Tuple, List
import database
from utils.helpers import generate_question_hash, calculate_similarity
from utils.logger import logger

SIMILARITY_THRESHOLD = 0.85


async def is_duplicate_question(
    question: str,
    options: List[str]
) -> Tuple[bool, str, str]:
    """
    Checks if a question or near-duplicate question already exists in SQLite.
    Returns: (is_duplicate: bool, reason: str, question_hash: str)
    """
    q_hash = generate_question_hash(question, options)

    # 1. Exact Hash Match
    existing = await database.get_question_by_hash(q_hash)
    if existing:
        logger.info(f"Duplicate detected: Exact hash match {q_hash}")
        return True, f"Exact duplicate question found (ID: {existing['id']})", q_hash

    # 2. Similarity Match with Recent Questions
    recent_questions = await database.get_recent_questions(limit=150)
    for prev in recent_questions:
        prev_text = prev.get("question", "")
        sim = calculate_similarity(question, prev_text)
        if sim >= SIMILARITY_THRESHOLD:
            logger.info(f"Near duplicate detected ({sim:.1%} match with question #{prev['id']})")
            return True, f"Near-duplicate question ({sim:.0%} match with ID {prev['id']})", q_hash

    return False, "", q_hash
