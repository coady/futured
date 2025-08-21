check:
	uv run pytest -s --cov

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run ty check futured

html:
	uv run --with futured mkdocs build
