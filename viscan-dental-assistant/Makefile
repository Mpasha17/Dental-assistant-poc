.PHONY: install run test demo

PY ?= python3
VENV ?= .venv
BIN = $(VENV)/bin

install:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt

run:
	LLM_PROVIDER=$${LLM_PROVIDER:-rule} STT_PROVIDER=$${STT_PROVIDER:-mock} \
		$(BIN)/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

test:
	LLM_PROVIDER=rule STT_PROVIDER=mock DEMO_DATE=2026-10-14 $(BIN)/pytest -q

demo:
	LLM_PROVIDER=rule STT_PROVIDER=mock DEMO_DATE=2026-10-14 $(BIN)/python scripts/capture_demo.py
