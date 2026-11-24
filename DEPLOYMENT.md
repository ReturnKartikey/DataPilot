# Deployment

## Docker Compose (single node)

```bash
cp .env.example .env
# edit .env as needed
docker compose up --build -d
```

Open `http://localhost:8000`. The React build is served by FastAPI from the same origin. SQLite and model artifacts persist in the `backend-data` volume.

## Before public deployment

- Terminate HTTPS at a reverse proxy/load balancer.
- Put authentication and authorization in front of every non-health endpoint. The current build is single-user and does not implement accounts or tenant isolation.
- Set `DATAPILOT_ALLOWED_HOSTS` to exact public hostnames and restrict `DATAPILOT_CORS_ORIGINS` to exact trusted browser origins.
- Set upload limits to match available memory and CPU.
- Store LLM credentials in the hosting platform's secret manager, never in Git or frontend env vars.
- Back up SQLite and artifacts; for multiple replicas migrate to PostgreSQL + object storage.
- Replace FastAPI in-process background tasks with Redis/RQ/Celery or another durable job queue.
- Run a non-root container, scan dependencies/images, and monitor resource use/logs.
- Keep Swagger docs disabled or protected in production (`DATAPILOT_ENV=production`).
- Do not load joblib artifacts uploaded by users or any untrusted party.

The provided Docker Compose setup is a single-instance deployment baseline, not a certified production/SLA setup.
