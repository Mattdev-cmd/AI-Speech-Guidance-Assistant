# AI Speech Guidance System - Enhancement Guide

This guide explains the new **personalization**, **real-time feedback**, and **learning analytics** features added to your speech guidance assistant.

## What's New

Your system now includes four powerful enhancement modules:

1. **User Profiles** (`user_profile.py`) — Track learner data, goals, and vocabulary
2. **Speech Analysis** (`speech_analyzer.py`) — Real-time feedback on pace, clarity, confidence, and filler words
3. **Learning Analytics** (`learning_analytics.py`) — Progress tracking and personalized recommendations
4. **Enhanced AI Engine** — Personalized suggestions based on learner level and goals

---

## 1. User Profile System

### What It Does
- Creates persistent learner profiles with learning history
- Tracks vocabulary with mastery levels
- Records conversation history and speech metrics
- Implements spaced repetition for vocabulary review
- Stores learning goals and tracks progress

### Key Features

#### Setting Up a Profile
```python
from modules.user_profile import UserProfile

# Load or create profile for a learner
profile = UserProfile("john_doe")

# Set proficiency level (beginner, intermediate, advanced)
profile.set_level("beginner")

# Add learning goals
profile.set_learning_goal(
    "Improve English conversation fluency",
    "Focus on workplace communication"
)
```

#### Vocabulary Management
```python
# Add vocabulary word
profile.add_vocabulary(
    word="eloquent",
    definition="Fluent, persuasive speaking or writing",
    difficulty="medium"
)

# Track reviews (spaced repetition)
profile.review_vocabulary("eloquent", correct=True)  # Increases mastery
profile.review_vocabulary("eloquent", correct=False) # Decreases mastery

# Get words due for review
due_words = profile.get_review_due_vocabulary(limit=5)
# Returns words based on spaced repetition algorithm
```

#### Recording Conversations
```python
# After each interaction, record it
profile.add_conversation_entry(
    transcript="I want to improve my speaking skills",
    suggestion="Consider joining a conversation club",
    feedback="Good sentence structure!"
)
```

#### Accessing Profile Data
```python
# Get a summary for AI personalization
context = profile.get_context_for_ai()
# Returns: "The learner is at beginner level. Learning goals: workplace communication..."

# Get detailed summary
summary = profile.get_profile_summary()
# Returns: {level, learning_goals, vocabulary_count, speech_metrics, ...}
```

---

## 2. Real-Time Speech Analysis

### What It Does
- Analyzes transcripts for clarity, pace, confidence, and vocabulary diversity
- Detects filler words (um, uh, like, etc.)
- Generates actionable feedback suggestions
- Integrates with user profiles for metric tracking

### Key Metrics

| Metric | What It Measures | Optimal Range |
|--------|------------------|---------------|
| **Clarity (%)** | Sentence structure, punctuation quality | 70-100% |
| **Pace (WPM)** | Words per minute | 130-160 |
| **Confidence (%)** | Assertive language vs. hedging | 60-100% |
| **Filler (%)** | Um, uh, like, etc. | 0-5% |
| **Vocabulary Diversity** | Unique words used | 40-80% |

### Usage

#### Basic Analysis
```python
from modules.speech_analyzer import SpeechAnalyzer

analyzer = SpeechAnalyzer()

# Analyze a transcript
transcript = "Um, I think the most important thing is, like, having good communication in your team."
metrics = analyzer.analyze_transcript(transcript, audio_duration=5.0)

print(f"Clarity: {metrics['clarity_score']:.0%}")
print(f"Pace: {metrics['pace_wpm']:.0f} WPM")
print(f"Confidence: {metrics['confidence']:.0%}")
print(f"Fillers: {metrics['filler_percentage']:.1f}%")

# Get suggestions
for suggestion in metrics['feedback']:
    print(f"• {suggestion}")
```

#### Generate Speech Report
```python
report = analyzer.get_speech_report(transcript, audio_duration=5.0)
print(report)
# Outputs:
# 📊 Speech Analysis Report
# ━━━━━━━━━━━━━━━━━━━━━━━━
# Clarity:         65%
# Pace:            144 WPM
# Confidence:      55%
# Vocabulary:      42% diversity
# Fillers:         8.5%
#
# 💡 Suggestions:
#   1. Try breaking thoughts into shorter, clearer sentences.
#   2. Reduce filler words (um, uh, like). You used 8.5%.
#   3. Use more assertive language to sound more confident.
```

---

## 3. Learning Analytics

### What It Does
- Calculates vocabulary mastery statistics
- Tracks speech improvement trends
- Generates progress reports
- Provides personalized next-step recommendations

