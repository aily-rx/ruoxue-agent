"""Agent tools for Phase 4.

Five tools:
  - search_web     : DuckDuckGo web search
  - read_file      : read local file (text + PDF)
  - get_weather    : weather via DuckDuckGo search
  - list_dir       : list directory contents
  - search_knowledge : search local FAISS knowledge base
"""

from __future__ import annotations

from pathlib import Path

from ddgs import DDGS
from langchain_core.tools import tool as langchain_tool


# ===========================================================================
# search_web
# ===========================================================================

@langchain_tool
def search_web(query: str) -> str:
    """Search the web for current information.

    Use this when you need facts, news, or any information beyond your
    knowledge cutoff. Returns top 5 results with title, URL, and snippet.

    Args:
        query: Search query string (e.g., "Beijing weather forecast")
    """
    try:
        results = list(DDGS().text(query, max_results=5))
        if not results:
            return "No results found."
        lines: list[str] = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            href = r.get("href", "")
            body = r.get("body", "")
            lines.append(f"{i}. {title}\n   {body}\n   {href}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"


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

    suffix = filepath.suffix.lower()

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(filepath))
            content = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
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
    """Get current weather by searching the web via DuckDuckGo.

    No API key required. Works globally for any city name.
    The LLM will read the search results and extract temperature,
    conditions, and forecast.

    Args:
        city: City name in Chinese or English (e.g., "北京", "Shanghai", "Tokyo")
    """
    try:
        results = list(DDGS().text(f"{city} 今天天气 温度", max_results=4))
        if not results:
            return f"未找到 {city} 的天气信息"

        lines = [f"{city} 天气查询结果："]
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            if title and "天气" in title:
                lines.append(f"■ {title}")
            if body:
                lines.append(f"  {body}")
        return "\n".join(lines)
    except Exception as e:
        return f"天气查询失败: {e}"


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
        return f"Knowledge base error: {e}"


# ===========================================================================
# Tool list for binding to LLM
# ===========================================================================

AGENT_TOOLS = [search_web, read_file, get_weather, list_dir, search_knowledge]
