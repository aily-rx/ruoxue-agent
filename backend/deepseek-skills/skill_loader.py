"""
DeepSeek Skills — Universal Skill Loader

Zero-dependency skill loader that matches user input to the most relevant
skill and returns its content as a system prompt fragment.

Usage:
    from skill_loader import SkillLoader

    loader = SkillLoader("./skills")

    # Match skill by user input
    name = loader.match("帮我写个单元测试")
    # → "tdd"

    # Load skill content
    prompt = loader.load("tdd")
    # → "# 测试驱动开发\n\n..."

    # Get all available skills
    all_skills = loader.list_skills()
    # → [{"name": "tdd", "display_name": "TDD测试驱动", ...}, ...]

Integration with LangChain/LangGraph:
    skill_prompt = loader.load(matched_skill)
    system_prompt = base_prompt + "\n\n" + skill_prompt

Integration with any LLM client:
    response = client.chat(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    )
"""

from __future__ import annotations

from pathlib import Path

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class SkillLoader:
    """Load and match DeepSeek skills from a skills directory."""

    def __init__(self, skills_dir: str = "./skills"):
        self._skills_dir = Path(skills_dir)
        self._skills: dict[str, dict] = {}
        self._index_built = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match(self, user_input: str) -> str | None:
        """Match user input to the best skill by keyword scoring.

        Returns the skill name if a match is found above threshold, else None.
        """
        self._ensure_index()
        if not self._skills:
            return None

        best_score = 0
        best_name: str | None = None
        input_lower = user_input.lower()

        for name, meta in self._skills.items():
            score = 0
            for keyword in meta.get("trigger_keywords", []):
                kw_lower = keyword.lower()
                if kw_lower in input_lower:
                    # Longer keyword matches score higher
                    score += len(kw_lower)
            # Weight by priority
            score *= meta.get("priority", 5)

            if score > best_score:
                best_score = score
                best_name = name

        # Minimum threshold to avoid false matches
        if best_score < 10:
            return None

        return best_name

    def load(self, name: str) -> str | None:
        """Load a skill's SKILL.md content as a prompt fragment.

        Returns the raw markdown text, or None if the skill doesn't exist.
        """
        self._ensure_index()
        skill_path = self._skills_dir
        # Search in engineering/ and productivity/ buckets
        for bucket in ("engineering", "productivity"):
            candidate = skill_path / bucket / name / "SKILL.md"
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
        return None

    def core_rules(self) -> str:
        """Return always-active behavioral rules for the AI.

        These rules don't need keyword matching — they belong in every system
        prompt. Callers should inject this text as a permanent prompt layer.
        """
        rules_path = self._skills_dir / "CORE_RULES.md"
        if rules_path.exists():
            return rules_path.read_text(encoding="utf-8")
        return ""

    def list_skills(self) -> list[dict]:
        """Return metadata for all loaded skills, sorted by priority desc."""
        self._ensure_index()
        result = []
        for name, meta in self._skills.items():
            result.append(
                {
                    "name": name,
                    "display_name": meta.get("display_name", name),
                    "type": meta.get("type", "model-invoked"),
                    "priority": meta.get("priority", 5),
                    "trigger_keywords": meta.get("trigger_keywords", []),
                }
            )
        result.sort(key=lambda s: s["priority"], reverse=True)
        return result

    def reload(self) -> None:
        """Force re-scan the skills directory."""
        self._skills = {}
        self._index_built = False
        self._ensure_index()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_index(self) -> None:
        if self._index_built:
            return
        for bucket in ("engineering", "productivity"):
            bucket_dir = self._skills_dir / bucket
            if not bucket_dir.is_dir():
                continue
            for skill_dir in bucket_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                yaml_path = skill_dir / "deepseek.yaml"
                if not yaml_path.exists():
                    continue
                try:
                    meta = self._parse_yaml(yaml_path)
                    if meta and meta.get("name"):
                        self._skills[meta["name"]] = meta
                except Exception:
                    continue
        self._index_built = True

    def _parse_yaml(self, path: Path) -> dict | None:
        """Parse a deepseek.yaml file. Uses PyYAML if available, otherwise a
        minimal built-in parser for the simple structure we use."""
        text = path.read_text(encoding="utf-8")
        if HAS_YAML:
            return yaml.safe_load(text)
        return self._minimal_yaml_parse(text)

    @staticmethod
    def _minimal_yaml_parse(text: str) -> dict:
        """Minimal YAML parser for deepseek.yaml files.
        Handles the simple key-value and list structures we use.
        No external dependency required.
        """
        result: dict = {}
        current_key: str | None = None
        current_list: list = []

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # List item
            if stripped.startswith("- "):
                if current_key:
                    current_list.append(stripped[2:].strip().strip("\"'"))
                continue

            # Key-value
            if ":" in stripped:
                # Save previous list
                if current_key and current_list:
                    result[current_key] = current_list
                    current_list = []

                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip().strip("\"'")
                if value:
                    # Try to convert to number
                    try:
                        result[key] = int(value)
                    except ValueError:
                        try:
                            result[key] = float(value)
                        except ValueError:
                            result[key] = value
                else:
                    current_key = key
                    current_list = []

        # Save last list
        if current_key and current_list:
            result[current_key] = current_list

        return result
