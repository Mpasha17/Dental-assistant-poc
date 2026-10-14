"""Force the offline providers before the app is imported."""

from __future__ import annotations

import os

os.environ["LLM_PROVIDER"] = "rule"
os.environ["STT_PROVIDER"] = "mock"
os.environ["DEMO_DATE"] = "2026-10-14"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_state():
    from app.config import reset_settings
    from app.llm.router import reset_llm_router
    from app.session import session_store
    from app.tools.dictation import clear_drafts
    from app.tools.store import reset_stores

    reset_settings()
    reset_llm_router()
    reset_stores()
    session_store.clear()
    clear_drafts()
    yield
    reset_settings()
    reset_llm_router()
    reset_stores()
    session_store.clear()
    clear_drafts()


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
