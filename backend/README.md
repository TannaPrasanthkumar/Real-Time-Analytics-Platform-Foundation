# Real-Time Analytics Platform Backend

This directory houses the production-grade Python FastAPI backend codebase.

## Prerequisites
- Python 3.11+
- Poetry (for dependency management)
- Redis and PostgreSQL servers running

## Setup
1. Install dependencies:
   ```bash
   poetry install
   ```
2. Run development server:
   ```bash
   poetry run uvicorn app.main:app --reload
   ```
