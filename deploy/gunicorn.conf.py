"""Gunicorn production config for SipSense API."""

import multiprocessing

# Bind to localhost — nginx will proxy to this
bind = "127.0.0.1:8000"

# Workers: t3.micro only has ~1GB RAM. With PyTorch loaded, each worker
# uses ~350MB, so 2 workers is the safe maximum.
workers = 2

# Use uvicorn's ASGI worker for FastAPI
worker_class = "uvicorn.workers.UvicornWorker"

# Timeout: 120s for slow ML inference or Claude API calls
timeout = 120

# Graceful restart timeout
graceful_timeout = 30

# Log to stdout/stderr (systemd captures it via journald)
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Preload the app so the PyTorch model is loaded once, shared across workers
preload_app = True

# Restart workers after this many requests to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50
