"""
User Profile Management.

Manages learner profiles, learning goals, vocabulary tracking,
and personalization for the speech guidance assistant.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class UserProfile:
    """Manages user learning profile and progress."""

    def __init__(self, user_id: str, profiles_dir: str = "./profiles"):
        self.user_id = user_id
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(exist_ok=True)
        self.profile_file = self.profiles_dir / f"{user_id}_profile.json"
        
        self.data = self._load_profile()

    def _load_profile(self) -> dict:
        """Load profile from disk or create new one."""
        if self.profile_file.exists():
            with open(self.profile_file, "r") as f:
                return json.load(f)
        
        return {
            "user_id": self.user_id,
            "created_at": datetime.now().isoformat(),
            "learning_goals": [],
            "level": "beginner",  # beginner, intermediate, advanced
            "target_language": "english",
            "vocabulary": {},  # word: {learned_at, difficulty, reviews, last_review, mastery_level}
            "speech_metrics": {
                "avg_pace_wpm": 0,
                "clarity_score": 0.0,
                "confidence_score": 0.0,
                "accent_notes": [],
            },
            "conversation_history": [],  # [{timestamp, transcript, suggestion, feedback}]
            "lesson_count": 0,
            "total_speaking_minutes": 0,
            "last_session": None,
        }

    def save(self):
        """Save profile to disk."""
        with open(self.profile_file, "w") as f:
            json.dump(self.data, f, indent=2)
        logger.info(f"Profile saved for user {self.user_id}")

    def set_learning_goal(self, goal: str, description: str = "", target_date: str = None):
        """Add a learning goal."""
        goal_obj = {
            "goal": goal,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "target_date": target_date,
            "status": "active",  # active, paused, completed
            "progress": 0,  # 0-100%
        }
        self.data["learning_goals"].append(goal_obj)
        self.save()
        logger.info(f"Goal '{goal}' added for user {self.user_id}")

    def set_level(self, level: str):
        """Set proficiency level: beginner, intermediate, advanced."""
        valid_levels = ["beginner", "intermediate", "advanced"]
        if level in valid_levels:
            self.data["level"] = level
            self.save()
            logger.info(f"Level set to {level} for user {self.user_id}")
        else:
            logger.warning(f"Invalid level {level}. Must be one of {valid_levels}")

    def add_vocabulary(self, word: str, definition: str, difficulty: str = "medium"):
        """Add or update vocabulary word."""
        self.data["vocabulary"][word.lower()] = {
            "definition": definition,
            "difficulty": difficulty,  # easy, medium, hard
            "learned_at": datetime.now().isoformat(),
            "reviews": 0,
            "last_review": None,
            "mastery_level": 0,  # 0-100%
        }
        self.save()

    def review_vocabulary(self, word: str, correct: bool):
        """Record a vocabulary review attempt."""
        word_lower = word.lower()
        if word_lower not in self.data["vocabulary"]:
            logger.warning(f"Word '{word}' not found in vocabulary")
            return
        
        vocab_entry = self.data["vocabulary"][word_lower]
        vocab_entry["last_review"] = datetime.now().isoformat()
        vocab_entry["reviews"] += 1
        
        if correct:
            vocab_entry["mastery_level"] = min(100, vocab_entry["mastery_level"] + 10)
        else:
            vocab_entry["mastery_level"] = max(0, vocab_entry["mastery_level"] - 5)
        
        self.save()
        logger.debug(f"Updated mastery for '{word}' to {vocab_entry['mastery_level']}%")

    def get_review_due_vocabulary(self, limit: int = 5) -> list[str]:
        """Get vocabulary words due for spaced repetition review."""
        now = datetime.now()
        due_words = []
        
        for word, entry in self.data["vocabulary"].items():
            if entry["mastery_level"] >= 100:
                continue  # Skip fully mastered words
            
            last_review = entry["last_review"]
            if last_review is None:
                due_words.append(word)
            else:
                last_review_dt = datetime.fromisoformat(last_review)
                # Spaced repetition: review when days = mastery_level / 20
                days_until_review = max(1, 30 - (entry["mastery_level"] // 5))
                review_due_date = last_review_dt + timedelta(days=days_until_review)
                
                if now >= review_due_date:
                    due_words.append(word)
        
        return due_words[:limit]

    def add_conversation_entry(self, transcript: str, suggestion: str, feedback: str = ""):
        """Record a conversation turn."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "transcript": transcript,
            "suggestion": suggestion,
            "feedback": feedback,
        }
        self.data["conversation_history"].append(entry)
        self.data["lesson_count"] += 1
        self.data["last_session"] = datetime.now().isoformat()
        self.save()

    def update_speech_metrics(self, metrics: dict):
        """Update speech analysis metrics (pace, clarity, confidence)."""
        for key, value in metrics.items():
            if key in self.data["speech_metrics"]:
                if isinstance(value, list):
                    # For accent notes, append
                    if key == "accent_notes":
                        self.data["speech_metrics"][key].extend(value)
                else:
                    # For numeric metrics, update (simple average)
                    current = self.data["speech_metrics"][key]
                    if isinstance(current, (int, float)):
                        self.data["speech_metrics"][key] = (current + value) / 2
                    else:
                        self.data["speech_metrics"][key] = value
        self.save()

    def get_profile_summary(self) -> dict:
        """Return a summary for personalization."""
        return {
            "level": self.data["level"],
            "learning_goals": [g["goal"] for g in self.data["learning_goals"] if g["status"] == "active"],
            "target_language": self.data["target_language"],
            "vocabulary_count": len(self.data["vocabulary"]),
            "lesson_count": self.data["lesson_count"],
            "speech_metrics": self.data["speech_metrics"],
        }

    def get_context_for_ai(self) -> str:
        """Generate a context string for AI personalization."""
        summary = self.get_profile_summary()
        goals = ", ".join(summary["learning_goals"]) if summary["learning_goals"] else "general improvement"
        
        context = (
            f"The learner is at {summary['level']} level. "
            f"Learning goals: {goals}. "
            f"Vocabulary learned: {summary['vocabulary_count']} words. "
            f"Sessions completed: {summary['lesson_count"]}. "
            f"Recent speech clarity: {summary['speech_metrics']['clarity_score']:.1%}."
        )
        return context
