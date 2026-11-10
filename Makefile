SRC=pv_site_api tests

lint:
	uv run ruff check $(SRC)
	uv run black --check $(SRC)
	uv run isort --check $(SRC)

format:
	uv run ruff check --fix $(SRC)
	uv run black $(SRC)
	uv run isort $(SRC)

test:
	uv run pytest tests

.PHONY: lint format test
