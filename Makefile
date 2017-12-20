check:
	python3 setup.py $@ -mrs
	flake8
	mypy futured.py
	pytest --cov --cov-fail-under=100

clean:
	hg st -in | xargs rm
	rm -rf build dist futured.egg-info

dist:
	python3 setup.py sdist bdist_wheel
	rst2html.py README.rst $@/README.html
