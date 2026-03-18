"""
Real-time Speech Analysis.

Provides feedback on pace, clarity, filler words, and speech quality.
"""

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)


class SpeechAnalyzer:
    """Analyzes speech transcripts for quality metrics."""

    # Common filler words
    FILLER_WORDS = {
        "um", "uh", "like", "you know", "so", "basically", "actually", 
        "literally", "just", "right", "okay", "well", "i mean", "anyway"
    }
    
    # Emphasis markers (words that show confidence)
    EMPHASIS_WORDS = {
        "definitely", "absolutely", "certainly", "clearly", "obviously",
        "importantly", "significantly", "crucial", "essential", "critical"
    }

    def __init__(self):
        self.avg_speech_duration = 0  # seconds
        self.word_count_history = []

    def analyze_transcript(self, transcript: str, audio_duration: float = None) -> dict:
        """Analyze a transcript and return quality metrics.
        
        Args:
            transcript: The transcribed speech text
            audio_duration: Duration of audio in seconds (for pace calculation)
        
        Returns:
            Dictionary with metrics:
              - clarity_score (0.0-1.0): Based on sentence structure, punctuation
              - pace_wpm: Words per minute (if audio_duration provided)
              - filler_percentage: % of speech that is fillers
              - confidence: Estimated confidence level
              - feedback: List of actionable suggestions
              - vocabulary_diversity: Unique word ratio
        """
        if not transcript.strip():
            return {
                "clarity_score": 0.0,
                "pace_wpm": 0,
                "filler_percentage": 0.0,
                "confidence": 0.0,
                "feedback": [],
                "vocabulary_diversity": 0.0,
                "word_count": 0,
            }

        metrics = {}
        
        # 1. Clarity Score
        metrics["clarity_score"] = self._calculate_clarity(transcript)
        
        # 2. Pace (WPM)
        metrics["word_count"] = len(transcript.split())
        if audio_duration and audio_duration > 0:
            metrics["pace_wpm"] = (metrics["word_count"] / audio_duration) * 60
        else:
            metrics["pace_wpm"] = 0
        
        # 3. Filler Words
        metrics["filler_percentage"] = self._calculate_filler_percentage(transcript)
        
        # 4. Confidence
        metrics["confidence"] = self._estimate_confidence(transcript)
        
        # 5. Vocabulary Diversity
        metrics["vocabulary_diversity"] = self._calculate_vocabulary_diversity(transcript)
        
        # 6. Generate Feedback
        metrics["feedback"] = self._generate_feedback(metrics, transcript)
        
        return metrics

    def _calculate_clarity(self, transcript: str) -> float:
        """Estimate clarity based on sentence structure and length."""
        sentences = re.split(r'[.!?]', transcript)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return 0.5
        
        # Average sentence length (optimal: 8-15 words)
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
        length_score = 1.0 - abs(avg_sentence_length - 12) / 20
        length_score = max(0.0, min(1.0, length_score))
        
        # Sentence count (more sentences = more structure)
        sentence_score = min(1.0, len(sentences) / 5)
        
        # Capital usage (proper capitalization)
        capitals = sum(1 for c in transcript if c.isupper())
        capital_ratio = capitals / len(transcript) if transcript else 0
        capital_score = min(1.0, capital_ratio / 0.1)
        
        clarity = (length_score * 0.5 + sentence_score * 0.3 + capital_score * 0.2)
        return max(0.0, min(1.0, clarity))

    def _calculate_filler_percentage(self, transcript: str) -> float:
        """Calculate percentage of transcript that is filler words."""
        words = transcript.lower().split()
        
        filler_count = 0
        for filler in self.FILLER_WORDS:
            filler_count += transcript.lower().count(filler)
        
        return (filler_count / len(words)) * 100 if words else 0.0

    def _estimate_confidence(self, transcript: str) -> float:
        """Estimate confidence based on language markers."""
        lower_text = transcript.lower()
        
        # Positive markers
        emphasis_count = sum(1 for word in self.EMPHASIS_WORDS if word in lower_text)
        question_count = transcript.count('?')
        
        # Negative markers (hedging)
        hedges = ["maybe", "might", "could", "perhaps", "seem", "sort of", "kind of"]
        hedge_count = sum(1 for hedge in hedges if hedge in lower_text)
        
        words = transcript.split()
        word_count = len(words)
        
        confidence = 0.5  # baseline
        if word_count > 0:
            confidence += (emphasis_count * 0.05) - (hedge_count * 0.03) - (question_count * 0.02)
        
        return max(0.0, min(1.0, confidence))

    def _calculate_vocabulary_diversity(self, transcript: str) -> float:
        """Calculate type-token ratio (unique words / total words)."""
        words = transcript.lower().split()
        if not words:
            return 0.0
        
        unique_words = len(set(words))
        return unique_words / len(words)

    def _generate_feedback(self, metrics: dict, transcript: str) -> list[str]:
        """Generate actionable feedback based on metrics."""
        feedback = []
        
        # Clarity feedback
        if metrics["clarity_score"] < 0.6:
            feedback.append("Try breaking thoughts into shorter, clearer sentences.")
        
        # Pace feedback
        pace = metrics["pace_wpm"]
        if 0 < pace < 100:
            feedback.append("You're speaking slowly. Try increasing your pace slightly.")
        elif pace > 180:
            feedback.append("You're speaking quickly. Slow down a bit for clarity.")
        
        # Filler words
        if metrics["filler_percentage"] > 10:
            feedback.append(f"Reduce filler words (um, uh, like). You used {metrics['filler_percentage']:.1f}%.")
        
        # Confidence
        if metrics["confidence"] < 0.5:
            feedback.append("Use more assertive language to sound more confident.")
        
        # Vocabulary diversity
        if metrics["vocabulary_diversity"] < 0.4:
            feedback.append("Expand your vocabulary. Try using different words instead of repeating.")
        
        return feedback

    def get_speech_report(self, transcript: str, audio_duration: float = None) -> str:
        """Generate a human-readable speech report."""
        metrics = self.analyze_transcript(transcript, audio_duration)
        
        report = (
            f"📊 Speech Analysis Report\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Clarity:         {metrics['clarity_score']:.0%}\n"
            f"Pace:            {metrics['pace_wpm']:.0f} WPM\n"
            f"Confidence:      {metrics['confidence']:.0%}\n"
            f"Vocabulary:      {metrics['vocabulary_diversity']:.0%} diversity\n"
            f"Fillers:         {metrics['filler_percentage']:.1f}%\n\n"
        )
        
        if metrics["feedback"]:
            report += "💡 Suggestions:\n"
            for i, suggestion in enumerate(metrics["feedback"], 1):
                report += f"  {i}. {suggestion}\n"
        
        return report
