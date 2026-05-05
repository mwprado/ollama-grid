# OllamaGrid Router

`ollama-grid-router` is the first resource-aware routing layer for OllamaGrid.

It is intentionally small and currently uses only the Go standard library. This keeps the first implementation easy to build, audit, and package as an RPM later.

## Current scope

- Reads backend definitions from `config.example.json`.
- Periodically checks each backend using `/api/version`.
- Proxies normal Ollama API requests to one healthy backend.
- Selects the backend using a simple least-cost score.
- Supports volatile session affinity using the `X-Ollama-Grid-Session` header.
- Exposes `/healthz` and `/routes` for inspection.

No database is used yet. Session affinity is in memory and disappears when the router restarts.

## Build

From this directory:

```bash
go build -o ollama-grid-router .
```

## Run

```bash
./ollama-grid-router -config config.example.json
```

By default, the example configuration listens on:

```text
127.0.0.1:8090
```

## Inspect router health

```bash
curl -s http://127.0.0.1:8090/healthz
curl -s http://127.0.0.1:8090/routes
```

## Proxy to Ollama

```bash
curl -s http://127.0.0.1:8090/api/version
```

## Session affinity

The first request with a session header selects a backend. Later requests using the same session header try to stay on the same backend while it remains healthy.

```bash
curl -s \
  -H 'X-Ollama-Grid-Session: demo-session-1' \
  http://127.0.0.1:8090/api/version
```

## Scoring rule

The first implementation uses:

```text
score = active_requests / backend_weight + healthcheck_latency_ms / 1000
```

The lowest score wins.

This is deliberately simple. Later versions should incorporate:

- queued tokens;
- model already loaded;
- free VRAM/RAM;
- tokens per second;
- recent error rate;
- per-model backend eligibility;
- persistent session affinity using SQLite/PostgreSQL/Redis.

## Intended evolution

```text
v1: healthcheck + weighted least-active routing + volatile session affinity
v2: persistent sessions and routing decisions
v3: node telemetry and model-aware routing
v4: distributed multi-host OllamaGrid
```
