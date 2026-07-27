.PHONY: install lint typecheck test run demo docker-up

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

demo:
	python -m app.demo

docker-up:
	docker compose up --build
