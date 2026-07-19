import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from open_notebook.research_skills.models import (
    LoadedResearchSkill,
    ResearchSkillSummary,
)

MAX_SKILL_BODY_CHARS = 8000
EXPECTED_SKILL_FILES = {"manifest.json", "SKILL.md"}
KNOWN_RESEARCH_TOOLS = {
    "list_notebook_sources",
    "search_notebook_evidence",
    "read_source",
    "read_note",
    "discover_across_notebooks",
    "tavily_search",
    "list_scientific_databases",
    "search_scientific_database",
    "fetch_scientific_record",
}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
BLOCKED_CONTENT_PATTERNS = (
    re.compile(r"ignore .{0,80}(previous|prior|system|developer).{0,40}instructions?", re.I),
    re.compile(r"(always|must always).{0,40}(run|invoke|load|use).{0,30}skill", re.I),
    re.compile(r"\b(pip|npm|yarn|pnpm|uv)\s+(install|add)\b", re.I),
    re.compile(r"\b(shell|bash|zsh|powershell)\b", re.I),
    re.compile(r"\b(payment|purchase|billing|charge a card)\b", re.I),
    re.compile(r"\b(password|credential|api key|access token|secret key)\b", re.I),
    re.compile(r"(write|modify|delete|overwrite).{0,50}(notebook|source|note)", re.I),
    re.compile(r"忽略.{0,40}(指令|提示词|系统消息)"),
    re.compile(r"(强制|始终).{0,20}(调用|加载|使用).{0,20}技能"),
    re.compile(r"(安装依赖|执行.{0,10}(脚本|命令)|读取.{0,20}(密钥|凭据))"),
    re.compile(r"(修改|删除|覆盖).{0,30}(笔记本|来源|笔记)"),
)


class ResearchSkillValidationError(ValueError):
    pass


