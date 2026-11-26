from functools import lru_cache
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage

from app.core.config import get_model_settings


def extract_text(message: BaseMessage) -> str:
    """Extract readable text from a LangChain response."""
    content: Any = message.content

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []

        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        return "\n".join(
            part for part in text_parts if part
        ).strip()

    return str(content).strip()


@lru_cache
def get_chat_model() -> ChatGoogleGenerativeAI:
    """Create one reusable Gemini chat model instance."""
    settings = get_model_settings()

    if settings.gemini_api_key is None:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Configure it in the environment."
        )

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key.get_secret_value(),
        max_output_tokens=2048,
        timeout=90,
        max_retries=2,
    )


def invoke_model(prompt: str) -> str:
    """Invoke Gemini and return normalized generated text."""
    if not prompt or not prompt.strip():
        raise ValueError("The model prompt cannot be empty.")

    response = get_chat_model().invoke(prompt)
    result = extract_text(response)

    if not result:
        raise RuntimeError(
            "Gemini returned an empty text response."
        )

    return result
