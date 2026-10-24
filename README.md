# GroundTruth

Real-time flight reality assessment engine. GroundTruth predicts and assesses actual flight delays, turnaround feasibility, and tail-swap possibilities before airlines announce them.

## Monorepo Layout

```
GroundTruth/
├── backend/
│   ├── app/
│   │   ├── core/          # config.py, logging
│   │   ├── schemas/       # Shared Pydantic data contracts
│   │   ├── services/      # Service placeholders
│   │   ├── api/           # v1 router & health endpoint
│   │   └── main.py        # FastAPI entrypoint
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_schemas.py
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/              # Placeholder directory for Phase 4
├── docker-compose.yml     # Backend, Redis, Postgres
├── .env.example
├── .gitignore
├── STATE.md               # Architecture handoff & active state log
└── README.md
```

## Quickstart

### Running locally with Docker Compose

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
```

### Running unit tests

```bash
pytest -v backend/tests
```
