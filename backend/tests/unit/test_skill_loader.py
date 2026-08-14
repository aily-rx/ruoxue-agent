"""SkillLoader 单元测试 — 关键词匹配 / 加载 / 边界输入。

覆盖: match 命中/未命中/阈值/大小写/长关键词优先/priority 加权,
load 存在与缺失, core_rules, list_skills 排序, reload, 最小 YAML 解析器。
全部使用 tmp_path 构造临时 skills 目录, 不依赖仓库内真实 skills/。
"""

from __future__ import annotations

from pathlib import Path

from backend.agent.skill_loader import SkillLoader


def _make_skills_dir(tmp_path: Path) -> Path:
    """构造含 3 个 skill + CORE_RULES 的临时 skills 目录。"""
    skills_dir = tmp_path / "skills"
    tdd = skills_dir / "engineering" / "tdd"
    review = skills_dir / "engineering" / "code-review"
    handoff = skills_dir / "productivity" / "handoff"
    tdd.mkdir(parents=True)
    review.mkdir(parents=True)
    handoff.mkdir(parents=True)

    tdd.joinpath("deepseek.yaml").write_text(
        "name: tdd\ndisplay_name: TDD测试驱动\npriority: 9\ntrigger_keywords:\n  - 写测试\n  - 单元测试\n",
        encoding="utf-8",
    )
    tdd.joinpath("SKILL.md").write_text("# TDD\n写测试前先写断言。", encoding="utf-8")

    review.joinpath("deepseek.yaml").write_text(
        "name: code-review\ndisplay_name: 代码审查\npriority: 5\ntrigger_keywords:\n  - 审查\n  - code review\n",
        encoding="utf-8",
    )
    review.joinpath("SKILL.md").write_text("# Code Review\n审查边界。", encoding="utf-8")

    handoff.joinpath("deepseek.yaml").write_text(
        "name: handoff\ndisplay_name: 会话交接\npriority: 8\ntrigger_keywords:\n  - 总结一下\n",
        encoding="utf-8",
    )
    handoff.joinpath("SKILL.md").write_text("# Handoff\n交接上下文。", encoding="utf-8")

    skills_dir.joinpath("CORE_RULES.md").write_text("1. 先验证再声称过关", encoding="utf-8")
    return skills_dir


def _loader(tmp_path: Path) -> SkillLoader:
    return SkillLoader(str(_make_skills_dir(tmp_path)))


# --- match: 命中 / 未命中 / 边界 ---


def test_match_hit_by_keyword(tmp_path: Path) -> None:
    loader = _loader(tmp_path)
    assert loader.match("帮我写个单元测试") == "tdd"


def test_match_no_hit_returns_none(tmp_path: Path) -> None:
    loader = _loader(tmp_path)
    assert loader.match("今天天气怎么样") is None


def test_match_below_threshold_returns_none(tmp_path: Path) -> None:
    """关键词必须整体出现在输入中——只含子串不算命中（阈值过滤）。"""
    loader = _loader(tmp_path)
    assert loader.match("测试") is None  # "写测试"/"单元测试" 都不含于 "测试"


def test_match_empty_input(tmp_path: Path) -> None:
    loader = _loader(tmp_path)
    assert loader.match("") is None


def test_match_case_insensitive_english(tmp_path: Path) -> None:
    loader = _loader(tmp_path)
    assert loader.match("请 CODE REVIEW 这个 PR") == "code-review"


def test_match_prefers_longer_keyword_score(tmp_path: Path) -> None:
    """长关键词 + 高 priority 的 skill 应胜出（score = Σlen(kw) × priority）。"""
    loader = _loader(tmp_path)
    # tdd: 单元测试 4×9=36 | handoff: 总结一下 4×8=32 → tdd 胜
    assert loader.match("帮我写个单元测试并总结一下") == "tdd"
    # tdd: 写测试 3×9=27 | handoff: 总结一下 4×8=32 → handoff 胜
    assert loader.match("帮我写测试然后总结一下") == "handoff"


def test_match_empty_skills_dir(tmp_path: Path) -> None:
    loader = SkillLoader(str(tmp_path / "empty"))
    assert loader.match("任意输入") is None
    assert loader.list_skills() == []


# --- load / core_rules ---


def test_load_existing_skill(tmp_path: Path) -> None:
    loader = _loader(tmp_path)
    content = loader.load("tdd")
    assert content is not None
    assert "TDD" in content


def test_load_missing_skill_returns_none(tmp_path: Path) -> None:
    loader = _loader(tmp_path)
    assert loader.load("no-such-skill") is None


def test_core_rules_loaded(tmp_path: Path) -> None:
    loader = _loader(tmp_path)
    assert "先验证" in loader.core_rules()


def test_core_rules_missing_returns_empty(tmp_path: Path) -> None:
    loader = SkillLoader(str(tmp_path / "bare"))  # 目录不存在
    assert loader.core_rules() == ""


# --- list_skills / reload ---


def test_list_skills_sorted_by_priority_desc(tmp_path: Path) -> None:
    loader = _loader(tmp_path)
    names = [s["name"] for s in loader.list_skills()]
    assert names == ["tdd", "handoff", "code-review"]  # priority 9 > 8 > 5


def test_list_skills_metadata_fields(tmp_path: Path) -> None:
    loader = _loader(tmp_path)
    tdd = next(s for s in loader.list_skills() if s["name"] == "tdd")
    assert tdd["display_name"] == "TDD测试驱动"
    assert tdd["priority"] == 9
    assert "单元测试" in tdd["trigger_keywords"]


def test_reload_picks_up_changes(tmp_path: Path) -> None:
    skills_dir = _make_skills_dir(tmp_path)
    loader = SkillLoader(str(skills_dir))
    assert loader.match("帮我审查代码") == "code-review"

    # 新增一个高优先级 skill, reload 后应立即可见
    new = skills_dir / "engineering" / "bugfix"
    new.mkdir()
    new.joinpath("deepseek.yaml").write_text(
        "name: bugfix\npriority: 10\ntrigger_keywords:\n  - 修bug\n",
        encoding="utf-8",
    )
    new.joinpath("SKILL.md").write_text("# Bugfix\n", encoding="utf-8")

    loader.reload()
    assert loader.match("帮我修bug") == "bugfix"


# --- 最小 YAML 解析器（无 PyYAML 环境的兜底路径）---


def test_minimal_yaml_parse_basic(tmp_path: Path) -> None:
    parsed = SkillLoader._minimal_yaml_parse("name: tdd\npriority: 9\ntrigger_keywords:\n  - 写测试\n  - 单元测试\n")
    assert parsed == {"name": "tdd", "priority": 9, "trigger_keywords": ["写测试", "单元测试"]}


def test_minimal_yaml_parse_skips_comments_and_empty(tmp_path: Path) -> None:
    parsed = SkillLoader._minimal_yaml_parse("# 注释\n\nname: tdd\n")
    assert parsed == {"name": "tdd"}
