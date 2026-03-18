"""
Streaming Response Handler.

Enables real-time token streaming from LLM providers (OpenAI, Groq, Ollama)
for a Gemini-like experience where responses appear token-by-token.

Supports:
  - Web streaming via callback functions
  - Terminal streaming with real-time display
  - Multiple LLM providers (OpenAI, Groq, Ollama)
"""

import logging
import threading
from typing import Callable, Generator

logger = logging.getLogger(__name__)


class StreamingResponseHandler:
    """Handles streaming responses from LLM providers."""

    def __init__(self, config: dict):
        self.cfg = config.get("ai", {})
        self.provider = self.cfg.get("provider", "openai")
        self.max_tokens = self.cfg.get("max_tokens", 500)
        self.temperature = self.cfg.get("temperature", 0.7)

    def stream_response(
        self, 
        messages: list[dict],
        on_token: Callable[[str], None] = None,
        on_complete: Callable[[str], None] = None,
        on_error: Callable[[str], None] = None,
    ) -> str:
        """
        Stream a response from the LLM.
        
        Args:
            messages: List of message dicts for the LLM
            on_token: Callback function called for each token: on_token(token_str)
            on_complete: Callback when complete (full response): on_complete(full_response)
            on_error: Callback on error: on_error(error_message)
        
        Returns:
            Full accumulated response string
        """
        try:
            if self.provider == "ollama":
                return self._stream_ollama(messages, on_token, on_complete, on_error)
            elif self.provider == "groq":
                return self._stream_groq(messages, on_token, on_complete, on_error)
            else:
                return self._stream_openai(messages, on_token, on_complete, on_error)
        except Exception as e:
            error_msg = f"Streaming error: {str(e)}"
            logger.error(error_msg)
            if on_error:
                on_error(error_msg)
            return ""

    def _stream_openai(
        self,
        messages: list[dict],
        on_token: Callable[[str], None] = None,
        on_complete: Callable[[str], None] = None,
        on_error: Callable[[str], None] = None,
    ) -> str:
        """Stream from OpenAI API."""
        try:
            from openai import OpenAI

            api_key = self.cfg.get("openai_api_key", "")
            if not api_key:
                raise ValueError("OpenAI API key not configured")

            client = OpenAI(api_key=api_key, timeout=60.0)
            
            full_response = ""
            
            with client.chat.completions.create(
                model=self.cfg.get("openai_model", "gpt-4o-mini"),
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True,
            ) as stream:
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        full_response += token
                        if on_token:
                            on_token(token)
            
            if on_complete:
                on_complete(full_response)
            return full_response

        except Exception as e:
            logger.error("OpenAI streaming failed: %s", e)
            if on_error:
                on_error(str(e))
            return ""

    def _stream_groq(
        self,
        messages: list[dict],
        on_token: Callable[[str], None] = None,
        on_complete: Callable[[str], None] = None,
        on_error: Callable[[str], None] = None,
    ) -> str:
        """Stream from Groq API."""
        try:
            from groq import Groq

            api_key = self.cfg.get("groq_api_key", "")
            if not api_key:
                raise ValueError("Groq API key not configured")

            client = Groq(api_key=api_key, timeout=60.0)
            
            full_response = ""
            
            with client.chat.completions.create(
                model=self.cfg.get("groq_model", "llama-3.3-70b-versatile"),
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True,
            ) as stream:
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        full_response += token
                        if on_token:
                            on_token(token)
            
            if on_complete:
                on_complete(full_response)
            return full_response

        except Exception as e:
            logger.error("Groq streaming failed: %s", e)
            if on_error:
                on_error(str(e))
            return ""

    def _stream_ollama(
        self,
        messages: list[dict],
        on_token: Callable[[str], None] = None,
        on_complete: Callable[[str], None] = None,
        on_error: Callable[[str], None] = None,
    ) -> str:
        """Stream from Ollama (local)."""
        try:
            import ollama

            model = self.cfg.get("ollama_model", "llama3.2:1b")
            
            full_response = ""
            
            response = ollama.chat(
                model=model,
                messages=messages,
                stream=True,
                options={
                    "num_predict": self.max_tokens,
                    "temperature": self.temperature,
                    "num_ctx": 2048,
                    "repeat_penalty": 1.1,
                },
            )
            
            for chunk in response:
                token = chunk.get("message", {}).get("content", "")
                if token:
                    full_response += token
                    if on_token:
                        on_token(token)
            
            if on_complete:
                on_complete(full_response)
            return full_response

        except Exception as e:
            logger.error("Ollama streaming failed: %s", e)
            if on_error:
                on_error(str(e))
            return ""

    def stream_response_async(
        self,
        messages: list[dict],
        on_token: Callable[[str], None] = None,
        on_complete: Callable[[str], None] = None,
        on_error: Callable[[str], None] = None,
    ) -> threading.Thread:
        """
        Stream response in a background thread.
        
        Returns:
            The thread object (you can call .join() to wait for completion)
        """
        def _stream_thread():
            self.stream_response(messages, on_token, on_complete, on_error)
        
        thread = threading.Thread(target=_stream_thread, daemon=True)
        thread.start()
        return thread