### Key Metrics

```python
from modules.learning_analytics import LearningAnalytics

analytics = LearningAnalytics(profile)

# Get vocabulary statistics
vocab_stats = analytics.calculate_vocabulary_mastery()
# Returns: {total_words, mastered, in_progress, new, avg_mastery, mastery_by_difficulty}

# Get speech improvement stats
speech_stats = analytics.calculate_speech_improvement()
# Returns: {current_clarity, current_pace, current_confidence, lessons_completed, recommended_focus}
```

### Usage Examples

#### Generate Progress Report
```python
report = analytics.get_progress_report()
print(report)
# Outputs:
# 📚 Learning Progress Report
# ═════════════════════════════════════════
# 
# 📖 Vocabulary:
#   Total words learned: 42
#   Mastered: 28 (67%)
#   In progress: 10
#   Average mastery: 74%
#
# 🗣️ Speech Proficiency:
#   Lessons completed: 15
#   Clarity score: 72%
#   Confidence: 68%
#   Current pace: 148 WPM
#
# 💡 Recommendation:
#   Build confidence through assertive language
#
# 🎯 Active Goals:
#   • Improve English conversation fluency
```

#### Get Next Learning Recommendation
```python
next_step = analytics.suggest_next_lesson_focus()
print(next_step)
# Outputs: "Next: Review these vocabulary words: eloquent, pragmatic, concise"
# or: "Next: Practice speaking in shorter, clearer sentences"
# or: "Next: Work on using more confident language patterns"
```

#### Export Analytics
```python
data = analytics.export_analytics()
# Returns JSON-ready dict with all analytics for dashboards/reports
```

---

## 4. Enhanced AI Personalization

### What It Does
- Generates AI responses tailored to learner's level and goals
- Incorporates learner context into system prompts
- Provides vocabulary exercises with spaced repetition
- Aligns suggestions with learning objectives

### New Methods

#### Goal-Tailored Suggestions
```python
from modules.ai_engine import AIResponseEngine

# Initialize with user profile for personalization
ai_engine = AIResponseEngine(config, user_profile=profile)

# Generate suggestions aligned with learner's goals
response = ai_engine.generate_goal_tailored_suggestions(
    transcript="I want to improve my presentation skills",
    scene_description="Person in conference room"
)

# Returns: {summary, suggestions, guidance, goal_alignment}
print(response['goal_alignment'])
# Outputs: "This aligns with your goal to improve workplace communication"
```

#### Vocabulary Exercises
```python
# Generate an interactive vocabulary exercise
exercise = ai_engine.generate_vocabulary_exercise(word="eloquent")

# Returns: {word, definition, usage_examples, quiz}
print(f"Definition: {exercise['definition']}")
print(f"Usage: {exercise['usage_examples'][0]}")
print(f"Quiz: {exercise['quiz']}")
```

#### Personalized System Prompt
The AI engine now automatically includes:
- Learner's proficiency level
- Active learning goals
- Current vocabulary count
- Recent speech metrics

This ensures all suggestions are contextually appropriate.

---

## Integration with Main Application

### Complete Workflow

```python
from modules.user_profile import UserProfile
from modules.ai_engine import AIResponseEngine
from modules.speech_analyzer import SpeechAnalyzer
from modules.learning_analytics import LearningAnalytics
import yaml

# ============================================================================
# 1. INITIALIZE SESSION
# ============================================================================
def setup_session(user_id: str):
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    profile = UserProfile(user_id)
    ai_engine = AIResponseEngine(config, user_profile=profile)
    speech_analyzer = SpeechAnalyzer()
    analytics = LearningAnalytics(profile)
    
    return {profile, ai_engine, speech_analyzer, analytics}

# ============================================================================
# 2. PROCESS EACH SPEECH TURN
# ============================================================================
def process_speech(transcript: str, audio_duration: float, session: dict):
    profile, ai_engine, speech_analyzer, analytics = session
    
    # Analyze speech quality
    metrics = speech_analyzer.analyze_transcript(transcript, audio_duration)
    
    # Generate personalized suggestions
    suggestions = ai_engine.generate_goal_tailored_suggestions(transcript)
    
    # Record interaction
    profile.add_conversation_entry(
        transcript=transcript,
        suggestion=suggestions["suggestions"][0],
        feedback=metrics["feedback"][0] if metrics["feedback"] else ""
    )
    
    # Update metrics
    profile.update_speech_metrics({
        "clarity_score": metrics["clarity_score"],
        "avg_pace_wpm": metrics["pace_wpm"],
    })
    
    # Return comprehensive feedback
    return {
        "suggestions": suggestions["suggestions"],
        "speech_feedback": metrics,
        "goal_alignment": suggestions.get("goal_alignment", ""),
    }

# ============================================================================
# 3. TRACK PROGRESS
# ============================================================================
session = setup_session("user_001")
profile, ai_engine, speech_analyzer, analytics = session

# ... process multiple turns ...

# Show progress
analytics.get_progress_report()
analytics.suggest_next_lesson_focus()

# Manage vocabulary reviews
due_words = profile.get_review_due_vocabulary()
for word in due_words:
    exercise = ai_engine.generate_vocabulary_exercise(word)
    # Present exercise to learner
    # Record result: profile.review_vocabulary(word, correct=True/False)
```

