[![image](https://img.shields.io/pypi/v/futured.svg)](https://pypi.org/project/futured/)
![image](https://img.shields.io/pypi/pyversions/futured.svg)
![image](https://img.shields.io/pypi/status/futured.svg)
[![image](https://img.shields.io/travis/coady/futured.svg)](https://travis-ci.org/coady/futured)
[![image](https://img.shields.io/codecov/c/github/coady/futured.svg)](https://codecov.io/github/coady/futured)

Futured provides a simple consistent interface for concurrent functional
programming in Python. It can wrap any callable to return
`concurrent.futures.Future` objects, and it can wrap any async coroutine
to return `asyncio.Future` objects.

# Usage
## threaded, processed
Transform any callable into one which runs in a thread or process pool, and returns a future.

```python
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
```

Naturally `futured` wrappers can be used as decorators, but arguments can also be partially bound.

```python
@threaded
def slow():
   ...

fetch = threaded(requests.Session().get, url)
fetch(params=...)
```

Methods are supported, as well as a `decorated` utility for
automatically subclassing.

```python
from futured import decorated

FutureSession = decorated(requests.Session, request=threaded)

 # equivalent to
class FutureSession(requests.Session):
    request = threaded(requests.Session.request)
```

Thread and process pool executors may be customized and reused.

```python
threaded(max_workers=...)(func, ...)
processed(max_workers=...)(func, ...)
```

`futured` classes have a `waiting` context manager which collects results from tasks.
Futures can be registered at creation, or appended to the list of tasks.

```python
with threaded.waiting(future,... ) as tasks:
    tasks.append(future)
tasks  # results in order
```

## asynced
The same interface works for `aynscio`. For convenience, there's also a synchronous `run` method.

```python
from futured import asynced
import aiohttp

fetch = asynced(aiohttp.ClientSession().get)
fetch(url)  # returns coroutine
fetch.run(url)  # single synchronous call

 # generate results as described above
fetch.results(fs)
fetch.map(urls)
fetch.mapzip(urls)
```

## command
`command` wraps `subprocess.Popen` to provide a `Future` compatible interface.

```python
from futured import futured, command

command('ls').result()  # returns stdout or raises stderr
command('ls').pipe('wc')  # pipes into next command, or | ('wc',... )
for line in command('ls'):  # iterable lines
command.coroutine('ls')  # returns coroutine

futured(command, 'ls')  # supports `map` interface
asynced(command.coroutine, 'ls')  # supports `map` interface with timeout
```

## forked
`forked` allows iteration in separate child processes.

```python
from futured import forked

for value in forked(values, max_workers=...):
    # in a child process
 # in parent after children have exited
```

# Installation

    $ pip install futured

# Tests
100% branch coverage.

    $ pytest [--cov]

# Changes
0.3
* `forked` has optional maximum number of workers
* `waiting` context manager
* `command` pipes (`|`)
* `distributed.Client` support

0.2
* `command.coroutine` creates asyncio subprocesses
* `futured.mapzip` generates results zipped with arguments
* `asynced.run` supports asynchronous iterators
