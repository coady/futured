check:
	python -m pytest -s --cov

lint:
	ruff .
	ruff format --check .
	mypy -p futured

html:
	PYTHONPATH=$(PWD) python -m mkdocs build
