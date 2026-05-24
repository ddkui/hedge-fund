# tests/shared/test_memory.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os


@pytest.mark.asyncio
async def test_write_to_obsidian_creates_file(tmp_path):
    from shared.memory import MemoryMixin
    mixin = MemoryMixin.__new__(MemoryMixin)
    mixin.name = "test_agent"
    mixin.obsidian_root = str(tmp_path)
    mixin.logger = MagicMock()
    await mixin.write_to_obsidian(
        title="Test Signal",
        body="AAPL is bullish.",
        tags=["test", "aapl"],
    )
    files = list(tmp_path.glob("**/*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "AAPL is bullish." in content
    assert "tags: [test, aapl]" in content


@pytest.mark.asyncio
async def test_write_to_chroma_adds_document(tmp_path):
    from shared.memory import MemoryMixin
    mixin = MemoryMixin.__new__(MemoryMixin)
    mixin.name = "test_agent"
    mixin.chroma_root = str(tmp_path)
    mixin.logger = MagicMock()
    await mixin.write_to_chroma(
        doc_id="aapl-bullish-001",
        text="AAPL is bullish based on RSI and MACD.",
        metadata={"symbol": "AAPL", "agent": "test"},
    )
    # Verify collection was created and has 1 document
    import chromadb
    client = chromadb.PersistentClient(path=str(tmp_path))
    col = client.get_collection("test_agent")
    assert col.count() == 1
