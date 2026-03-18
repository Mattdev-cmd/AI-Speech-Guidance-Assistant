"""
Integration Example: Using Enhanced AI Speech Guidance Features

This example shows how to integrate the new personalization,
speech analysis, and learning features into your speech guidance assistant.
"""

from modules.user_profile import UserProfile
from modules.ai_engine import AIResponseEngine
from modules.speech_analyzer import SpeechAnalyzer
from modules.learning_analytics import LearningAnalytics
import yaml


def setup_learner_session(user_id: str, config_path: str = "config.yaml"):
    """Initialize a personalized learning session."""
    
    # Load configuration
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # 1. Load or create user profile
    profile = UserProfile(user_id)
    
    # 2. Initialize AI engine with personalization
    ai_engine = AIResponseEngine(config, user_profile=profile)
    
    # 3. Initialize speech analyzer for real-time feedback
    speech_analyzer = SpeechAnalyzer()
    
    # 4. Initialize learning analytics for progress tracking
    analytics = LearningAnalytics(profile)
    
    return {
        "profile": profile,
        "ai_engine": ai_engine,
        "speech_analyzer": speech_analyzer,
        "analytics": analytics
    }


def process_speech_turn(
    transcript: str,
    audio_duration: float,
    session: dict,
    scene_description: str = None,
) -> dict:
    """Process a single speech turn with all enhancements.
    
    Args:
        transcript: The transcribed speech from the user
        audio_duration: Duration of the audio in seconds
        session: Session dict from setup_learner_session()
        scene_description: Optional scene context from camera
    
    Returns:
        Comprehensive response with suggestions, feedback, and learning insights
    """
    
    profile = session["profile"]
    ai_engine = session["ai_engine"]
    speech_analyzer = session["speech_analyzer"]
    analytics = session["analytics"]
    
    # 1. Analyze speech quality
    speech_metrics = speech_analyzer.analyze_transcript(transcript, audio_duration)
    
    # 2. Generate goal-tailored suggestions
    suggestions = ai_engine.generate_goal_tailored_suggestions(
        transcript, 
        scene_description
    )
    
    # 3. Generate combined (suggestions + learning insights)
    response, insights = ai_engine.generate_combined(
        transcript, 
        scene_description
    )
    
    # 4. Update user profile with this interaction
    profile.add_conversation_entry(
        transcript=transcript,
        suggestion=suggestions.get("suggestions", [""])[0],
        feedback=speech_metrics.get("feedback", [""])[0]
    )
    
    # 5. Update speech metrics
    profile.update_speech_metrics({
        "clarity_score": speech_metrics["clarity_score"],
        "confidence_score": speech_analyzer._estimate_confidence(transcript),
        "avg_pace_wpm": speech_metrics["pace_wpm"]
    })
    
    # 6. Add vocabulary from insights
    for vocab_item in insights.get("vocabulary", []):
        if "term" in vocab_item and "definition" in vocab_item:
            profile.add_vocabulary(
                vocab_item["term"],
                vocab_item["definition"],
                difficulty="medium"
            )
    
    # 7. Compile full response
    full_response = {
        "summary": response.get("summary", ""),
        "suggestions": response.get("suggestions", []),
        "guidance": response.get("guidance", ""),
        "goal_alignment": suggestions.get("goal_alignment", ""),
        
        # Speech feedback
        "speech_feedback": {
            "clarity": f"{speech_metrics['clarity_score']:.0%}",
            "pace_wpm": f"{speech_metrics['pace_wpm']:.0f}",
            "confidence": f"{speech_metrics['confidence']:.0%}",
            "suggestions": speech_metrics.get("feedback", []),
        },
        
        # Learning insights
        "learning_insights": {
            "vocabulary": insights.get("vocabulary", []),
            "topic_note": insights.get("topic_note", ""),
            "follow_up_questions": insights.get("follow_up_questions", []),
        },
        
        # Progress information
        "progress": {
            "lesson_count": profile.data["lesson_count"],
            "vocab_learned": len(profile.data["vocabulary"]),
        }
    }
    
    return full_response


