# 🚨 Emergency Medical Response Platform (EMRP)

A production-grade, real-time emergency dispatch system built from scratch based on the technical report specification.

## Architecture

```
emrp/
├── backend/           # FastAPI + MongoDB + Redis + Arq
│   ├── app/
│   │   ├── core/          # Config, DB, Redis, Security, Logging
│   │   ├── models/        # Pydantic v2 schemas + MongoDB documents
│   │   ├── state_machines/ # Incident & Ambulance FSMs
│   │   ├── services/      # Business logic (incident, dispatch, audit, outbox, routing)
│   │   ├── routers/       # FastAPI route handlers (emergency, fleet, hospitals, dispatcher, auth)
│   │   ├── workers/       # Arq background tasks (outbox relay, offer sweeper, dispatch)
│   │   ├── websockets/    # WebSocket connection manager
│   │   └── main.py        # FastAPI app with lifespan
│   └── tests/
├── frontend/
│   ├── caller-pwa/    # Patient PWA (Next.js) — SOS button, live tracking
│   ├── dispatcher/    # Dispatcher Console (Next.js) — live board, fleet
│   └── hospital/      # Hospital Console (Next.js) — pre-alerts, capacity
└── infra/
    ├── docker-compose.yml  # Full stack: Mongo RS, Redis, API, Worker, Caddy
    ├── Caddyfile
    └── mongo-init/
```

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Pydantic v2 + Uvicorn |
| Database | MongoDB 7 (3-node Replica Set, 2dsphere indexes) |
| Queue | Redis + Arq (async workers) |
| Realtime | WebSockets + Redis pub/sub |
| Routing | OSRM (haversine fallback) |
| Frontend | Next.js 15 + TypeScript |
| Ingress | Caddy (TLS termination) |

## Key Design Guarantees

1. **No Silent Incident Loss** — Every SOS writes `Incident + OutboxEvent` atomically in a replica-set transaction
2. **Race-Free Dispatch** — Atomic CAS (Compare-And-Set) on ambulance status prevents double-assignment
3. **Idempotency** — Mutating endpoints require `Idempotency-Key` header; retries replay original response
4. **FSM-Validated Transitions** — All status changes validated against explicit transition tables
5. **Audit Chain** — Every state change logged with SHA-256 hash-chained entries
6. **Offer Expiry** — Sweeper task releases stale offers and re-queues incidents (default 15s)

## Quick Start (Docker)

```bash
# 1. Clone and configure
cp .env.production .env
# Edit .env: set SECRET_KEY to a random 64+ char string

# 2. Start everything
cd infra
docker-compose up -d

# 3. Wait for MongoDB replica set to initialize (~30s)
docker-compose logs -f mongo-init

# 4. Access
# API docs:        http://localhost:8000/api/docs
# Caller PWA:      http://localhost:3000
# Dispatcher:      http://localhost:3001
```

## Local Development (without Docker)

```bash
# Backend
cd backend
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# Worker (separate terminal)
python -m arq app.workers.worker.WorkerSettings

# Caller PWA (separate terminal)
cd frontend/caller-pwa
npm install
npm run dev    # http://localhost:3000

# Dispatcher (separate terminal)
cd frontend/dispatcher
npm install
npm run dev -- --port 3001   # http://localhost:3001
```

## API Reference

### Authentication
```
POST /api/v1/auth/register   — Create account
POST /api/v1/auth/token      — Login (OAuth2 password flow)
```

### Emergency SOS (Phase 1)
```
POST  /api/v1/emergency/sos          — Submit SOS (requires Idempotency-Key header)
GET   /api/v1/emergency/{id}         — Get incident status
PATCH /api/v1/emergency/{id}/status  — Manual status transition (dispatcher only)
WS    /api/v1/emergency/{id}/ws      — Live status updates
```

### Fleet Management (Phase 2)
```
POST  /api/v1/fleet/                          — Register ambulance
GET   /api/v1/fleet/                          — List fleet
PATCH /api/v1/fleet/{id}/telemetry            — Push GPS update
PATCH /api/v1/fleet/{id}/status               — Update unit status
POST  /api/v1/fleet/{id}/offers/{oid}/respond — Accept/decline offer
WS    /api/v1/fleet/{id}/ws                   — Unit live connection
```

### Hospitals & Pre-Alerts (Phase 4)
```
POST  /api/v1/hospitals/                            — Register hospital
GET   /api/v1/hospitals/                            — List hospitals
PATCH /api/v1/hospitals/{id}/capacity               — Update capacity
POST  /api/v1/hospitals/{id}/pre-alerts/{aid}/acknowledge — Acknowledge pre-alert
WS    /api/v1/hospitals/{id}/ws                     — Hospital live feed
```

### Dispatcher (Phase 4)
```
GET  /api/v1/dispatcher/incidents  — Active incident board
GET  /api/v1/dispatcher/fleet      — Full fleet view
WS   /api/v1/dispatcher/ws         — Live dispatcher feed
```

### AI Medical Triage (Phase 5 — Hugging Face Integration)
```
POST /api/v1/triage/assess         — AI symptom classification & pre-arrival protocols
                                     (Hugging Face Inference API or clinical heuristic fallback)
```

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
# 27 passed across core, fleet FSM, and AI triage test suites
```

## State Machines

### Incident Lifecycle
```
RECEIVED → VALIDATING → QUEUED → OFFERING → ASSIGNED → EN_ROUTE → ON_SCENE → TRANSPORTING → HANDED_OVER → CLOSED
                               ↓               ↓            ↓
                          NO_RESOURCE      CANCELLED   ESCALATED_MANUAL
```

### Ambulance Lifecycle
```
OFF_DUTY → AVAILABLE → OFFERED → DISPATCHED → EN_ROUTE → ON_SCENE → TRANSPORTING → HANDOVER → AVAILABLE
```

## Security

- JWT bearer tokens with role-based access (`caller`, `dispatcher`, `operator`, `unit`, `hospital_admin`, `admin`)
- Idempotency keys scoped to caller session with SHA-256 request hash deduplication
- Audit log with SHA-256 hash-chaining for tamper detection
- MongoDB replica set transactions for atomicity

## Phase Status

- ✅ Phase 0: Infrastructure (docker-compose, Mongo 3-node RS, Redis 7, Caddy proxy)
- ✅ Phase 1: Reliable Core (SOS, idempotency replay, outbox relay, FSM, audit chain)
- ✅ Phase 2: Fleet & Dispatch Engine (geo-query 2dsphere, CAS lock, offer sweeper, telemetry)
- ✅ Phase 3: Caller PWA (GPS accuracy rings, SOS button, WebSocket live tracking, fallback)
- ✅ Phase 4: Dispatcher & Hospital Consoles (live board, fleet telemetry map, pre-alerts, bed capacity)
- ✅ Phase 5: AI Medical Triage & Protocol Advisor (Hugging Face model repository + clinical heuristic fallback)
