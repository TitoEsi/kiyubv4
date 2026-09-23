"""RAG cache load/index/retrieve — no live Ollama required."""
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

import rag as rag_mod
from rag import RAGSystem, parse_cache, query_from_constraints, wrap_cache

LIVE = {
    "lotShape": "rectangle",
    "lotWidth": 20.0,
    "lotDepth": 30.0,
    "bedrooms": 2,
    "bathrooms": 2,
    "sqft": 1800,
    "stories": 1,
    "style": "modern",
    "openPlan": False,
    "primarySuite": True,
    "homeOffice": True,
    "formalDining": False,
    "garage": "2car",
    "laundry": "room",
    "outdoor": "patio",
    "ceilingHeight": "standard",
}

TINY_KB = {
    "chunks": [
        {"id": "kit", "category": "kitchen", "text": "Kitchen should be adjacent to dining."},
        {"id": "gar", "category": "garage", "text": "Garage belongs at the front of the house."},
        {"id": "bed", "category": "bedroom", "text": "Bedrooms cluster in a quiet wing."},
    ]
}


def _vec(text: str) -> list[float]:
    v = [0.0] * 8
    if "Kitchen" in text or "kitchen" in text.lower() or "dining" in text.lower():
        v[0] = 1.0
    elif "Garage" in text or "garage" in text.lower():
        v[1] = 1.0
    else:
        v[2] = 1.0
    return v


def _write_kb(path: Path) -> Path:
    path.write_text(json.dumps(TINY_KB), encoding="utf-8")
    return path


def _system(tmp_path: Path, cache_payload=None) -> RAGSystem:
    kb = _write_kb(tmp_path / "arch_knowledge.json")
    cache = tmp_path / "embed_cache.json"
    if cache_payload is not None:
        cache.write_text(json.dumps(cache_payload), encoding="utf-8")
    return RAGSystem(kb_path=kb, cache_path=cache)


class _Client:
    gets = 0
    posts = 0
    fail_health = False
    fail_post = False
    post_prompts: list[str] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kwargs):
        _Client.gets += 1
        if _Client.fail_health:
            raise httpx.ConnectError("Connection refused")
        resp = MagicMock()
        resp.status_code = 200
        return resp

    async def post(self, url, json=None, **kwargs):
        _Client.posts += 1
        if _Client.fail_post:
            raise httpx.ConnectError("Connection refused")
        prompt = (json or {}).get("prompt", "")
        _Client.post_prompts.append(prompt)
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = lambda: None
        resp.json = lambda: {"embedding": _vec(prompt)}
        return resp


@pytest.fixture
def httpx_client(monkeypatch):
    _Client.gets = 0
    _Client.posts = 0
    _Client.fail_health = False
    _Client.fail_post = False
    _Client.post_prompts = []
    monkeypatch.setattr(rag_mod.httpx, "AsyncClient", _Client)
    return _Client


def test_parse_legacy_cache_without_model_metadata():
    raw = {"kit": [0.1, 0.2], "gar": [0.3, 0.4]}
    model, embeddings, dimension = parse_cache(raw)
    assert model is None
    assert set(embeddings) == {"kit", "gar"}
    assert dimension == 2


def test_parse_wrapped_cache():
    raw = wrap_cache({"kit": [1.0, 2.0, 3.0]}, model="nomic-embed-text:latest")
    model, embeddings, dimension = parse_cache(raw)
    assert model == "nomic-embed-text:latest"
    assert embeddings["kit"] == [1.0, 2.0, 3.0]
    assert dimension == 3


def test_empty_cache_load_does_not_embed(tmp_path, httpx_client):
    system = _system(tmp_path, cache_payload={})
    st = system.load()
    assert st["state"] == "unavailable"
    assert st["cached"] == 0
    assert st["total"] == 3
    assert httpx_client.posts == 0
    assert httpx_client.gets == 0
    hits = asyncio.run(system.retrieve("kitchen dining"))
    assert hits == []
    assert httpx_client.posts == 0


def test_initialize_is_disk_only(tmp_path, httpx_client):
    system = _system(tmp_path, cache_payload={})
    asyncio.run(system.initialize())
    assert httpx_client.posts == 0
    assert httpx_client.gets == 0
    assert system.status()["cached"] == 0


def test_partial_cache_indexes_only_missing(tmp_path, httpx_client):
    partial = wrap_cache(
        {"kit": _vec("Kitchen should be adjacent to dining.")},
        model="nomic-embed-text:latest",
    )
    system = _system(tmp_path, cache_payload=partial)
    system.load()
    assert system.status()["state"] == "partial"
    result = asyncio.run(system.index_missing())
    assert result["indexed"] == 2
    assert result["missing"] == 0
    assert result["cached"] == 3
    assert httpx_client.posts == 2
    saved = json.loads(system._cache_path.read_text(encoding="utf-8"))
    assert saved["model"] == "nomic-embed-text:latest"
    assert set(saved["embeddings"]) == {"kit", "gar", "bed"}


