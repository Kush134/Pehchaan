FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace/apps/api
COPY apps/api/requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY apps/api .
RUN useradd --create-home pehchaan && mkdir -p /workspace/data && chown -R pehchaan:pehchaan /workspace
USER pehchaan
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m app.database.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
