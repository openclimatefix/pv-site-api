SRC=pv_site_api tests

.PHONY: lint
lint:
	poetry run ruff $(SRC)
	poetry run black --check $(SRC)
	poetry run isort --check $(SRC)

.PHONY: format
format:
	poetry run ruff --fix $(SRC)
	poetry run black $(SRC)
	poetry run isort $(SRC)
