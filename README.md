[![image](https://img.shields.io/pypi/v/futured.svg)](https://pypi.org/project/futured/)
![image](https://img.shields.io/pypi/pyversions/futured.svg)
[![image](https://pepy.tech/badge/futured)](https://pepy.tech/project/futured)
![image](https://img.shields.io/pypi/status/futured.svg)
[![image](https://github.com/coady/futured/workflows/build/badge.svg)](https://github.com/coady/futured/actions)
[![image](https://codecov.io/gh/coady/futured/branch/main/graph/badge.svg)](https://codecov.io/github/coady/futured)
[![image](https://github.com/coady/futured/workflows/codeql/badge.svg)](https://github.com/coady/futured/security/code-scanning)
[![image](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![image](https://mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)

Futured provides a consistent interface for concurrent functional programming in Python. It wraps any callable to return a `concurrent.futures.Future`, wraps any async coroutine with a compatible `Task` interface, and provides concurrent iterators and context managers for futures.

## Usage
### threaded, processed
Transform any callable into one which runs in a thread or process pool, and returns a future.

```python
from futured import threaded, processed
import httpx

fetch = threaded(httpx.Client().get)
fetch(url)  # return Future

fs = (fetch(url + path) for path in paths)
threaded.results(fs)  # generate results from futures
threaded.results(fs, timeout=...)  # generate results as completed

fetch.map(urls)  # generate results in order
fetch.map(urls, timeout=...)  # generate results as completed
fetch.mapzip(urls)  # generate (url, result) pairs as completed
```

Thread and process pool executors may be used as context managers, customized with options, and reused with different callables.

```python
threaded(max_workers=...)(func, ...)
processed(max_workers=...)(func, ...)
```

`futured` classes have a `waiting` context manager which collects results from tasks. Futures can be registered at creation, or appended to the list of tasks.

```python
with threaded.waiting(*fs) as tasks:
    tasks.append(future)
tasks  # list of completed results
```

`futured` classes provide a `tasks` interface which generalizes `futures.as_completed` and `futures.wait`, while allowing the set of tasks to be modified, e.g., for retries.

```python
threaded.tasks(fs, timeout=...)  # mutable set of running tasks which iterate as completed
```

### asynced
The same interface works for `asyncio`.

```python
from futured import asynced
import httpx

fetch = asynced(httpx.AsyncClient().get)
fetch(url)  # return coroutine

asynced.results(fs)  # generate results from futures
asynced.results(fs, timeout=...)  # generate results as completed

fetch.map(urls)  # generate results in order
fetch.map(urls, timeout=...)  # generate results as completed
fetch.mapzip(urls)  # generate (url, result) pairs as completed
```

`asynced` provides utilities for calling coroutines from a synchronous context. `waiting` is similar to [trio's nursery](https://trio.readthedocs.io/en/latest/reference-core.html#nurseries-and-spawning), but returns results from a synchronous `with` block.

```python
asynced.run(async_func, ...)  # call and run until complete
asynced.run(async_gen, ...)  # call and run synchronous iterator
with asynced.waiting(*fs) as tasks:  # concurrent coroutines completed in a block
asynced.tasks(fs, timeout=...)  # mutable set of running tasks which iterate as completed
```

### extensions
There is also support for [dask distributed](https://distributed.dask.org/) clients and [gevent](http://www.gevent.org/) greenlets.

```python
from futured import distributed, greened
```

### decorators
Naturally `futured` wrappers can be used as decorators, but arguments can also be partially bound.

```python
@threaded
def slow():
   ...

fetch = threaded(httpx.Client().get, url)
fetch(params=...)
```

Methods are supported, as well as a `decorated` utility for automatically subclassing.

```python
from futured import decorated

FutureClient = decorated(httpx.Client, request=threaded)

 # equivalent to
class FutureClient(httpx.Client):
    request = threaded(httpx.Client.request)
```

### command
`command` wraps `subprocess.Popen` to provide a `Future` compatible interface.

```python
from futured import futured, command

command('ls').result()  # return stdout or raises stderr
command('ls').pipe('wc')  # pipes into next command, or | ('wc',... )
for line in command('ls'):  # iterable lines
command.coroutine('ls')  # return coroutine

futured(command, 'ls')  # supports `map` interface
asynced(command.coroutine, 'ls')  # supports `map` interface with timeout
```

### forked
`forked` allows iteration in separate child processes.

```python
from futured import forked

for value in forked(values, max_workers=...):
    # in a child process
 # in parent after children have exited
```

## Installation
```console
% pip install futured
```

## Tests
100% branch coverage.

```console
% pytest [--cov]
```
