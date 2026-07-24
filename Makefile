.PHONY: lint format test run

lint:
	poetry run ruff check .

format:
	poetry run ruff format .
	poetry run ruff check . --fix

test:
	poetry run pytest

run:
	poetry run uvicorn app.main:app --reload
