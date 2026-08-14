"""Agent tools for Phase 4.

Five tools:
  - search_web     : Tavily AI search (结构化结果，国内可直接访问)
  - read_file      : read local file (text + PDF)
  - get_weather    : weather via wttr.in (零 API Key，国内可访问)
  - list_dir       : list directory contents
  - search_knowledge : search local FAISS knowledge base
"""

from __future__ import annotations

from pathlib import Path

import httpx
from backend.config import TAVILY_API_KEY
from langchain_core.tools import tool as langchain_tool
from tavily import TavilyClient

_tavily = TavilyClient(api_key=TAVILY_API_KEY)

# read_file 字节上限: 防止读超大文件卡死 Agent 链路
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


# ===========================================================================
# search_web
# ===========================================================================


@langchain_tool
def search_web(query: str) -> str:
    """Search the web using Tavily AI search engine.

    Returns AI-summarized results with full content extraction (not just snippets).
    Results include a ready-to-use answer summary and detailed result pages.
    Works in China without proxy. Best for factual, current, or research queries.

    Args:
        query: Search query string (e.g., "Python 3.13 new features")
    """
    try:
        response = _tavily.search(query, max_results=5, include_answer=True)
        lines: list[str] = []

        # AI-generated answer summary (Tavily 的核心优势)
        if response.get("answer"):
            lines.append(f"【AI 摘要】{response['answer']}\n")

        # Detailed results
        results = response.get("results", [])
        if not results:
            return "No results found." if not lines else "\n".join(lines)

        lines.append("【详细结果】")
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url = r.get("url", "")
            content = r.get("content", "")
            score = r.get("score", 0)
            lines.append(f"{i}. {title} (相关性: {score:.0%})")
            if content:
                lines.append(f"   {content}")
            lines.append(f"   {url}")
        return "\n".join(lines)
    except Exception as e:
        return f"[工具执行失败] search_web 出错：{e}。请告知用户网络暂时不可用，不要编造搜索结果。"


# ===========================================================================
# read_file
# ===========================================================================


@langchain_tool
def read_file(path: str) -> str:
    """Read the contents of a local file (text or PDF).

    Supports .txt, .md, .py, .json, .pdf and other text formats.
    PDF files are extracted via pypdf. Truncates at 8000 chars.

    Args:
        path: Absolute or relative file path
    """
    try:
        filepath = Path(path).expanduser().resolve()
    except Exception:
        return f"Error: invalid path '{path}'"

    if not filepath.exists():
        return f"Error: file not found: {path}"
    if filepath.is_dir():
        return f"Error: '{path}' is a directory, not a file"
    try:
        if filepath.stat().st_size > MAX_FILE_SIZE_BYTES:
            return f"Error: 文件超过 {MAX_FILE_SIZE_BYTES // 1024 // 1024}MB 上限，拒绝读取: {path}"
    except OSError:
        return f"Error: cannot stat file: {path}"

    suffix = filepath.suffix.lower()

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(filepath))
            content = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            return f"Error reading PDF: {e}"
    else:
        try:
            content = filepath.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return "Error: cannot read binary file as text"
        except Exception as e:
            return f"Error reading file: {e}"

    if len(content) > 8000:
        content = content[:8000] + "\n...(truncated)"
    return content


# ===========================================================================
# get_weather
# ===========================================================================


@langchain_tool
def get_weather(city: str) -> str:
    """Get current weather from wttr.in (free, no API key, no proxy needed).

    Returns temperature, conditions, humidity, and wind for any city worldwide.
    Works in China without proxy. City name supports Chinese and English.

    Args:
        city: City name in Chinese or English (e.g., "北京", "Shanghai", "Tokyo")
    """
    try:
        resp = httpx.get(
            f"https://wttr.in/{city}",
            params={"format": "j1"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        current = data.get("current_condition", [{}])[0]
        if not current:
            return f"未找到 {city} 的天气信息"

        temp_c = current.get("temp_C", "?")
        feels_like = current.get("FeelsLikeC", "?")
        humidity = current.get("humidity", "?")
        wind_speed = current.get("windspeedKmph", "?")
        wind_dir = current.get("winddir16Point", "?")
        weather_desc = current.get("weatherDesc", [{}])[0].get("value", "未知")
        visibility = current.get("visibility", "?")

        forecast_lines: list[str] = []
        weather_data = data.get("weather", [])
        for day in weather_data[:3]:
            date = day.get("date", "")
            max_t = day.get("maxtempC", "?")
            min_t = day.get("mintempC", "?")
            desc = day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", "?")
            forecast_lines.append(f"  {date}: {min_t}°C ~ {max_t}°C, {desc}")

        return (
            f"【{city} 当前天气】\n"
            f"  温度: {temp_c}°C (体感 {feels_like}°C)\n"
            f"  天气: {weather_desc}\n"
            f"  湿度: {humidity}%\n"
            f"  风速: {wind_speed} km/h ({wind_dir})\n"
            f"  能见度: {visibility} km\n"
            f"\n【未来预报】\n" + "\n".join(forecast_lines)
        )
    except httpx.HTTPError as e:
        return f"[工具执行失败] get_weather 网络错误：{e}。请告知用户天气服务暂时不可用，不要编造天气数据。"
    except Exception as e:
        return f"[工具执行失败] get_weather 出错：{e}。请告知用户天气服务暂时不可用，不要编造天气数据。"


# ===========================================================================
# list_dir
# ===========================================================================


@langchain_tool
def list_dir(path: str = ".") -> str:
    """List files and subdirectories in a directory.

    Args:
        path: Directory path (defaults to current directory)
    """
    try:
        dirpath = Path(path).expanduser().resolve()
    except Exception:
        return f"Error: invalid path '{path}'"

    if not dirpath.exists():
        return f"Error: directory not found: {path}"
    if not dirpath.is_dir():
        return f"Error: '{path}' is not a directory"

    try:
        items = sorted(dirpath.iterdir())
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as e:
        return f"Error listing directory: {e}"

    if not items:
        return "(empty directory)"

    lines = []
    for item in items:
        prefix = "[DIR]" if item.is_dir() else "[FILE]"
        size = ""
        if item.is_file():
            try:
                size = f" ({item.stat().st_size} bytes)"
            except OSError:
                pass
        lines.append(f"{prefix} {item.name}{size}")
    return "\n".join(lines)


# ===========================================================================
# search_knowledge
# ===========================================================================


@langchain_tool
def search_knowledge(query: str) -> str:
    """Search the local FAISS knowledge base for relevant information.

    Use this when the user asks about the project's architecture, design,
    or documented features.

    Args:
        query: Search query (e.g., "how does emotion system work")
    """
    try:
        from backend.agent.rag_service import knowledge_base

        result = knowledge_base.search(query)
        return result
    except Exception as e:
        return f"[工具执行失败] search_knowledge 出错：{e}。请告知用户知识库暂时不可用，不要编造知识库内容。"


# ===========================================================================
# Tool list for binding to LLM
# ===========================================================================

AGENT_TOOLS = [search_web, read_file, get_weather, list_dir, search_knowledge]
