.. .. image:: https://img.shields.io/pypi/v/futured.svg
..    :target: https://pypi.python.org/pypi/futured/
.. .. image:: https://img.shields.io/pypi/pyversions/futured.svg
.. .. image:: https://img.shields.io/pypi/status/futured.svg
.. .. image:: https://img.shields.io/travis/coady/futured.svg
..    :target: https://travis-ci.org/coady/futured
.. .. image:: https://img.shields.io/codecov/c/github/coady/futured.svg
..    :target: https://codecov.io/github/coady/futured

Futured provides a simple consistent interface for concurrent functional programming in Python.
It can wrap any callable to return ``concurrent.futures.Future`` objects,
and it can wrap any async coroutine to return ``asyncio.Future`` objects.

Usage
=========================
Transform any callable into one which runs in a thread or process pool, and returns a future.

.. code-block:: python

   from futured import threaded, processed
   import requests

   fetch = threaded(requests.Session().get)
   fetch(url)  # returns Future

   fs = (fetch(url + path) for path in paths)
   fetch.results(fs)  # generates results in order
   fetch.results(fs, timeout=None)  # generates results as completed

   fetch.map(urls)  # generates results in order
   fetch.map(urls, timeout=None)  # generates results as completed

Naturally futured wrappers can be used as decorators,
but arguments can also be partially bound.

.. code-block:: python

   @threaded
   def slow():
      ...

   fetch = threaded(Session().get, url)
   fetch(params=...)

The same interface works for ``aynscio``.

.. code-block:: python

   from futured import asynced
   import aiohttp

   fetch = asynced(aiohttp.ClientSession().get)

Installation
=========================
::

   $ pip install futured

Dependencies
=========================
* Python 3.4+

Tests
=========================
100% branch coverage. ::

   $ pytest [--cov]
