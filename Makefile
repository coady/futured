all: check
	make -C docs html SPHINXOPTS=-W

check:
	python3 setup.py $@ -ms
	black --check -q .
	flake8
	mypy futured.py --ignore-missing-imports
	pytest --cov --cov-fail-under=100
