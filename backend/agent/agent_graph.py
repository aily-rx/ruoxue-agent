"""LangGraph agent — Phase 4 core.

Architecture:
  START → agent_node → should_continue → tools_node / END
              ↑                                      │
              └──────────────────────────────────────┘

State uses a four-layer prompt: system_prompt (static persona)
+ runtime_context (date) + memory_context (Chroma) + skill_context (DeepSeek Skills).
"""

from __future__ import annotations

import sys
from collections.abc import AsyncGenerator, Sequence
from datetime import datetime
from pathlib import Path
from typing import Annotated

from backend.agent.chroma_memory import chroma_memory
from backend.agent.emotional_agent import (
    EMOTION_SYSTEM_PROMPT,
    EMOTION_TAG_RE,
    SSEEvent,
)
from backend.agent.tools import AGENT_TOOLS
from backend.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
)
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

# ---------------------------------------------------------------------------
# DeepSeek Skills — dynamic prompt injection
# ---------------------------------------------------------------------------

_deepseek_skills_path = str(Path(__file__).resolve().parent.parent / "deepseek-skills")
if _deepseek_skills_path not in sys.path:
    sys.path.insert(0, _deepseek_skills_path)

from skill_loader import SkillLoader  # noqa: E402

_skill_loader = SkillLoader(str(Path(__file__).resolve().parent.parent / "deepseek-skills" / "skills"))

# ---------------------------------------------------------------------------
# LangGraph State
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    """State carried through the agent graph.

    Four-layer prompt architecture:
      system_prompt   — static:  persona, emotion rules, reply format
      runtime_context — dynamic: date/time (future: user profile, emotion state)
      memory_context  — retrieval: Chroma long-term memory
      skill_context   — dynamic: matched DeepSeek Skill prompt (engineering/productivity)
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    system_prompt: str
    runtime_context: str
    memory_context: str
    skill_context: str


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,  # type: ignore[arg-type]
        base_url=DEEPSEEK_BASE_URL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,  # type: ignore[call-arg]
        streaming=True,
    )


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


async def agent_node(state: AgentState) -> dict:
    """Core reasoning node — combines three prompt layers, then invokes LLM.

    Does NOT construct prompts — only reads state and concatenates.
    All prompt building happens upstream in run_agent_stream.
    """
    llm = _build_llm()
    llm_with_tools = llm.bind_tools(AGENT_TOOLS)

    # Layer 1: static persona  |  Layer 2: runtime  |  Layer 3: long-term memory  |  Layer 4: skill
    parts = [state["system_prompt"]]
    if state["runtime_context"]:
        parts.append(state["runtime_context"])
    if state["memory_context"]:
        parts.append(state["memory_context"])
    if state["skill_context"]:
        parts.append(state["skill_context"])
    system_text = "\n\n".join(parts)

    system = SystemMessage(content=system_text)
    messages = [system] + list(state["messages"])
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """Router: check whether the last message contains tool calls."""
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    return END


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

_workflow = StateGraph(AgentState)
_workflow.add_node("agent", agent_node)
_workflow.add_node("tools", ToolNode(AGENT_TOOLS))
_workflow.add_edge(START, "agent")
_workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        END: END,
    },
)
_workflow.add_edge("tools", "agent")

agent_graph = _workflow.compile()


# ---------------------------------------------------------------------------
# Public API — drop-in replacement for emotional_agent.generate_reply()
# ---------------------------------------------------------------------------


async def run_agent_stream(
    user_text: str,
    history: list[dict] | None = None,
) -> AsyncGenerator[SSEEvent, None]:
    """Stream the agent's reply token-by-token via SSE.

    Builds a four-layer system prompt and hands it to LangGraph:
      Layer 1 — system_prompt   (static persona from emotional_agent)
      Layer 2 — runtime_context  (current date, future: user profile)
      Layer 3 — memory_context   (Chroma long-term memory)
      Layer 4 — skill_context    (keyword-matched from deepseek-skills/)
    """
    # Layer 1: static persona (never changes)
    system_prompt = EMOTION_SYSTEM_PROMPT

    # Layer 2: runtime context (dynamic per-request)
    now = datetime.now()
    weekday = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]
    runtime_context = f"当前日期：{now.year}年{now.month}月{now.day}日，星期{weekday}。"

    # Layer 3: long-term memory (semantic retrieval from Chroma)
    memory_context = (
        "\n\n你拥有长期记忆。以下是与当前话题相关的历史对话，"
        "请自然地引用它们（如果用户问起相关话题，可以说「之前我们聊过」）：\n\n"
    )
    chroma_hits = chroma_memory.retrieve_context(user_text)
    if chroma_hits:
        memory_context += chroma_hits
        print(f"[Chroma] retrieved context ({len(chroma_hits)} chars)")
    else:
        memory_context = ""  # skip if nothing relevant

    # Layer 4: dynamic skill context (keyword-matched from deepseek-skills/)
    skill_context = ""
    skill_name = _skill_loader.match(user_text)
    if skill_name:
        skill_content = _skill_loader.load(skill_name)
        if skill_content:
            skill_context = (
                f"[技能指令 — {skill_name}]\n" "以下是适用于当前任务的专项指令，请严格遵循：\n\n" f"{skill_content}"
            )
            print(f"[Skill] matched '{skill_name}' for input: {user_text[:50]}...")

    # --- Build LangChain messages from short-term history ---
    lc_messages: list[BaseMessage] = []
    for msg in history or []:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))

    lc_messages.append(HumanMessage(content=user_text))

    full_text = ""
    emotion_tag_sent = False
    tool_phase = False  # True while LLM is calling/delegating to tools

    # Errors propagate to routes.py which wraps them as SSE error events
    async for item in agent_graph.astream(
        {
            "messages": lc_messages,
            "system_prompt": system_prompt,
            "runtime_context": runtime_context,
            "memory_context": memory_context,
            "skill_context": skill_context,
        },
        stream_mode="messages",
    ):
        if isinstance(item, tuple) and len(item) == 2:
            chunk, _metadata = item
        else:
            chunk = item

        # --- Tool phase detection ---
        if not isinstance(chunk, AIMessageChunk):
            # ToolMessage or other — tools have returned, ready for real response
            tool_phase = False
            full_text = ""
            emotion_tag_sent = False
            continue

        if chunk.tool_call_chunks:
            # LLM is about to call tools — discard internal thinking text
            tool_phase = True
            full_text = ""
            emotion_tag_sent = False
            continue

        if tool_phase:
            # Suppress all content while tools are executing
            continue
        # --- End tool phase detection ---

        chunk_text: str = chunk.content if isinstance(chunk.content, str) else ""
        if not chunk_text:
            continue

        full_text += chunk_text

        if not emotion_tag_sent:
            match = EMOTION_TAG_RE.match(full_text)
            if match:
                emotion = match.group(1).lower()
                intensity = float(match.group(2))
                yield SSEEvent(
                    event="emotion",
                    data={"emotion": emotion, "intensity": intensity},
                )
                full_text = full_text[match.end() :]
                emotion_tag_sent = True
                if full_text:
                    yield SSEEvent(event="token", data={"text": full_text})
                continue

        if emotion_tag_sent:
            yield SSEEvent(event="token", data={"text": chunk_text})

    if not emotion_tag_sent:
        yield SSEEvent(
            event="emotion",
            data={"emotion": "neutral", "intensity": 0.3},
        )
        if full_text:
            yield SSEEvent(event="token", data={"text": full_text})

    yield SSEEvent(event="done", data={})
