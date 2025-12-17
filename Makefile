check:
	uv run pytest -s --cov

lint:
	uvx ruff check
	uvx ruff format --check
	uvx ty check futured

html:
	uv run --group docs mkdocs build
