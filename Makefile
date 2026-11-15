.PHONY: setup migrate seed api web test test-api test-web check build e2e up down telephony-gateway telephony-tunnel

setup:
	uv venv --python 3.12 apps/api/.venv
	uv pip install --python apps/api/.venv/bin/python -r apps/api/requirements.lock.txt
	npm ci

migrate:
	cd apps/api && .venv/bin/alembic upgrade head

seed:
	cd apps/api && .venv/bin/python -m app.database.seed

api:
	cd apps/api && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --timeout-graceful-shutdown 3

web:
	cd apps/web && npm run dev -- --hostname 127.0.0.1

test-api:
	cd apps/api && .venv/bin/python -m pytest -q

test-web:
	cd apps/web && npm run test

test: test-api test-web

check:
	cd apps/web && npm run typecheck && npm run lint

build:
	cd apps/web && npm run build

e2e:
	cd apps/web && npm run test:e2e

up:
	docker compose -f infra/docker-compose.yml up --build -d

down:
	docker compose -f infra/docker-compose.yml down

# Expose this callback-only service through a development HTTPS tunnel.
telephony-gateway:
	cd apps/api && .venv/bin/uvicorn app.telephony_gateway:app --host 127.0.0.1 --port 8010 --no-access-log --timeout-graceful-shutdown 3

telephony-tunnel:
	./scripts/telephony_tunnel.sh