def setup_learning_goal(session: dict, goal: str, description: str = ""):
    """Help learner set a specific learning goal."""
    profile = session["profile"]
    profile.set_learning_goal(goal, description)
    print(f"✅ Goal set: {goal}")


def check_vocabulary_due_for_review(session: dict, limit: int = 5) -> list:
    """Get vocabulary words due for spaced repetition review."""
    profile = session["profile"]
    due_words = profile.get_review_due_vocabulary(limit)
    return due_words


def do_vocabulary_exercise(session: dict, word: str = None) -> dict:
    """Generate and run an interactive vocabulary exercise."""
    ai_engine = session["ai_engine"]
    exercise = ai_engine.generate_vocabulary_exercise(word)
    return exercise


def record_vocabulary_review(session: dict, word: str, correct: bool):
    """Record whether learner got vocabulary review correct."""
    profile = session["profile"]
    profile.review_vocabulary(word, correct)


def show_progress_report(session: dict):
    """Display detailed learning progress report."""
    analytics = session["analytics"]
    report = analytics.get_progress_report()
    print(report)


def get_learning_recommendation(session: dict) -> str:
    """Get AI recommendation for next learning activity."""
    analytics = session["analytics"]
    return analytics.suggest_next_lesson_focus()


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import json
    
    # Initialize session for a learner
    print("🎓 Initializing AI Speech Guidance System with Enhancements...")
    session = setup_learner_session("learner_001")
    
    # Set learning goal
    print("\n📍 Setting Learning Goals...")
    setup_learning_goal(
        session,
        "Improve English conversation fluency",
        "Focus on speaking naturally in professional settings"
    )
    
    # Simulate a speech turn
    print("\n🎤 Processing Speech Turn...")
    transcript = "Um, I think, like, the most important thing is to, uh, maintain good communication with your team."
    audio_duration = 8.5  # 8.5 seconds
    
    result = process_speech_turn(
        transcript,
        audio_duration,
        session,
        scene_description="Person speaking in a conference room"
    )
    
    print("\n📋 Response Generated:")
    print(f"Summary: {result['summary']}")
    print(f"Suggestions:")
    for i, sugg in enumerate(result['suggestions'], 1):
        print(f"  {i}. {sugg}")
    
    print(f"\n🗣️ Speech Feedback:")
    for key, value in result["speech_feedback"].items():
        if key != "suggestions":
            print(f"  {key}: {value}")
    
    if result["speech_feedback"]["suggestions"]:
        print("  Improvement areas:")
        for suggestion in result["speech_feedback"]["suggestions"]:
            print(f"    - {suggestion}")
    
    print(f"\n💡 Learning Insights:")
    for vocab in result["learning_insights"]["vocabulary"]:
        print(f"  • {vocab['term']}: {vocab['definition']}")
    
    if result["learning_insights"]["follow_up_questions"]:
        print("  Follow-up questions:")
        for q in result["learning_insights"]["follow_up_questions"]:
            print(f"    • {q}")
    
    # Show progress
    print("\n📊 Progress Report:")
    show_progress_report(session)
    
    # Get recommendation
    print("\n🎯 Next Steps:")
    recommendation = get_learning_recommendation(session)
    print(f"  {recommendation}")
    
    # Check vocabulary due for review
    print("\n📚 Vocabulary Review Due:")
    due_words = check_vocabulary_due_for_review(session, limit=3)
    if due_words:
        for word in due_words:
            print(f"  • {word}")
            # Generate exercise for first word
            if word == due_words[0]:
                exercise = do_vocabulary_exercise(session, word)
                print(f"\n    Exercise for '{word}':")
                print(f"    Definition: {exercise.get('definition', 'N/A')}")
                if exercise.get('usage_examples'):
                    print(f"    Usage: {exercise['usage_examples'][0]}")
                print(f"    Quiz: {exercise.get('quiz', 'N/A')}")
    else:
        print("  No vocabulary words due for review right now!")
    
    print("\n✅ Session complete!")