---

## Configuration Updates

Add these to your `config.yaml` for enhanced features:

```yaml
# --- Learning/Personalization Settings ---
learning:
  enable_profiles: true
  enable_spaced_repetition: true
  vocabulary_difficulty_levels: ["easy", "medium", "hard"]
  spaced_repetition_intervals: [1, 3, 7, 14, 30]  # days

# --- Speech Analysis Settings ---
speech_analysis:
  enable_real_time_feedback: true
  filler_word_detection: true
  min_clarity_threshold: 0.6
  ideal_pace_wpm: 145  # words per minute
  
# --- Analytics Settings ---
analytics:
  enable_progress_tracking: true
  export_interval: "daily"  # or "session"
  vocabulary_mastery_threshold: 80  # %
```

---

## Examples

### Example 1: Basic Educational Session
See [example_enhanced_usage.py](example_enhanced_usage.py) for a complete runnable example.

### Example 2: Vocabulary Exercise Workflow
```python
# Check what needs review
due_words = profile.get_review_due_vocabulary(limit=3)

for word in due_words:
    # Generate exercise
    exercise = ai_engine.generate_vocabulary_exercise(word)
    
    # Present to learner
    print(f"Word: {exercise['word']}")
    print(f"Definition: {exercise['definition']}")
    print(f"Usage: {exercise['usage_examples'][0]}")
    print(f"Quiz: {exercise['quiz']}")
    
    # Get learner response (in real app)
    learner_correct = get_user_response()
    
    # Update mastery
    profile.review_vocabulary(word, learner_correct)
```

### Example 3: Level-Adaptive Responses
```python
# AI engine automatically adapts to level
ai_engine.user_profile.set_level("beginner")
# Generates simpler, more basic suggestions

ai_engine.user_profile.set_level("advanced")
# Generates more sophisticated, nuanced suggestions
```

---

## File Structure

```
modules/
├── user_profile.py          # ✨ NEW: User profile management
├── speech_analyzer.py       # ✨ NEW: Real-time speech analysis
├── learning_analytics.py    # ✨ NEW: Progress tracking & analytics
├── ai_engine.py            # UPDATED: Now supports personalization
├── audio_capture.py
├── camera_module.py
├── speech_to_text.py
├── text_to_speech.py
├── display.py
└── ... (other modules)

profiles/                     # ✨ NEW: User profile storage
├── user_001_profile.json
├── user_002_profile.json
└── ...

example_enhanced_usage.py    # ✨ NEW: Integration example
ENHANCEMENT_GUIDE.md         # ✨ NEW: This file
```

---

## Best Practices

1. **Set Clear Learning Goals** — Goals should be specific and measurable
2. **Regular Vocabulary Reviews** — Use spaced repetition for long-term retention
3. **Track Speech Metrics** — Monitor clarity and pace improvements over time
4. **Personalize Difficulty** — Adjust vocabulary difficulty as proficiency improves
5. **Use Analytics for Guidance** — Let data guide what to practice next

---

## Troubleshooting

**Q: Vocabulary mastery not improving?**  
A: Ensure reviews are recorded `profile.review_vocabulary(word, correct=True/False)`.

**Q: Speech feedback seems inaccurate?**  
A: Longer transcripts (>20 words) provide better analysis. Ensure audio_duration is accurate.

**Q: Goals not showing in suggestions?**  
A: Verify goals are set with `profile.set_learning_goal()` and status is "active".

**Q: Vocabulary words not due for review?**  
A: Words need initial review first. New words appear as due immediately.

---

## Next Steps

1. ✅ Integrate modules into your `main.py`
2. ✅ Test with `example_enhanced_usage.py`
3. ✅ Create user profiles for your learners
4. ✅ Monitor progress with analytics
5. ✅ Customize prompts and goals per learner

Happy learning! 🎓
