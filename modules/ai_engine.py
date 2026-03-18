"""
AI Response Engine.

Generates contextual speech guidance and response suggestions
using a local LLM (Ollama), OpenAI API, or Groq API.
Incorporates visual scene context from the camera when available.
"""

import base64
import json
import logging
import time

logger = logging.getLogger(__name__)


class AIResponseEngine:
    """Generates response suggestions using LLM inference."""

    def __init__(self, config: dict, user_profile=None):
        self.cfg = config.get("ai", {})
        self.provider = self.cfg.get("provider", "openai")
        self.max_tokens = self.cfg.get("max_tokens", 256)
        self.temperature = self.cfg.get("temperature", 0.7)
        self.system_prompt = self.cfg.get("system_prompt", "You are a helpful speech guidance assistant.")
        self.user_profile = user_profile  # Optional UserProfile instance for personalization

        self._conversation_history = []
        self._max_history = self.cfg.get("max_history", 10)  # Now configurable via config.yaml
        self.educational_mode = True

    def _build_system_prompt(self) -> str:
        """Build a personalized system prompt based on user profile."""
        if not self.user_profile:
            return self.system_prompt
        
        profile_context = self.user_profile.get_context_for_ai()
        personalized_prompt = (
            f"{self.system_prompt}\n\n"
            f"[Learner Context]: {profile_context}"
        )
        return personalized_prompt

    def _build_messages(self, user_text: str, scene_description: str | None = None) -> list[dict]:
        """Build the message list for the LLM."""
        messages = [{"role": "system", "content": self._build_system_prompt()}]

        # Add conversation history for context
        messages.extend(self._conversation_history[-self._max_history:])

        # Build the user message
        content = f"[User is speaking]: {user_text}"
        if scene_description:
            content += f"\n[Visual context]: {scene_description}"

        messages.append({"role": "user", "content": content})
        return messages

    def generate_suggestions(
        self, transcript: str, scene_description: str | None = None
    ) -> dict:
        """Generate response suggestions from a speech transcript.

        Args:
            transcript: The user's transcribed speech.
            scene_description: Optional scene description from camera analysis.

        Returns:
            Dictionary with keys:
              - "summary": Brief understanding of what the user said
              - "suggestions": List of 2-3 suggested responses
              - "guidance": Contextual advice for the speaker
        """
        if not transcript.strip():
            return {"summary": "", "suggestions": [], "guidance": ""}

        messages = self._build_messages(transcript, scene_description)

        structured_prompt = (
            "Based on what the user just said, provide:\n"
            '1. A one-line summary of their message labeled "SUMMARY:"\n'
            '2. Exactly 3 short suggested responses they could say next, labeled "SUGGESTION 1:", "SUGGESTION 2:", "SUGGESTION 3:"\n'
            '3. A brief guidance note labeled "GUIDANCE:"\n'
            "Keep each suggestion under 30 words."
        )
        messages.append({"role": "user", "content": structured_prompt})

        if self.provider == "ollama":
            raw = self._query_ollama(messages)
        elif self.provider == "groq":
            raw = self._query_groq(messages)
        else:
            raw = self._query_openai(messages)

        result = self._parse_response(raw)

        # Update conversation history
        self._conversation_history.append({"role": "user", "content": transcript})
        self._conversation_history.append({"role": "assistant", "content": raw})

        return result

    def generate_combined(self, transcript: str, scene_description: str | None = None) -> tuple[dict, dict]:
        """Generate suggestions and learning insights in a single LLM call.

        Returns:
            Tuple of (response_dict, insights_dict).
        """
        if not transcript.strip():
            return (
                {"summary": "", "suggestions": [], "guidance": ""},
                {"vocabulary": [], "topic_note": "", "speech_feedback": "", "follow_up_questions": []},
            )

        messages = self._build_messages(transcript, scene_description)

        combined_prompt = (
            "Based on what the user just said, provide ALL of the following in one response:\n"
            'SUMMARY: (one-line summary of their message)\n'
            'SUGGESTION 1: (short response they could say, under 30 words)\n'
            'SUGGESTION 2: (another short response)\n'
            'SUGGESTION 3: (another short response)\n'
            'GUIDANCE: (brief contextual advice)\n'
        )
        if self.educational_mode:
            combined_prompt += (
                'VOCAB: term - definition (up to 2 key vocabulary words)\n'
                'TOPIC NOTE: (1 sentence educational note about the topic)\n'
                'SPEECH FEEDBACK: (brief feedback on speech clarity)\n'
                'QUESTION 1: (thought-provoking follow-up question)\n'
                'QUESTION 2: (another follow-up question)\n'
            )
        combined_prompt += "Be concise. Keep the entire response short."
        messages.append({"role": "user", "content": combined_prompt})

        if self.provider == "ollama":
            raw = self._query_ollama(messages)
        elif self.provider == "groq":
            raw = self._query_groq(messages)
        else:
            raw = self._query_openai(messages)

        response = self._parse_response(raw)
        insights = self._parse_learning_insights(raw) if self.educational_mode else {
            "vocabulary": [], "topic_note": "", "speech_feedback": "", "follow_up_questions": []
        }

        # Update conversation history
        self._conversation_history.append({"role": "user", "content": transcript})
        self._conversation_history.append({"role": "assistant", "content": raw})

        return response, insights

    def analyze_scene(self, image_bytes: bytes) -> str:
        """Analyze a camera frame and return a scene description.

        Uses a multimodal model if available, otherwise returns empty string.
        """
        if not image_bytes:
            return ""

        if self.provider == "ollama":
            return self._analyze_scene_ollama(image_bytes)
        elif self.provider == "groq":
            return ""  # Groq doesn't support vision
        return self._analyze_scene_openai(image_bytes)

    def _query_ollama(self, messages: list[dict]) -> str:
        """Query the local Ollama LLM."""
        try:
            import ollama

            model = self.cfg.get("ollama_model", "llama3.2:3b")
            response = ollama.chat(
                model=model,
                messages=messages,
                options={
                    "num_predict": self.max_tokens,
                    "temperature": self.temperature,
                    "num_ctx": 2048,
                    "repeat_penalty": 1.1,
                },
            )
            return response["message"]["content"]
        except Exception as e:
            logger.error("Ollama query failed: %s", e)
            return ""

    def _query_groq(self, messages: list[dict]) -> str:
        """Query the Groq API (fast cloud inference)."""
        try:
            from groq import Groq

            api_key = self.cfg.get("groq_api_key", "")
            if not api_key:
                logger.error("Groq API key not configured")
                return ""

            client = Groq(api_key=api_key, timeout=30.0)
            response = client.chat.completions.create(
                model=self.cfg.get("groq_model", "llama-3.3-70b-versatile"),
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("Groq query failed: %s", e)
            return ""

    def _query_openai(self, messages: list[dict]) -> str:
        """Query the OpenAI API."""
        try:
            from openai import OpenAI

            api_key = self.cfg.get("openai_api_key", "")
            if not api_key:
                logger.error("OpenAI API key not configured")
                return ""

            client = OpenAI(api_key=api_key, timeout=30.0)
            response = client.chat.completions.create(
                model=self.cfg.get("openai_model", "gpt-4o-mini"),
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("OpenAI query failed: %s", e)
            return ""

    def _analyze_scene_ollama(self, image_bytes: bytes) -> str:
        """Analyze scene using Ollama with a vision model."""
        try:
            import ollama

            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            response = ollama.chat(
                model="llava:7b",  # Vision model
                messages=[
                    {
                        "role": "user",
                        "content": "Briefly describe the scene in one sentence. Focus on people, objects, and context relevant to a conversation.",
                        "images": [b64_image],
                    }
                ],
                options={"num_predict": 80},
            )
            desc = response["message"]["content"].strip()
            logger.info("Scene analysis: %s", desc[:80])
            return desc
        except Exception as e:
            logger.debug("Ollama scene analysis unavailable: %s", e)
            return ""

    def _analyze_scene_openai(self, image_bytes: bytes) -> str:
        """Analyze scene using OpenAI Vision."""
        try:
            from openai import OpenAI

            api_key = self.cfg.get("openai_api_key", "")
            if not api_key:
                return ""

            client = OpenAI(api_key=api_key)
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Briefly describe the scene in one sentence. Focus on people, objects, and context.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                            },
                        ],
                    }
                ],
                max_tokens=80,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.debug("OpenAI scene analysis failed: %s", e)
            return ""

    def _parse_response(self, raw: str) -> dict:
        """Parse the structured LLM response into components."""
        result = {"summary": "", "suggestions": [], "guidance": ""}

        if not raw:
            return result

        lines = raw.strip().split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            upper = line.upper()
            if upper.startswith("SUMMARY:"):
                result["summary"] = line.split(":", 1)[1].strip()
                current_section = "summary"
            elif "SUGGESTION" in upper and ":" in line:
                suggestion = line.split(":", 1)[1].strip().strip('"')
                if suggestion:
                    result["suggestions"].append(suggestion)
                current_section = "suggestion"
            elif upper.startswith("GUIDANCE:"):
                result["guidance"] = line.split(":", 1)[1].strip()
                current_section = "guidance"
            elif current_section == "guidance":
                result["guidance"] += " " + line

        # Fallback: if parsing fails, use raw text as guidance
        if not result["suggestions"] and not result["summary"]:
            result["guidance"] = raw.strip()

        return result

    def generate_learning_insights(self, transcript: str) -> dict:
        """Generate educational insights from the user's speech.

        Returns:
            Dictionary with keys:
              - "vocabulary": List of {"term": str, "definition": str}
              - "topic_note": Brief educational explanation about the topic
              - "speech_feedback": Constructive feedback on speech quality
              - "follow_up_questions": List of Socratic questions
        """
        if not self.educational_mode or not transcript.strip():
            return {"vocabulary": [], "topic_note": "", "speech_feedback": "", "follow_up_questions": []}

        messages = [
            {"role": "system", "content": (
                "You are an educational analyst. Given a speech transcript, "
                "extract learning opportunities. Be concise and helpful."
            )},
            {"role": "user", "content": f"Transcript: {transcript}"},
            {"role": "user", "content": (
                "Analyze this transcript and provide:\n"
                '1. Up to 3 key vocabulary words with short definitions, each labeled "VOCAB: term - definition"\n'
                '2. A 1-2 sentence educational note about the topic being discussed, labeled "TOPIC NOTE:"\n'
                '3. Brief constructive feedback on the speech clarity or structure, labeled "SPEECH FEEDBACK:"\n'
                '4. 2 thought-provoking follow-up questions to deepen understanding, labeled "QUESTION 1:" and "QUESTION 2:"\n'
                "Keep everything concise."
            )}
        ]

        if self.provider == "ollama":
            raw = self._query_ollama(messages)
        else:
            raw = self._query_openai(messages)

        return self._parse_learning_insights(raw)

    def _parse_learning_insights(self, raw: str) -> dict:
        """Parse the structured educational response."""
        result = {"vocabulary": [], "topic_note": "", "speech_feedback": "", "follow_up_questions": []}
        if not raw:
            return result

        lines = raw.strip().split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            upper = line.upper()
            if upper.startswith("VOCAB:"):
                content = line.split(":", 1)[1].strip()
                if " - " in content:
                    term, definition = content.split(" - ", 1)
                    result["vocabulary"].append({"term": term.strip(), "definition": definition.strip()})
                current_section = "vocab"
            elif upper.startswith("TOPIC NOTE:"):
                result["topic_note"] = line.split(":", 1)[1].strip()
                current_section = "topic_note"
            elif upper.startswith("SPEECH FEEDBACK:"):
                result["speech_feedback"] = line.split(":", 1)[1].strip()
                current_section = "speech_feedback"
            elif "QUESTION" in upper and ":" in line:
                q = line.split(":", 1)[1].strip()
                if q:
                    result["follow_up_questions"].append(q)
                current_section = "question"
            elif current_section == "topic_note":
                result["topic_note"] += " " + line
            elif current_section == "speech_feedback":
                result["speech_feedback"] += " " + line

        return result

    def clear_history(self):
        """Clear conversation history."""
        self._conversation_history.clear()

    def generate_vocabulary_exercise(self, word: str = None) -> dict:
        """Generate an interactive vocabulary exercise.
        
        Args:
            word: Specific word to focus on, or None to use a learner's due word.
        
        Returns:
            Dictionary with exercise details including definition, usage, and quiz.
        """
        if not word and self.user_profile:
            due_words = self.user_profile.get_review_due_vocabulary(limit=1)
            word = due_words[0] if due_words else None
        
        if not word:
            return {"word": "", "definition": "", "usage_examples": [], "quiz": ""}
        
        messages = [
            {"role": "system", "content": "You are a vocabulary assistant."},
            {"role": "user", "content": f"Create a vocabulary exercise for the word: {word}"},
            {"role": "user", "content": (
                f"Provide for '{word}':\n"
                "DEFINITION: (clear, simple definition)\n"
                "USAGE 1: (example sentence)\n"
                "USAGE 2: (another example)\n"
                "QUIZ: (True/False question to test understanding)\n"
            )}
        ]
        
        if self.provider == "ollama":
            raw = self._query_ollama(messages)
        elif self.provider == "groq":
            raw = self._query_groq(messages)
        else:
            raw = self._query_openai(messages)
        
        return self._parse_vocabulary_exercise(raw, word)

    def _parse_vocabulary_exercise(self, raw: str, word: str) -> dict:
        """Parse vocabulary exercise response."""
        result = {"word": word, "definition": "", "usage_examples": [], "quiz": ""}
        
        lines = raw.strip().split("\n")
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            upper = line.upper()
            if upper.startswith("DEFINITION:"):
                result["definition"] = line.split(":", 1)[1].strip()
                current_section = "definition"
            elif upper.startswith("USAGE"):
                example = line.split(":", 1)[1].strip() if ":" in line else line
                if example:
                    result["usage_examples"].append(example)
                current_section = "usage"
            elif upper.startswith("QUIZ:"):
                result["quiz"] = line.split(":", 1)[1].strip()
                current_section = "quiz"
            elif current_section == "quiz" and result["quiz"]:
                result["quiz"] += " " + line
        
        return result

    def generate_goal_tailored_suggestions(self, transcript: str, scene_description: str | None = None) -> dict:
        """Generate suggestions tailored to the learner's specific goals.
        
        Incorporates learning goals and vocabulary from user profile.
        """
        if not transcript.strip():
            return {"summary": "", "suggestions": [], "guidance": "", "goal_alignment": ""}
        
        messages = self._build_messages(transcript, scene_description)
        
        # Build goal-aware prompt
        goal_context = ""
        if self.user_profile:
            summary = self.user_profile.get_profile_summary()
            goals = summary.get("learning_goals", [])
            if goals:
                goal_context = f"\nConsider the learner's goals: {', '.join(goals)}. "
        
        structured_prompt = (
            f"Based on what the user just said, provide:{goal_context}\n"
            '1. A one-line summary labeled "SUMMARY:"\n'
            '2. Exactly 3 short suggested responses labeled "SUGGESTION 1:", "SUGGESTION 2:", "SUGGESTION 3:"\n'
            '3. A brief guidance note labeled "GUIDANCE:"\n'
            '4. A note on how this aligns with their learning goals, labeled "GOAL ALIGNMENT:"\n'
            "Keep each suggestion under 30 words."
        )
        messages.append({"role": "user", "content": structured_prompt})
        
        if self.provider == "ollama":
            raw = self._query_ollama(messages)
        elif self.provider == "groq":
            raw = self._query_groq(messages)
        else:
            raw = self._query_openai(messages)
        
        result = self._parse_response(raw)
        
        # Add goal alignment
        lines = raw.split("\n")
        for i, line in enumerate(lines):
            if line.upper().startswith("GOAL ALIGNMENT:"):
                result["goal_alignment"] = line.split(":", 1)[1].strip()
        
        # Update conversation history
        self._conversation_history.append({"role": "user", "content": transcript})
        self._conversation_history.append({"role": "assistant", "content": raw})
        
        return result
