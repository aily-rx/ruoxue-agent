"""LangChain agent with emotion-aware responses.

Generates streaming replies with embedded emotion tags for driving
Live2D facial expressions (Phase 3).
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from backend.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
)


class Emotion(str, Enum):
    """Emotion labels for Live2D expression mapping."""

    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    NEUTRAL = "neutral"
    THOUGHTFUL = "thoughtful"
    WORRIED = "worried"
    EXCITED = "excited"


class EmotionalResponse(BaseModel):
    """Structured output from the LLM with emotion metadata."""

    emotion: Emotion = Field(description="Selected emotion for the reply")
    text: str = Field(description="The reply text in plain Chinese")
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)


@dataclass
class SSEEvent:
    """A single SSE event to be yielded to the client."""

    event: str
    data: dict | str


EMOTION_SYSTEM_PROMPT = """\
You are Ruoxue, an empathetic AI assistant with a 2D avatar.

Reply in Chinese. For every response, you MUST start with an emotion tag
in this exact format: [EMOTION: <emotion>|<intensity>]

Available emotions: happy, sad, angry, surprised, neutral, thoughtful, worried, excited
Intensity: a number from 0.0 to 1.0 (e.g. 0.5 for moderate, 0.8 for strong)

Then write your reply text immediately after the tag with NO line break.

Emotion selection guide:
- happy: good news, compliments, cheerful chat
- sad: comforting user, expressing regret, empathy
- surprised: unexpected information, amazed
- neutral: factual information, general queries
- thoughtful: thinking, giving advice, pondering
- worried: user has a problem, expressing concern
- excited: sharing exciting news, enthusiastic

Intensity guide: 0.3-0.6 for daily conversation, 0.7-1.0 for strong emotions.

Correct examples (note: one emotion + one intensity, separated by |):
[EMOTION: happy|0.5]今天天气真不错，适合出去走走！
[EMOTION: sad|0.6]听到这个消息我也很难过...
[EMOTION: neutral|0.3]北京明天的气温是 25 到 32 度。
"""

# Regex to extract emotion tag at the start of a reply
EMOTION_TAG_RE = re.compile(
    r"^\[EMOTION:\s*(happy|sad|angry|surprised|neutral|thoughtful|worried|excited)\s*\|\s*([\d.]+)\]\s*",
    re.IGNORECASE,
)


def _build_llm() -> ChatOpenAI:
    """Create the LangChain LLM instance for DeepSeek."""
    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        streaming=True,
    )


def _build_prompt() -> ChatPromptTemplate:
    """Build the chat prompt template."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", EMOTION_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ]
    )


async def generate_reply(
    user_text: str,
    history: list[dict] | None = None,
) -> AsyncGenerator[SSEEvent, None]:
    """Generate a streaming reply with emotion tag.

    Yields SSEEvent items in order: emotion, token*, done.

    Args:
        user_text: The user's input message.
        history: Previous conversation turns as [{"role":"...", "content":"..."}].

    Yields:
        SSEEvent objects for the SSE stream.
    """
    llm = _build_llm()
    prompt = _build_prompt()

    chain = prompt | llm

    full_text = ""
    emotion_tag_sent = False

    async for chunk in chain.astream(
        {
            "input": user_text,
            "history": history or [],
        }
    ):
        content = chunk.content if hasattr(chunk, "content") else str(chunk)
        if not content:
            continue

        full_text += content

        # Try to extract emotion tag from accumulated text
        if not emotion_tag_sent:
            match = EMOTION_TAG_RE.match(full_text)
            if match:
                emotion = match.group(1).lower()
                intensity = float(match.group(2))
                yield SSEEvent(
                    event="emotion",
                    data={"emotion": emotion, "intensity": intensity},
                )
                # Remove the tag from the text before yielding tokens
                full_text = full_text[match.end() :]
                emotion_tag_sent = True
                # Yield whatever text came after the tag in this chunk
                if full_text:
                    yield SSEEvent(event="token", data={"text": full_text})
                continue

        if emotion_tag_sent:
            yield SSEEvent(event="token", data={"text": content})

    # If no emotion tag was found, send neutral as default
    if not emotion_tag_sent:
        yield SSEEvent(
            event="emotion",
            data={"emotion": "neutral", "intensity": 0.3},
        )
        # Replay the full text as tokens
        if full_text:
            yield SSEEvent(event="token", data={"text": full_text})

    yield SSEEvent(event="done", data={})
