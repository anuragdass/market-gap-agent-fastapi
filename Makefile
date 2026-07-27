.PHONY: install lint typecheck test run docker-up migrate migration

install:
	pip install -e ".[dev]"

lint:
	ruff check app tests

typecheck:
	mypy app

test:
	pytest -q

run:
	uvicorn app.main:app --reload

# Primary way to use the agent: `make docker-up`, then open http://localhost:8000
# and submit the form (or POST to /api/v1/runs directly). There is no CLI/script
# entrypoint -- the web UI and API are the only interface.
docker-up:
	docker compose up --build

# Run after `docker-up` (once, and again after pulling new migrations):
#   make migrate
migrate:
	docker compose exec api alembic upgrade head

# Generate a new migration after changing app/db/models.py:
#   make migration name="add foo column"
migration:
	docker compose exec api alembic revision --autogenerate -m "$(name)"
