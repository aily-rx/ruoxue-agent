"""Unit tests for agent tools (pure logic, no I/O)."""

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
