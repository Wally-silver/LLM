import asyncio
from pathlib import Path

from app.services.datasource import DataSourceService


class DummyHTTPClient:
    async def get(self, _url: str):
        raise RuntimeError("not used in this test")


def test_inline_source():
    async def _run():
        service = DataSourceService(http_client=DummyHTTPClient())
        doc = await service.load("inline", "hello world", doc_id="d1")
        assert doc.doc_id == "d1"
        assert doc.text == "hello world"

    asyncio.run(_run())


def test_file_source(tmp_path: Path):
    async def _run():
        f = tmp_path / "a.txt"
        f.write_text("abc", encoding="utf-8")
        service = DataSourceService(http_client=DummyHTTPClient())
        doc = await service.load("file", str(f), doc_id="d2")
        assert doc.text == "abc"

    asyncio.run(_run())
