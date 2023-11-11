check:
	python -m pytest -s --cov

lint:
	black --check .
	ruff .
	mypy -p futured

html:
	PYTHONPATH=$(PWD) python -m mkdocs build
