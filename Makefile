SRC=pv_site_api tests

lint:
	poetry run ruff $(SRC)
	poetry run black --check $(SRC)
	poetry run isort --check $(SRC)

format:
	poetry run ruff --fix $(SRC)
	poetry run black $(SRC)
	poetry run isort $(SRC)

test:
	poetry run pytest tests

.PHONY: lint format test
