all: check
	PYTHONPATH=$(PWD) mkdocs build

check:
	python3 setup.py $@ -ms
	black --check -q .
	flake8
	mypy -p futured
	pytest --cov --cov-fail-under=100
