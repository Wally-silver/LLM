from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SourceDocument:
    doc_id: str
    text: str
    source_type: str
    source_value: str


class DataSourceService:
    """Load documents from multiple datasource types."""

    def __init__(self, http_client, max_chars: int = 2_000_000):
        self.http_client = http_client
        self.max_chars = max_chars

    async def load(self, source_type: str, source_value: str, doc_id: str | None = None) -> SourceDocument:
        source_type = source_type.lower().strip()
        if source_type == "inline":
            text = source_value
        elif source_type == "file":
            text = Path(source_value).read_text(encoding="utf-8")
        elif source_type == "url":
            resp = await self.http_client.get(source_value)
            resp.raise_for_status()
            text = resp.text
        else:
            raise ValueError(f"unsupported source_type: {source_type}")

        if len(text) > self.max_chars:
            text = text[: self.max_chars]

        return SourceDocument(
            doc_id=doc_id or f"{source_type}:{hash(source_value)}",
            text=text,
            source_type=source_type,
            source_value=source_value,
        )
