"""HouseGAN checkpoint/remote availability. Does not claim untrained nets are trained."""

from __future__ import annotations

import asyncio

import httpx
import pytest
import torch

from moe.housegan.bubble_diagram import build_bubble_diagram
from moe.housegan.inference import (
    generate_layouts,
    get_housegan_status,
    remote_enabled,
    reset_housegan_runtime,
)


def _diagram():
    return build_bubble_diagram({
        "bedrooms": 1,
        "bathrooms": 1,
        "garage": "none",
        "outdoor": "none",
        "homeOffice": False,
        "primarySuite": False,
        "sqft": 800,
        "laundry": "none",
    })


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    reset_housegan_runtime()
    monkeypatch.delenv("KIYUB_HOUSEGAN_REMOTE_ENABLED", raising=False)
    yield
    reset_housegan_runtime()


def test_missing_checkpoint_unavailable_no_httpx(tmp_path, monkeypatch):
    class Boom:
        def __init__(self, *a, **k):
            raise AssertionError("httpx should not be constructed")

    monkeypatch.setattr("moe.housegan.inference.WEIGHTS_DIR", tmp_path / "empty")
    monkeypatch.setattr("moe.housegan.inference.httpx.AsyncClient", Boom)
    st = get_housegan_status()
    assert st.available is False
    assert st.source == "unavailable"
    assert st.reason == "checkpoint_missing"
    layouts = asyncio.run(generate_layouts(_diagram(), num_variants=1, mode="auto"))
    assert layouts == []
    assert remote_enabled() is False


def test_invalid_checkpoint_load_failed(tmp_path, monkeypatch):
    junk = tmp_path / "housegan_pp.pt"
    junk.write_bytes(b"not-a-pytorch-checkpoint")
    monkeypatch.setattr("moe.housegan.inference.WEIGHTS_DIR", tmp_path)
    st = get_housegan_status()
    assert st.available is False
    assert st.source == "load_failed"
    assert st.reason and st.reason.startswith("load_failed")
    layouts = asyncio.run(generate_layouts(_diagram(), num_variants=1, mode="auto"))
    assert layouts == []


def test_valid_checkpoint_path_load_attempted(tmp_path, monkeypatch):
    (tmp_path / "housegan_pp.pt").write_bytes(b"placeholder")
    monkeypatch.setattr("moe.housegan.inference.WEIGHTS_DIR", tmp_path)
    loads = {"n": 0}

    class FakeModel:
        def __call__(self, room_types, adj):
            n = int(room_types.shape[0])
            return torch.ones(n, 1, 64, 64)

    def fake_load(path, device="cpu"):
        loads["n"] += 1
        return FakeModel()

    monkeypatch.setattr("moe.housegan.model.load_pretrained", fake_load)
    st = get_housegan_status()
    assert loads["n"] == 1
    assert st.available is True
    assert st.source == "local_trained"


def test_remote_disabled_does_not_call_adapter(tmp_path, monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("remote adapter must not run")

    monkeypatch.setattr("moe.housegan.inference.WEIGHTS_DIR", tmp_path / "empty")
    monkeypatch.setattr("moe.housegan.inference._run_remote", boom)
    layouts = asyncio.run(generate_layouts(_diagram(), num_variants=1, mode="auto"))
    assert layouts == []


def test_remote_404_not_retried(tmp_path, monkeypatch):
    monkeypatch.setattr("moe.housegan.inference.WEIGHTS_DIR", tmp_path / "empty")
    monkeypatch.setenv("KIYUB_HOUSEGAN_REMOTE_ENABLED", "1")
    calls = {"n": 0}

    async def fail_remote(*a, **k):
        calls["n"] += 1
        req = httpx.Request("POST", "https://buildify-housegan.hf.space/api/predict")
        resp = httpx.Response(404, request=req)
        raise httpx.HTTPStatusError("404", request=req, response=resp)

    monkeypatch.setattr("moe.housegan.inference._run_remote", fail_remote)
    d = _diagram()
    a = asyncio.run(generate_layouts(d, num_variants=1, mode="auto"))
    b = asyncio.run(generate_layouts(d, num_variants=1, mode="auto"))
    assert a == []
    assert b == []
    assert calls["n"] == 1
    st = get_housegan_status()
    assert st.available is False
    assert st.reason == "remote_unavailable"
