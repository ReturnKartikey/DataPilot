FROM node:22-alpine AS frontend-build
WORKDIR /workspace/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATAPILOT_ENV=production \
    DATAPILOT_DATA_DIR=/var/lib/datapilot
WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /workspace/frontend/dist /app/frontend/dist
RUN mkdir -p /var/lib/datapilot && useradd --create-home --uid 10001 datapilot && chown -R datapilot:datapilot /app /var/lib/datapilot
USER datapilot
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
