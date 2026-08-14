"""Unit tests for agent tools (pure logic, no I/O)."""

import httpx
from backend.agent.tools import AGENT_TOOLS


class TestAgentTools:
    """High-level test suite for the tool collection."""

    def test_has_five_tools(self):
        """All 5 tools should be registered."""
        assert len(AGENT_TOOLS) == 5

    def test_has_correct_tool_names(self):
        """Verify expected tool names are present."""
        names = {t.name for t in AGENT_TOOLS}
        expected = {"search_web", "read_file", "get_weather", "list_dir", "search_knowledge"}
        assert names == expected

    def test_every_tool_has_description(self):
        """Every tool must provide a description for the LLM."""
        for tool in AGENT_TOOLS:
            assert tool.description, f"Tool '{tool.name}' is missing a description"
            assert len(tool.description) > 10, f"Tool '{tool.name}' description too short"


class TestSearchWebTool:
    """Tests for search_web tool."""

    def test_has_expected_name(self):
        tool = [t for t in AGENT_TOOLS if t.name == "search_web"][0]
        assert tool.name == "search_web"


class TestReadFileTool:
    """Tests for read_file tool."""

    def test_has_expected_name(self):
        tool = [t for t in AGENT_TOOLS if t.name == "read_file"][0]
        assert tool.name == "read_file"


class TestToolErrorHandling:
    """工具级容错: 失败必须返回结构化错误文案(含防幻觉指令), 而不是抛异常。"""

    @staticmethod
    def _tool(name: str):
        return [t for t in AGENT_TOOLS if t.name == name][0]

    def test_search_web_error_returns_structured_message(self, monkeypatch):
        """网络失败 → 结构化错误 + 防幻觉指令, 让 LLM 决定如何告知用户。"""

        class FakeTavily:
            def search(self, *args, **kwargs):
                raise RuntimeError("network down")

        monkeypatch.setattr("backend.agent.tools._tavily", FakeTavily())
        result = self._tool("search_web").invoke({"query": "测试"})
        assert "[工具执行失败]" in result
        assert "不要编造搜索结果" in result

    def test_get_weather_http_error_returns_structured_message(self, monkeypatch):
        def fake_get(*args, **kwargs):
            raise httpx.HTTPError("timeout")

        monkeypatch.setattr("backend.agent.tools.httpx.get", fake_get)
        result = self._tool("get_weather").invoke({"city": "北京"})
        assert "[工具执行失败]" in result
        assert "不要编造天气数据" in result

    def test_search_knowledge_error_returns_structured_message(self, monkeypatch):
        class FakeKB:
            def search(self, query):
                raise RuntimeError("index corrupt")

        monkeypatch.setattr("backend.agent.rag_service.knowledge_base", FakeKB())
        result = self._tool("search_knowledge").invoke({"query": "测试"})
        assert "[工具执行失败]" in result
        assert "不要编造知识库内容" in result

    def test_read_file_rejects_oversized_file(self, tmp_path):
        big = tmp_path / "big.txt"
        big.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
        result = self._tool("read_file").invoke({"path": str(big)})
        assert "上限" in result

    def test_read_file_missing_returns_error(self):
        result = self._tool("read_file").invoke({"path": "/no/such/file.txt"})
        assert "not found" in result

    def test_read_file_directory_returns_error(self, tmp_path):
        result = self._tool("read_file").invoke({"path": str(tmp_path)})
        assert "directory" in result
