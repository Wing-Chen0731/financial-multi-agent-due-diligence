from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    risk_level: str
    triggers: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    path: Path = field(default=Path())
    body: str = ""


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) != 3:
        return {}, text
    metadata: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, parts[2].lstrip()


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


class SkillRegistry:
    """Loads and routes versioned Markdown skills without hidden code execution."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else Path(__file__).resolve().parent
        self._skills = self._load()

    def _load(self) -> dict[str, SkillDefinition]:
        skills: dict[str, SkillDefinition] = {}
        for path in sorted(self.root.glob("**/SKILL.md")):
            metadata, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
            name = metadata.get("name") or path.parent.name
            skills[name] = SkillDefinition(
                name=name,
                description=metadata.get("description", ""),
                risk_level=metadata.get("risk_level", "medium"),
                triggers=_csv(metadata.get("triggers")),
                tools=_csv(metadata.get("tools")),
                path=path,
                body=body,
            )
        return skills

    def all(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def get(self, name: str) -> SkillDefinition:
        try:
            return self._skills[name]
        except KeyError as exc:
            raise KeyError(f"未注册 Skill: {name}") from exc

    def recommend(self, query: str) -> list[str]:
        normalized = query.lower()
        scored: list[tuple[int, str]] = []
        for skill in self._skills.values():
            score = sum(1 for trigger in skill.triggers if trigger.lower() in normalized)
            if score:
                scored.append((score, skill.name))
        return [name for _, name in sorted(scored, key=lambda item: (-item[0], item[1]))]

    def render_context(self, names: list[str]) -> str:
        selected = [self.get(name) for name in names if name in self._skills]
        if not selected:
            return "未匹配到专用 Skill。"
        sections = []
        for skill in selected:
            compact_body = re.sub(r"\n{3,}", "\n\n", skill.body).strip()
            sections.append(f"### {skill.name}（风险等级：{skill.risk_level}）\n{compact_body}")
        return "\n\n".join(sections)


_REGISTRY: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = SkillRegistry()
    return _REGISTRY
