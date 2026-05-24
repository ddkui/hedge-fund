# shared/memory.py
import hashlib
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import List


def _hash_embedding(text: str, dim: int = 128) -> List[float]:
    """
    Deterministic local embedding: splits text into `dim` chunks and
    hashes each chunk into a float in [-1, 1]. No network or model required.
    """
    seed = text.encode("utf-8")
    result = []
    for i in range(dim):
        digest = hashlib.sha256(seed + struct.pack(">I", i)).digest()
        # Take first 4 bytes as unsigned int, normalise to [-1, 1]
        value = struct.unpack(">I", digest[:4])[0]
        result.append((value / 2**31) - 1.0)
    return result


class MemoryMixin:
    """
    Adds write_to_chroma() and write_to_obsidian() to any agent.
    Agents call these after computing a result worth remembering.
    """
    obsidian_root: str = "memory/obsidian"
    chroma_root: str = "memory/chroma"

    async def write_to_obsidian(self, title: str, body: str, tags: list[str] | None = None) -> None:
        """Write a markdown file to the Obsidian vault."""
        try:
            now = datetime.now(timezone.utc)
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H%M%S")
            agent_dir = Path(self.obsidian_root) / self.name
            agent_dir.mkdir(parents=True, exist_ok=True)

            safe_title = title[:50].replace(" ", "-").replace("/", "-").lower()
            filename = f"{date_str}-{time_str}-{safe_title}.md"
            filepath = agent_dir / filename

            tag_str = ", ".join(tags or [self.name])
            content = f"""---
title: {title}
agent: {self.name}
date: {now.isoformat()}
tags: [{tag_str}]
---

{body}
"""
            filepath.write_text(content, encoding="utf-8")
        except Exception as exc:
            self.logger.warning("obsidian_write_failed", error=str(exc))

    async def write_to_chroma(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """Store a document in ChromaDB for semantic retrieval."""
        try:
            import chromadb
            client = chromadb.PersistentClient(path=self.chroma_root)
            collection = client.get_or_create_collection(
                name=self.name,
                metadata={"hnsw:space": "cosine"},
            )
            meta = metadata or {"_source": self.name}
            collection.upsert(
                ids=[doc_id],
                embeddings=[_hash_embedding(text)],
                documents=[text],
                metadatas=[meta],
            )
        except Exception as exc:
            self.logger.warning("chroma_write_failed", error=str(exc))

    async def recall_from_chroma(self, query: str, n_results: int = 5) -> list[dict]:
        """Retrieve semantically similar past documents."""
        try:
            import chromadb
            client = chromadb.PersistentClient(path=self.chroma_root)
            collection = client.get_or_create_collection(name=self.name)
            if collection.count() == 0:
                return []
            results = collection.query(
                query_embeddings=[_hash_embedding(query)],
                n_results=min(n_results, collection.count()),
            )
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            return [{"text": d, "metadata": m} for d, m in zip(docs, metas)]
        except Exception as exc:
            self.logger.warning("chroma_recall_failed", error=str(exc))
            return []
