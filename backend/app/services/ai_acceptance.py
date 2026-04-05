"""Universal AI field acceptance utility.

All AI enrichment results land in staging columns (ai_title, ai_description,
ai_tags, ai_attributes) and are NEVER auto-applied to the user-visible main
fields. Acceptance is always explicit: the user sends accept_ai_<field>=True
in a PATCH /products/{id} request.

ACCEPTANCE_MAP defines the complete contract:
  (accept_flag, ai_column, main_column, strategy)

Strategies:
  "set"   — copy ai_column directly to main_column
  "merge" — dict-merge ai_column into main_column (ai values win on conflict)

To add a new AI field: add a row here and nowhere else. The PATCH handler,
enrichment tasks, and schema all read from this contract.
"""

from typing import Any

# Single source of truth for every AI → main-field mapping.
ACCEPTANCE_MAP: list[tuple[str, str, str, str]] = [
    # (accept_flag,          ai_column,       main_column,  strategy)
    ("accept_ai_title",       "ai_title",       "title",      "set"),
    ("accept_ai_description", "ai_description", "body_html",  "set"),
    ("accept_ai_tags",        "ai_tags",        "tags",       "set"),
    ("accept_ai_attributes",  "ai_attributes",  "metafields", "merge"),
]

# Fields that trigger a Shopify out-of-sync when changed via acceptance
SYNC_TRIGGER_FIELDS: frozenset[str] = frozenset({"title", "body_html", "tags"})


def apply_ai_acceptance(product: Any, update_data: dict) -> set[str]:
    """Pop every accept_ai_* flag from update_data and copy AI fields to main fields.

    Args:
        product:     SQLAlchemy Product ORM instance (mutated in place).
        update_data: The mutable dict from payload.model_dump(exclude_unset=True).
                     accept_ai_* keys are removed so the generic setattr loop
                     in the caller doesn't try to write them back to the model.

    Returns:
        The set of *main* field names that were actually changed — the caller
        uses this to decide whether to mark sync_status as out_of_sync.
    """
    changed: set[str] = set()

    for accept_flag, ai_col, main_col, strategy in ACCEPTANCE_MAP:
        if not update_data.pop(accept_flag, False):
            continue

        ai_value = getattr(product, ai_col, None)
        if ai_value is None:
            continue  # nothing staged — silently skip

        if strategy == "merge":
            current = getattr(product, main_col) or {}
            merged = {**current, **ai_value}
            setattr(product, main_col, merged)
        else:
            setattr(product, main_col, ai_value)

        changed.add(main_col)

    return changed
