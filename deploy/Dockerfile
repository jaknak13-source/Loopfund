# Backend image: the multi-agent fund + FastAPI dashboard API + MCP server.
# Inference uses whichever model backend is configured in config/models.yaml
# (a local server such as LM Studio/Ollama, or any cloud provider via .env).
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY scripts/requirements.txt ./scripts/requirements.txt
RUN pip install --upgrade pip && pip install -r scripts/requirements.txt

# App code (see .dockerignore for what's excluded).
COPY . .

# Run as a non-root user. Own /app so the user can write runtime state.
RUN useradd --create-home --uid 10001 loopfund && chown -R loopfund:loopfund /app
USER loopfund

# Persisted runtime state (portfolio, blackboard DB, vector memory, logs).
VOLUME ["/app/data", "/app/logs"]

# Dashboard API (8500) and MCP streamable-HTTP (8600).
EXPOSE 8500 8600

# Binds 0.0.0.0 INSIDE the container (required to be reachable via the published
# port). Control exposure at the host: docker-compose publishes only to 127.0.0.1
# by default. Do NOT publish these ports to the internet without authentication.
# LOOPFUND_AUTOLOOP=<seconds> starts the unattended deliberation loop on boot.
ENV LOOPFUND_AUTOLOOP=3600
CMD ["uvicorn", "dashboard.api.server:build_default_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8500"]
