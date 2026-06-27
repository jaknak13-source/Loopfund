# Deploying loopfund with Docker

loopfund runs on any Docker host: a local machine, a VPS, or a cloud VM. There is
nothing provider-specific in the images.

## Images and services

- `deploy/Dockerfile` builds the Python backend (the multi-agent loop + dashboard
  API).
- `deploy/Dockerfile.web` + `deploy/nginx.conf` build an nginx image that serves
  the built React dashboard and proxies `/api` (and `/mcp`) to the backend.
- `deploy/docker-compose.yml` wires the services together: `backend`, an optional
  `mcp` server, and `web`.

## Quick start

Run from the repo root:

```bash
cp .env.example .env   # then edit .env (see below)
docker compose -f deploy/docker-compose.yml up --build
```

The dashboard is served by the `web` service on port 80; map it to whatever host
port you want in `deploy/docker-compose.yml` (for example `8080:80`). The backend
exposes the REST API used by the dashboard.

## Single-port alternative

The backend can also serve the built dashboard itself on one port, without the
separate `web`/nginx service:

```bash
./start.sh
```

This is convenient for local runs. For a multi-service deployment, prefer nginx in
front via `docker compose`.

## Configuration

Set the model backend and any API keys through environment variables or the `.env`
file (referenced by `env_file:` in the compose file). See `.env.example` for the
available variables and placeholder values. Do not commit real secrets.

## Unattended operation

Set `LOOPFUND_AUTOLOOP=<seconds>` to have the backend run a research/decision cycle
on that interval without manual triggering (for example `3600` for hourly). Leave
it unset to run cycles only on demand.

## Notes

- The system starts and stays in dry mode; live execution requires an explicit
  opt-in (see `docs/STRATEGY.md`).
- Persist `data/` and `logs/` via volumes (the compose file already does) so state
  survives restarts.
