"""
RAG (Retrieval-Augmented Generation) system using Ollama nomic-embed-text.
Retrieves relevant US architectural standards to improve floor plan generation.

Startup loads the persistent embedding cache from disk only.
Indexing missing chunks is an explicit, resume-safe operation.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from pathlib import Path
from typing import Any, Optional

import httpx

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text:latest"
KB_PATH = Path(__file__).parent / "arch_knowledge.json"
CACHE_PATH = Path(__file__).parent / "embed_cache.json"

HEALTH_TIMEOUT_S = 3.0
INDEX_EMBED_TIMEOUT_S = 30.0
RETRIEVE_TIMEOUT_S = 8.0


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b + 1e-9)


def _is_vector(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(x, (int, float)) for x in value[:8])
    )


def parse_cache(raw: Any) -> tuple[Optional[str], dict[str, list[float]], Optional[int]]:
    """Parse wrapped or legacy cache. Does not fabricate vectors."""
    if not isinstance(raw, dict) or not raw:
        return None, {}, None

    if isinstance(raw.get("embeddings"), dict):
        model = raw.get("model")
        if model is not None and not isinstance(model, str):
            model = None
        embeddings: dict[str, list[float]] = {}
        for key, value in raw["embeddings"].items():
            if _is_vector(value):
                embeddings[str(key)] = [float(x) for x in value]
        dimension = raw.get("dimension")
        if not isinstance(dimension, int) and embeddings:
            dimension = len(next(iter(embeddings.values())))
        elif not isinstance(dimension, int):
            dimension = None
        return model, embeddings, dimension

    embeddings = {}
    for key, value in raw.items():
        if key in {"model", "dimension", "embeddings"}:
            continue
        if _is_vector(value):
            embeddings[str(key)] = [float(x) for x in value]
    dimension = len(next(iter(embeddings.values()))) if embeddings else None
    return None, embeddings, dimension


def wrap_cache(
    embeddings: dict[str, list[float]],
    model: str = EMBED_MODEL,
) -> dict[str, Any]:
    dimension = None
    if embeddings:
        dimension = len(next(iter(embeddings.values())))
    return {
        "model": model,
        "dimension": dimension,
        "embeddings": embeddings,
    }


def query_from_constraints(constraints: dict) -> str:
    parts = [
        f"{constraints.get('bedrooms', 0)} bedrooms",
        f"{constraints.get('bathrooms', 0)} bathrooms",
        "living room",
        "kitchen",
    ]
    if constraints.get("homeOffice"):
        parts.append("home office")
    if constraints.get("formalDining"):
        parts.append("dining room")
    garage = constraints.get("garage") or "none"
    if garage != "none":
        parts.append(f"{garage} garage")
    outdoor = constraints.get("outdoor") or "none"
    if outdoor != "none":
        parts.append(outdoor)
    style = constraints.get("style") or "residential"
    sqft = constraints.get("sqft") or 0
    return (
        f"A residential floor plan, {style} style, {sqft} sqft, "
        + ", ".join(parts)
        + "."
    )


async def _embed(text: str, timeout: float = INDEX_EMBED_TIMEOUT_S) -> list[float]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
        )
        resp.raise_for_status()
        embedding = resp.json()["embedding"]
        if not _is_vector(embedding):
            raise ValueError("Ollama embedding response is not a numeric vector")
        return [float(x) for x in embedding]


async def ollama_reachable(timeout: float = HEALTH_TIMEOUT_S) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


class RAGSystem:
    def __init__(
        self,
        kb_path: Path = KB_PATH,
        cache_path: Path = CACHE_PATH,
    ):
        self._kb_path = Path(kb_path)
        self._cache_path = Path(cache_path)
        self._chunks: list[dict] = []
        self._embeddings: dict[str, list[float]] = {}
        self._cache_model: Optional[str] = None
        self._dimension: Optional[int] = None
        self._ready = False

    def load(self) -> dict[str, Any]:
        """Load knowledge base and cache from disk. No Ollama calls."""
        kb = json.loads(self._kb_path.read_text(encoding="utf-8"))
        self._chunks = list(kb.get("chunks") or [])
        self._embeddings = {}
        self._cache_model = None
        self._dimension = None

        if self._cache_path.exists():
            try:
                raw = json.loads(self._cache_path.read_text(encoding="utf-8") or "{}")
            except (OSError, json.JSONDecodeError):
                raw = {}
            model, embeddings, dimension = parse_cache(raw)
            if model is not None and model != EMBED_MODEL:
                print(
                    f"[RAG] Cache model {model!r} does not match {EMBED_MODEL}; "
                    "ignoring vectors until reindex."
                )
            else:
                self._cache_model = model or EMBED_MODEL
                self._embeddings = embeddings
                self._dimension = dimension

        self._ready = True
        st = self.status()
        print(
            f"[RAG] Loaded {st['total']} chunks, {st['cached']} cached embeddings "
            f"({st['state']})."
        )
        return st

    async def initialize(self) -> dict[str, Any]:
        """Backward compatible: disk load only. Does not index missing chunks."""
        return self.load()

    def _missing_chunks(self) -> list[dict]:
        return [c for c in self._chunks if c.get("id") not in self._embeddings]

    def _persist(self) -> None:
        payload = wrap_cache(self._embeddings, model=EMBED_MODEL)
        self._cache_model = payload["model"]
        self._dimension = payload["dimension"]
        self._cache_path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    async def index_missing(self) -> dict[str, Any]:
        """Embed only uncached chunks. Fail fast if Ollama is unreachable."""
        if not self._ready:
            self.load()

        missing = self._missing_chunks()
        if not missing:
            return {
                "indexed": 0,
                "missing": 0,
                "cached": len(self._embeddings),
                "stopped": False,
                "reason": "complete",
            }

        if not await ollama_reachable():
            print("[RAG] Ollama unreachable — skipping indexing.")
            return {
                "indexed": 0,
                "missing": len(missing),
                "cached": len(self._embeddings),
                "stopped": True,
                "reason": "ollama_unavailable",
            }

        indexed = 0
        print(f"[RAG] Indexing {len(missing)} missing chunks...")
        for chunk in missing:
            chunk_id = chunk.get("id")
            try:
                vec = await _embed(chunk["text"], timeout=INDEX_EMBED_TIMEOUT_S)
            except Exception as e:
                print(f"[RAG] Embed failed for {chunk_id}: {e} — stopping index.")
                return {
                    "indexed": indexed,
                    "missing": len(self._missing_chunks()),
                    "cached": len(self._embeddings),
                    "stopped": True,
                    "reason": "embed_failed",
                    "failed_id": chunk_id,
                }
            self._embeddings[str(chunk_id)] = vec
            self._persist()
            indexed += 1

        print(f"[RAG] Cached {len(self._embeddings)} embeddings.")
        return {
            "indexed": indexed,
            "missing": 0,
            "cached": len(self._embeddings),
            "stopped": False,
            "reason": "complete",
        }

    def status(self) -> dict[str, Any]:
        total = len(self._chunks)
        cached = len(self._embeddings)
        if not self._ready:
            state = "unloaded"
        elif total == 0:
            state = "unavailable"
        elif cached == 0:
            state = "unavailable"
        elif cached < total:
            state = "partial"
        else:
            state = "ready"
        dimension = self._dimension
        if dimension is None and self._embeddings:
            dimension = len(next(iter(self._embeddings.values())))
        return {
            "state": state,
            "model": self._cache_model or EMBED_MODEL,
            "cached": cached,
            "total": total,
            "dimension": dimension,
            "ready": self._ready and cached > 0,
        }

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        timeout: float = RETRIEVE_TIMEOUT_S,
    ) -> list[str]:
        """Return top-k chunks. Never indexes. Empty if cache or query embed fails."""
        if not self._ready:
            self.load()
        if not self._embeddings:
            return []

        try:
            query_vec = await _embed(query, timeout=timeout)
        except Exception:
            return []

        scored = []
        for chunk in self._chunks:
            chunk_id = chunk.get("id")
            if chunk_id in self._embeddings:
                sim = _cosine_sim(query_vec, self._embeddings[chunk_id])
                scored.append((sim, chunk["text"]))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [text for _, text in scored[:top_k]]

    async def retrieve_for_generate(self, constraints: dict, top_k: int = 5) -> dict[str, Any]:
        """Optional generate-path retrieval. Never indexes. Never raises."""
        if not self._ready:
            try:
                self.load()
            except Exception:
                return {
                    "rag_available": False,
                    "rag_reason": "cache_empty",
                    "rag_context": [],
                }
        if not self._embeddings:
            return {
                "rag_available": False,
                "rag_reason": "cache_empty",
                "rag_context": [],
            }
        try:
            hits = await self.retrieve(
                query_from_constraints(constraints),
                top_k=top_k,
                timeout=RETRIEVE_TIMEOUT_S,
            )
        except Exception:
            return {
                "rag_available": False,
                "rag_reason": "ollama_unavailable",
                "rag_context": [],
            }
        if not hits:
            return {
                "rag_available": False,
                "rag_reason": "ollama_unavailable",
                "rag_context": [],
            }
        return {
            "rag_available": True,
            "rag_reason": "ok",
            "rag_context": hits,
        }


# Singleton instance
rag = RAGSystem()


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KIYUB RAG cache tools")
    parser.add_argument("command", choices=["index", "status"])
    args = parser.parse_args(argv)
    rag.load()
    if args.command == "status":
        print(json.dumps(rag.status(), indent=2))
        return 0
    result = asyncio.run(rag.index_missing())
    print(json.dumps({"index": result, "status": rag.status()}, indent=2))
    return 0 if not result.get("stopped") or result.get("reason") == "complete" else 1


if __name__ == "__main__":
    sys.exit(_cli())
