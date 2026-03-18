"""
Learning Analytics and Progress Tracking.

Tracks learning progress, calculates metrics, and provides insights
on vocabulary mastery, speech improvement, and lesson engagement.
"""

import logging
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class LearningAnalytics:
    """Analyzes learner progress and generates insights."""

    def __init__(self, user_profile):
        self.profile = user_profile

    def calculate_vocabulary_mastery(self) -> dict:
        """Calculate overall vocabulary mastery statistics."""
        vocab = self.profile.data["vocabulary"]
        
        if not vocab:
            return {
                "total_words": 0,
                "mastered": 0,
                "in_progress": 0,
                "new": 0,
                "avg_mastery": 0.0,
                "mastery_by_difficulty": {}
            }
        
        mastered = sum(1 for v in vocab.values() if v["mastery_level"] >= 80)
        in_progress = sum(1 for v in vocab.values() if 20 <= v["mastery_level"] < 80)
        new = sum(1 for v in vocab.values() if v["mastery_level"] < 20)
        avg_mastery = sum(v["mastery_level"] for v in vocab.values()) / len(vocab)
        
        # By difficulty
        by_difficulty = defaultdict(lambda: {"total": 0, "avg_mastery": 0})
        for word, entry in vocab.items():
            diff = entry["difficulty"]
            by_difficulty[diff]["total"] += 1
            by_difficulty[diff]["avg_mastery"] += entry["mastery_level"]
        
        for diff in by_difficulty:
            by_difficulty[diff]["avg_mastery"] /= by_difficulty[diff]["total"]
        
        return {
            "total_words": len(vocab),
            "mastered": mastered,
            "in_progress": in_progress,
            "new": new,
            "avg_mastery": avg_mastery,
            "mastery_by_difficulty": dict(by_difficulty)
        }

    def calculate_speech_improvement(self) -> dict:
        """Calculate speech metric trends over time."""
        metrics = self.profile.data["speech_metrics"]
        history = self.profile.data["conversation_history"]
        
        if not history:
            return {
                "clarity_trend": 0.0,
                "pace_trend": 0.0,
                "confidence_trend": 0.0,
                "lessons_with_feedback": 0
            }
        
        # In production, you'd track metrics per lesson. For now, use latest.
        return {
            "current_clarity": metrics.get("clarity_score", 0.0),
            "current_pace": metrics.get("avg_pace_wpm", 0),
            "current_confidence": metrics.get("confidence_score", 0.0),
            "total_lessons": len(history),
            "recommended_focus": self._get_recommended_focus(metrics)
        }

    def _get_recommended_focus(self, metrics: dict) -> str:
        """Suggest a focus area based on weakest metric."""
        clarity = metrics.get("clarity_score", 0.5)
        confidence = metrics.get("confidence_score", 0.5)
        
        if clarity < 0.6:
            return "Focus on sentence structure and clarity"
        elif confidence < 0.5:
            return "Build confidence through assertive language"
        else:
            return "Continue improving vocabulary and pace"

    def get_progress_report(self) -> str:
        """Generate a human-readable progress report."""
        vocab_stats = self.calculate_vocabulary_mastery()
        speech_stats = self.calculate_speech_improvement()
        profile_summary = self.profile.get_profile_summary()
        
        report = (
            "📚 Learning Progress Report\n"
            "═════════════════════════════════════════\n\n"
            f"📖 Vocabulary:\n"
            f"  Total words learned: {vocab_stats['total_words']}\n"
            f"  Mastered: {vocab_stats['mastered']} ({vocab_stats['mastered']/max(1, vocab_stats['total_words'])*100:.0f}%)\n"
            f"  In progress: {vocab_stats['in_progress']}\n"
            f"  Average mastery: {vocab_stats['avg_mastery']:.0f}%\n\n"
            f"🗣️ Speech Proficiency:\n"
            f"  Lessons completed: {profile_summary['lesson_count']}\n"
            f"  Clarity score: {speech_stats['current_clarity']:.0%}\n"
            f"  Confidence: {speech_stats['current_confidence']:.0%}\n"
            f"  Current pace: {speech_stats['current_pace']:.0f} WPM\n\n"
            f"💡 Recommendation:\n"
            f"  {speech_stats['recommended_focus']}\n\n"
            f"🎯 Active Goals:\n"
        )
        
        if profile_summary["learning_goals"]:
            for goal in profile_summary["learning_goals"]:
                report += f"  • {goal}\n"
        else:
            report += "  No active goals yet. Set goals to guide your learning!\n"
        
        return report

    def suggest_next_lesson_focus(self) -> str:
        """Suggest what to practice next based on progress."""
        vocab_stats = self.calculate_vocabulary_mastery()
        speech_stats = self.calculate_speech_improvement()
        
        # Suggest vocabulary exercise if due words exist
        due_words = self.profile.get_review_due_vocabulary(limit=3)
        if due_words:
            return f"Next: Review these vocabulary words: {', '.join(due_words)}"
        
        # Suggest speech improvement
        if speech_stats["current_clarity"] < 0.7:
            return "Next: Practice speaking in shorter, clearer sentences"
        
        if speech_stats["current_confidence"] < 0.6:
            return "Next: Work on using more confident language patterns"
        
        # Default: continue with goals
        goals = self.profile.get_profile_summary()["learning_goals"]
        if goals:
            return f"Next: Continue working towards: {goals[0]}"
        
        return "Next: Set a specific learning goal to focus your practice!"

    def export_analytics(self) -> dict:
        """Export comprehensive analytics for reporting/dashboards."""
        return {
            "timestamp": datetime.now().isoformat(),
            "user_id": self.profile.user_id,
            "profile_summary": self.profile.get_profile_summary(),
            "vocabulary_stats": self.calculate_vocabulary_mastery(),
            "speech_stats": self.calculate_speech_improvement(),
            "total_lessons": self.profile.data["lesson_count"],
            "total_speaking_minutes": self.profile.data["total_speaking_minutes"],
            "last_session": self.profile.data["last_session"],
        }
