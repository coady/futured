check:
	pytest --cov

lint:
	python3 setup.py check -ms
	black --check .
	flake8
	mypy -p futured

html:
	PYTHONPATH=$(PWD):$(PYTHONPATH) mkdocs build