def test_complete_cache_load_makes_no_embed_requests(tmp_path, httpx_client):
    complete = wrap_cache(
        {c["id"]: _vec(c["text"]) for c in TINY_KB["chunks"]},
        model="nomic-embed-text:latest",
    )
    system = _system(tmp_path, cache_payload=complete)
    st = system.load()
    assert st["state"] == "ready"
    assert st["cached"] == 3
    result = asyncio.run(system.index_missing())
    assert result["indexed"] == 0
    assert result["reason"] == "complete"
    assert httpx_client.posts == 0
    assert httpx_client.gets == 0


def test_ollama_unavailable_fail_fast(tmp_path, httpx_client):
    httpx_client.fail_health = True
    system = _system(tmp_path, cache_payload={})
    system.load()
    result = asyncio.run(system.index_missing())
    assert result["stopped"] is True
    assert result["reason"] == "ollama_unavailable"
    assert result["indexed"] == 0
    assert result["missing"] == 3
    assert httpx_client.gets == 1
    assert httpx_client.posts == 0
    assert system.status()["state"] == "unavailable"


def test_retrieve_uses_cached_chunks_and_one_query_embed(tmp_path, httpx_client):
    complete = wrap_cache(
        {c["id"]: _vec(c["text"]) for c in TINY_KB["chunks"]},
        model="nomic-embed-text:latest",
    )
    system = _system(tmp_path, cache_payload=complete)
    system.load()
    httpx_client.posts = 0
    hits = asyncio.run(system.retrieve("kitchen adjacent to dining room"))
    assert httpx_client.posts == 1
    assert hits
    assert "Kitchen" in hits[0]
    assert len(hits) <= 3


def test_legacy_cache_is_not_invalidated(tmp_path, httpx_client):
    legacy = {c["id"]: _vec(c["text"]) for c in TINY_KB["chunks"]}
    system = _system(tmp_path, cache_payload=legacy)
    st = system.load()
    assert st["state"] == "ready"
    assert st["cached"] == 3
    assert httpx_client.posts == 0


def test_model_mismatch_ignores_vectors(tmp_path, httpx_client):
    payload = wrap_cache(
        {c["id"]: _vec(c["text"]) for c in TINY_KB["chunks"]},
        model="other-embed:latest",
    )
    system = _system(tmp_path, cache_payload=payload)
    st = system.load()
    assert st["cached"] == 0
    assert st["state"] == "unavailable"
    assert system._cache_path.exists()


def test_startup_and_generate_do_not_index():
    import main as main_mod

    startup = inspect.getsource(main_mod.startup_event)
    generate = inspect.getsource(main_mod.generate_moe)
    assert "rag.load()" in startup
    assert "index_missing" not in startup
    assert "initialize" not in startup
    assert "index_missing" not in generate
    assert "retrieve_for_generate" in generate


@pytest.fixture(scope="module")
def generated_plan():
    from moe.inference import predict_floor_plan
    from solver.pipeline import refine_generation

    result = refine_generation(LIVE, predict_floor_plan(LIVE, num_variants=1))
    return result


def test_generation_with_rag_unavailable(generated_plan, tmp_path, httpx_client):
    assert generated_plan["status"] == "valid"
    assert generated_plan["plans"]
    system = _system(tmp_path, cache_payload={})
    system.load()
    meta = asyncio.run(system.retrieve_for_generate(LIVE))
    assert meta["rag_available"] is False
    assert meta["rag_reason"] == "cache_empty"
    assert meta["rag_context"] == []
    combined = {**generated_plan, **meta}
    assert combined["status"] == "valid"
    assert combined["rag_available"] is False
    assert httpx_client.posts == 0


def test_generation_with_rag_available(generated_plan, tmp_path, httpx_client):
    assert generated_plan["status"] == "valid"
    complete = wrap_cache(
        {c["id"]: _vec(c["text"]) for c in TINY_KB["chunks"]},
        model="nomic-embed-text:latest",
    )
    system = _system(tmp_path, cache_payload=complete)
    system.load()
    meta = asyncio.run(system.retrieve_for_generate(LIVE))
    assert meta["rag_available"] is True
    assert meta["rag_reason"] == "ok"
    assert meta["rag_context"]
    combined = {**generated_plan, **meta}
    assert combined["status"] == "valid"
    assert combined["rag_available"] is True
    assert httpx_client.posts == 1


def test_query_from_constraints_mentions_program():
    q = query_from_constraints(LIVE)
    assert "2 bedrooms" in q
    assert "office" in q
    assert "garage" in q
    assert "kitchen" in q
