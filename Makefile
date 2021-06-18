check:
	pytest -s --cov

lint:
	black --check .
	flake8
	mypy -p futured

html:
	PYTHONPATH=$(PWD) python3 -m mkdocs build
