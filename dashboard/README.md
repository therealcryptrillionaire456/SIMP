# SIMP Monitoring Dashboard

Public read-only monitoring dashboard for the SIMP broker. Displays broker health, registered agents, capability maps, and an activity feed — all through safe, GET-only API routes.

## Quick Start

```bash
# Install dependencies (if not already installed)
pip install fastapi uvicorn httpx

# Start the dashboard (broker should be running on port 5555)
python dashboard/server.py
```

The dashboard will be available at **http://localhost:8050**.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SIMP_BROKER_URL` | `http://127.0.0.1:5555` | URL of the SIMP broker to proxy |
| `DASHBOARD_HOST` | `0.0.0.0` | Host to bind the dashboard server |
| `DASHBOARD_PORT` | `8050` | Port for the dashboard server |
| `POLL_INTERVAL` | `5` | Seconds between broker polls for activity detection |

## API Routes

All routes are **GET-only**. There are no POST, PUT, PATCH, or DELETE endpoints.

| Route | Description |
|---|---|
| `GET /` | Serves the dashboard frontend |
| `GET /api/health` | Broker health status |
| `GET /api/stats` | Broker statistics (intents received, routed, failed, etc.) |
| `GET /api/agents` | Registered agents with capabilities (endpoints redacted) |
| `GET /api/activity` | Recent activity feed from in-memory ring buffer |
| `GET /api/capabilities` | Capability map — which agents handle which capabilities |
| `GET /api/topology` | Network topology data (agents and connection modes) |

## Security

- **Read-only**: No write-capable routes are exposed
- **No secrets**: API keys, tokens, and credentials are stripped from all responses
- **No endpoints**: Actual agent URLs are replaced with mode indicators (`http` / `file-based`)
- **No file paths**: Local filesystem paths are removed from responses
- **No prompts**: Raw prompt bodies are never included in responses
- **No admin actions**: Cannot register, delete, pause, or send intents through the dashboard

## Reverse Proxy Setup

### Nginx

```nginx
server {
    listen 80;
    server_name simp-dashboard.example.com;

    location / {
        proxy_pass http://127.0.0.1:8050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Caddy

```
simp-dashboard.example.com {
    reverse_proxy 127.0.0.1:8050
}
```

## Architecture

```
dashboard/
  server.py            # FastAPI read-only adapter (port 8050)
  static/
    index.html         # Dashboard SPA
    style.css          # Dark theme styles
    app.js             # Frontend logic (vanilla JS)
  activity_log.jsonl   # Persistent activity log (auto-created)
  README.md            # This file
```

The dashboard server proxies requests to the SIMP broker (port 5555), redacts sensitive data, and serves the static frontend. A background poller detects broker state changes and records them in an in-memory ring buffer (last 100 events), optionally persisted to `activity_log.jsonl`.

If the broker is unreachable, the dashboard displays a clear "Broker Unreachable" state and continues polling until the broker becomes available.
