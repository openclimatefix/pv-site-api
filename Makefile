SRC=pv_site_api tests

lint:
	uvx ruff check $(SRC)
	uv run black --check $(SRC)
	uv run isort --check $(SRC)

format:
	uvx ruff check --fix $(SRC)
	uv run black $(SRC)
	uv run isort $(SRC)

test:
	uv run pytest tests

.PHONY: lint format test
