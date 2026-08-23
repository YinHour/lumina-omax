"""
Redaction rule domain model for the egress redaction gateway.

Each record is one dictionary entry of the "出网脱敏透明网关": a sensitive
original term (company name, person name, well id, ...) and the stable alias
that replaces it in every prompt that leaves the deployment for external LLM
providers. Aliases are never reassigned once created.

Records are created either manually by an administrator (source="manual") or
automatically by the regex auto-detection layer (source="auto"). Disabled
records keep their original unmasked on egress (admin intent wins over the
built-in regex patterns).
"""

from typing import ClassVar, Optional

from open_notebook.domain.base import ObjectModel

CATEGORY_COMPANY = "company"
CATEGORY_ADDRESS = "address"
CATEGORY_PERSON = "person"
CATEGORY_PHONE = "phone"
CATEGORY_WELL = "well"
CATEGORY_PRODUCT = "product"
CATEGORY_CUSTOM = "custom"

CATEGORIES = (
    CATEGORY_COMPANY,
    CATEGORY_ADDRESS,
    CATEGORY_PERSON,
    CATEGORY_PHONE,
    CATEGORY_WELL,
    CATEGORY_PRODUCT,
    CATEGORY_CUSTOM,
)


class RedactionRule(ObjectModel):
    """A single egress-redaction dictionary entry (original -> alias)."""

    table_name: ClassVar[str] = "redaction_rule"
    nullable_fields: ClassVar[set[str]] = {"note"}

    original: str
    alias: str
    category: str = CATEGORY_CUSTOM
    enabled: bool = True
    source: str = "manual"
    note: Optional[str] = None
