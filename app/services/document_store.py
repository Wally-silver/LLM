from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.services.datasource import SourceDocument


@dataclass
class StoreStats:
    document_count: int
    source_count: int


class DocumentStore:
    """Simple persistent document store (JSON-backed) for RAG ingest/index separation."""

    def __init__(self, storage_path: str = "data/runtime/doc_store.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._docs: dict[str, SourceDocument] = {}
        self.load()

    def load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            for item in data.get("documents", []):
                doc = SourceDocument(**item)
                self._docs[doc.doc_id] = doc
        except Exception:
            self._docs = {}

    def persist(self) -> None:
        payload = {"documents": [asdict(d) for d in self._docs.values()]}
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def upsert(self, doc: SourceDocument, overwrite: bool = True) -> bool:
        if doc.doc_id in self._docs and not overwrite:
            return False
        self._docs[doc.doc_id] = doc
        return True

    def bulk_upsert(self, docs: list[SourceDocument], overwrite: bool = True) -> dict:
        inserted = 0
        skipped = 0
        for d in docs:
            if self.upsert(d, overwrite=overwrite):
                inserted += 1
            else:
                skipped += 1
        self.persist()
        return {"inserted": inserted, "skipped": skipped, "total": len(self._docs)}

    def list_sources(self) -> list[dict]:
        return [
            {
                "doc_id": d.doc_id,
                "title": d.title,
                "source_type": d.source_type,
                "source_value": d.source_value,
                "metadata": d.metadata,
            }
            for d in self._docs.values()
        ]

    def get(self, doc_id: str) -> SourceDocument | None:
        return self._docs.get(doc_id)

    def to_index_metadata(self) -> dict[str, dict]:
        return {
            d.doc_id: {
                "doc_id": d.doc_id,
                "title": d.title,
                "source_type": d.source_type,
                "source_value": d.source_value,
                "metadata": d.metadata,
            }
            for d in self._docs.values()
        }

    def delete_by_doc_id(self, doc_id: str) -> bool:
        if doc_id not in self._docs:
            return False
        del self._docs[doc_id]
        self.persist()
        return True

    def delete_by_source(self, source_value: str) -> int:
        targets = [doc_id for doc_id, d in self._docs.items() if d.source_value == source_value]
        for doc_id in targets:
            del self._docs[doc_id]
        if targets:
            self.persist()
        return len(targets)

    def all_docs_for_index(self) -> list[tuple[str, str]]:
        return [(d.doc_id, d.text) for d in self._docs.values()]

    def stats(self) -> StoreStats:
        return StoreStats(document_count=len(self._docs), source_count=len({d.source_value for d in self._docs.values()}))
