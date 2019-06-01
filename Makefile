all: check
	make -C docs html SPHINXOPTS=-W

check:
	python3 setup.py $@ -ms
	black --check -q .
	flake8
	mypy futured.py --ignore-missing-imports
	pytest --cov --cov-fail-under=100

clean:
	hg st -in | xargs rm
	rm -rf build dist futured.egg-info

dist:
	python3 setup.py sdist bdist_wheel