class ResearchSkillRegistry:
    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = skills_dir or Path(__file__).parent / "skills"
        self._skills: dict[str, LoadedResearchSkill] | None = None

    def catalog(self) -> tuple[ResearchSkillSummary, ...]:
        skills = self._validated_skills()
        return tuple(
            item.summary
            for item in sorted(skills.values(), key=lambda item: item.summary.order)
        )

    def load(self, skill_id: str) -> LoadedResearchSkill:
        skill = self._validated_skills().get(skill_id)
        if skill is None:
            raise ResearchSkillValidationError(f"Unknown research skill: {skill_id}")
        return skill

    def load_many(
        self, skill_ids: list[str] | tuple[str, ...]
    ) -> tuple[LoadedResearchSkill, ...]:
        if len(skill_ids) != len(set(skill_ids)):
            raise ResearchSkillValidationError("Research skill IDs must be unique")
        return tuple(self.load(skill_id) for skill_id in skill_ids)

    def validate_ids(
        self, skill_ids: list[str] | tuple[str, ...]
    ) -> tuple[str, ...]:
        return tuple(item.summary.id for item in self.load_many(skill_ids))

    def _validated_skills(self) -> dict[str, LoadedResearchSkill]:
        if self._skills is None:
            self._skills = self._read_and_validate()
        return self._skills

    def _read_and_validate(self) -> dict[str, LoadedResearchSkill]:
        if not self.skills_dir.is_dir():
            raise ResearchSkillValidationError(
                f"Research skill directory does not exist: {self.skills_dir}"
            )
        root_entries = list(self.skills_dir.iterdir())
        if any(not path.is_dir() or path.is_symlink() for path in root_entries):
            raise ResearchSkillValidationError(
                "Research skills root may contain only real skill directories"
            )
        result: dict[str, LoadedResearchSkill] = {}
        orders: set[int] = set()
        for skill_dir in sorted(root_entries):
            entries = {path.name for path in skill_dir.iterdir()}
            if entries != EXPECTED_SKILL_FILES:
                raise ResearchSkillValidationError(
                    f"{skill_dir.name} must contain only manifest.json and SKILL.md"
                )
            if any(path.is_symlink() for path in skill_dir.iterdir()):
                raise ResearchSkillValidationError(
                    f"{skill_dir.name} may not contain symbolic links"
                )
            manifest = self._read_manifest(skill_dir / "manifest.json")
            skill = self._validate_skill(skill_dir, manifest)
            if skill.summary.id in result:
                raise ResearchSkillValidationError(
                    f"Duplicate research skill ID: {skill.summary.id}"
                )
            if skill.summary.order in orders:
                raise ResearchSkillValidationError(
                    f"Duplicate research skill order: {skill.summary.order}"
                )
            result[skill.summary.id] = skill
            orders.add(skill.summary.order)
        if len(result) != 10:
            raise ResearchSkillValidationError(
                f"Expected exactly 10 approved research skills, found {len(result)}"
            )
        return result

    @staticmethod
    def _read_manifest(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ResearchSkillValidationError(
                f"Invalid research skill manifest: {path}"
            ) from exc
        if not isinstance(value, dict):
            raise ResearchSkillValidationError(f"Manifest must be an object: {path}")
        return value

    @staticmethod
    def _required_text(manifest: dict[str, Any], field: str) -> str:
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ResearchSkillValidationError(
                f"Research skill manifest field {field} must be non-empty text"
            )
        return value.strip()

    def _validate_skill(
        self, skill_dir: Path, manifest: dict[str, Any]
    ) -> LoadedResearchSkill:
        expected_fields = {
            "id",
            "name",
            "version",
            "category",
            "description",
            "source",
            "license",
            "review_status",
            "allowed_tools",
            "order",
            "content_sha256",
        }
        if set(manifest) != expected_fields:
            raise ResearchSkillValidationError(
                f"{skill_dir.name} manifest fields do not match the approved schema"
            )
        skill_id = self._required_text(manifest, "id")
        version = self._required_text(manifest, "version")
        if skill_id != skill_dir.name or not ID_PATTERN.fullmatch(skill_id):
            raise ResearchSkillValidationError(f"Invalid research skill ID: {skill_id}")
        if not VERSION_PATTERN.fullmatch(version):
            raise ResearchSkillValidationError(
                f"Invalid research skill version: {version}"
            )
        if self._required_text(manifest, "review_status") != "approved":
            raise ResearchSkillValidationError(f"{skill_id} is not approved")
        if self._required_text(manifest, "license") != "MIT":
            raise ResearchSkillValidationError(f"{skill_id} must use the MIT license")

        allowed_tools = manifest.get("allowed_tools")
        if (
            not isinstance(allowed_tools, list)
            or not all(isinstance(item, str) for item in allowed_tools)
            or len(allowed_tools) != len(set(allowed_tools))
        ):
            raise ResearchSkillValidationError(
                f"{skill_id} allowed_tools must be a unique string list"
            )
        unknown_tools = set(allowed_tools) - KNOWN_RESEARCH_TOOLS
        if unknown_tools:
            raise ResearchSkillValidationError(
                f"{skill_id} references unknown tools: {sorted(unknown_tools)}"
            )
        order = manifest.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise ResearchSkillValidationError(f"{skill_id} order must be positive")

        content = (skill_dir / "SKILL.md").read_text(encoding="utf-8").strip()
        if not content or len(content) > MAX_SKILL_BODY_CHARS:
            raise ResearchSkillValidationError(
                f"{skill_id} content must be 1-{MAX_SKILL_BODY_CHARS} characters"
            )
        model_visible_text = "\n".join(
            [
                content,
                self._required_text(manifest, "name"),
                self._required_text(manifest, "category"),
                self._required_text(manifest, "description"),
                self._required_text(manifest, "source"),
            ]
        )
        for pattern in BLOCKED_CONTENT_PATTERNS:
            if pattern.search(model_visible_text):
                raise ResearchSkillValidationError(
                    f"{skill_id} contains blocked instruction pattern"
                )
        expected_hash = self._required_text(manifest, "content_sha256")
        actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if not SHA256_PATTERN.fullmatch(expected_hash) or expected_hash != actual_hash:
            raise ResearchSkillValidationError(
                f"{skill_id} content checksum does not match its manifest"
            )

        summary = ResearchSkillSummary(
            id=skill_id,
            name=self._required_text(manifest, "name"),
            version=version,
            category=self._required_text(manifest, "category"),
            description=self._required_text(manifest, "description"),
            source=self._required_text(manifest, "source"),
            license=self._required_text(manifest, "license"),
            review_status=self._required_text(manifest, "review_status"),
            allowed_tools=tuple(allowed_tools),
            order=order,
        )
        return LoadedResearchSkill(summary=summary, content=content)


@lru_cache(maxsize=1)
def get_research_skill_registry() -> ResearchSkillRegistry:
    return ResearchSkillRegistry()
