from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ResearchSkillSummary:
    id: str
    name: str
    version: str
    category: str
    description: str
    source: str
    license: str
    review_status: str
    allowed_tools: tuple[str, ...]
    order: int

    def as_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["allowed_tools"] = list(self.allowed_tools)
        return value


@dataclass(frozen=True)
class LoadedResearchSkill:
    summary: ResearchSkillSummary
    content: str

    def as_dict(self) -> dict[str, object]:
        return {
            **self.summary.as_dict(),
            "content": self.content,
        }
