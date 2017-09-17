.. image:: https://img.shields.io/pypi/v/futured.svg
   :target: https://pypi.python.org/pypi/futured/
.. image:: https://img.shields.io/pypi/pyversions/futured.svg
.. image:: https://img.shields.io/pypi/status/futured.svg
.. image:: https://img.shields.io/travis/coady/futured.svg
   :target: https://travis-ci.org/coady/futured
.. image:: https://img.shields.io/codecov/c/github/coady/futured.svg
   :target: https://codecov.io/github/coady/futured

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
   fetch.results(fs, timeout=...)  # generates results as completed

   fetch.map(urls)  # generates results in order
   fetch.map(urls, timeout=...)  # generates results as completed
   fetch.mapzip(urls)  # generates (url, result) pairs as completed

Naturally ``futured`` wrappers can be used as decorators,
but arguments can also be partially bound.

.. code-block:: python

   @threaded
   def slow():
      ...

   fetch = threaded(requests.Session().get, url)
   fetch(params=...)

Methods are supported, as well as a ``decorated`` utility for automatically subclassing.

.. code-block:: python

   from futured import decorated

   FutureSession = decorated(requests.Session, request=threaded)

   # equivalent to
   class FutureSession(requests.Session):
      request = threaded(requests.Session.request)

Thread and process pool executors may be customized and reused.

.. code-block:: python

   threaded(max_workers=...)(func, ...)
   processed(max_workers=...)(func, ...)

The same interface works for ``aynscio``.
For convenience, there's also a synchronous ``run`` method.

.. code-block:: python

   from futured import asynced
   import aiohttp

   fetch = asynced(aiohttp.ClientSession().get)
   fetch(url)  # returns coroutine
   fetch.run(url)  # single synchronous call

   # generate results as described above
   fetch.results(fs)
   fetch.map(urls)
   fetch.mapzip(urls)

``command`` wraps ``subprocess.Popen`` to provide a ``Future`` compatible interface.

.. code-block:: python

   from futured import futured, command

   command('ls').result()  # returns stdout or raises stderr
   command('ls').pipe('wc')  # pipes into next command
   for line in command('ls'):  # iterable lines
   command.coroutine('ls')  # returns coroutine

   futured(command, 'ls')  # supports `map` interface
   asynced(command.coroutine, 'ls')  # supports `map` interface with timeout

``forked`` allows iteration in separate child processes.

.. code-block:: python

   from futured import forked

   for value in forked(values):
      # in a child process
   # in parent after children have exited

Installation
=========================
::

   $ pip install futured

Dependencies
=========================
* Python 3.5+

Tests
=========================
100% branch coverage. ::

   $ pytest [--cov]

Changes
=========================
0.2

* ``command.coroutine`` creates asyncio subprocesses
* ``futured.mapzip`` generates results zipped with arguments
* ``asynced.run`` supports asynchronous iterators
