"""Load the loan-policy markdown corpus.

Each file under `data/policies/` is parsed into a `PolicyDoc` with its YAML
front-matter as metadata. The vector-store builder consumes these.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.utils import project_path


@dataclass
class PolicyDoc:
    policy_id: str
    section: str
    text: str
    metadata: dict

    def langchain_document(self):
        from langchain_core.documents import Document

        return Document(page_content=self.text, metadata=self.metadata)


def _split_frontmatter(raw: str) -> tuple[dict, str]:
    if raw.startswith("---\n"):
        _, fm, body = raw.split("---", 2)
        return yaml.safe_load(fm), body.strip()
    return {}, raw.strip()


def load_corpus(policy_dir: Path | None = None) -> list[PolicyDoc]:
    policy_dir = policy_dir or project_path("data/policies")
    docs: list[PolicyDoc] = []
    for path in sorted(policy_dir.glob("*.md")):
        front, body = _split_frontmatter(path.read_text(encoding="utf-8"))
        meta = {
            "policy_id": front.get("policy_id", path.stem),
            "section": front.get("section", path.stem),
            "source": str(path.relative_to(project_path("."))).replace("\\", "/"),
            "last_reviewed": str(front.get("last_reviewed", "")),
            "owner": front.get("owner", ""),
        }
        docs.append(
            PolicyDoc(
                policy_id=meta["policy_id"],
                section=meta["section"],
                text=body,
                metadata=meta,
            )
        )
    return docs
