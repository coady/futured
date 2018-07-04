import asyncio
import collections
import itertools
import operator
import os
import queue
import subprocess
import types
from concurrent import futures
from functools import partial
from typing import AsyncIterable, Callable, Generator, Iterable, Iterator

__version__ = '0.2'


class tasks(collections.OrderedDict):
    """A context manager which processes registered futures on exit."""
    def __init__(self, callback=None):
        self.callback = callback

    def add(self, func, *args, **kwargs):
        self[len(self)] = func(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.update(zip(self, self.callback(self.values())))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        for key in self:
            self[key] = await self[key]


class futured(partial):
    """A partial function which returns futures."""
    def __get__(self, instance, owner):
        return self if instance is None else types.MethodType(self, instance)

    @staticmethod
    def results(fs: Iterable, **kwargs) -> Iterator:
        """Generate results concurrently from futures, by default in order.

        :param fs: iterable of futures
        :param timeout: optional timeout generates results as completed
        """
        fs = list(fs)  # ensure futures are executing
        if kwargs:
            fs = futures.as_completed(fs, **kwargs)
        return map(operator.methodcaller('result'), fs)

    @staticmethod
    def items(iterable, **kwargs):
        """Generate key, result pairs as completed from futures.

        :param iterable: key, future pairs
        :param timeout: optional timeout
        """
        fs = []
        for key, future in iterable:
            future._key = key
            fs.append(future)
        return ((future._key, future.result()) for future in futures.as_completed(fs, **kwargs))

    def map(self, *iterables, **kwargs):
        """Asynchronously map function.

        :param kwargs: keyword options for `results`_
        """
        return self.results(map(self, *iterables), **kwargs)

    def mapzip(self, iterable: Iterable, **kwargs) -> Iterator:
        """Generate arg, result pairs as completed.

        :param kwargs: keyword options for `items`_
        """
        return self.items(((arg, self(arg)) for arg in iterable), **kwargs)

    @classmethod
    def wait(cls, **kwargs):
        """Return context manager which waits on `results`._"""
        return tasks(partial(cls.results, **kwargs))


class threaded(futures.ThreadPoolExecutor):
    """A partial function executed in its own thread pool."""
    def __new__(cls, *args, **kwargs):
        return cls()(*args, **kwargs) if args else object.__new__(cls)

    def __call__(self, func: Callable, *args, **kwargs):
        return futured(self.submit, func, *args, **kwargs)


class processed(futures.ProcessPoolExecutor):
    """A partial function executed in its own process pool."""
    __new__ = threaded.__new__
    __call__ = threaded.__call__


class asynced(futured):
    """A partial coroutine."""
    @staticmethod
    def results(fs: Iterable, *, loop=None, **kwargs) -> Iterator:
        """Generate results concurrently from coroutines or futures."""
        loop = loop or asyncio.get_event_loop()
        fs = [asyncio.ensure_future(future, loop=loop) for future in fs]
        if kwargs:
            fs = asyncio.as_completed(fs, loop=loop, **kwargs)
        return map(loop.run_until_complete, fs)

    @classmethod
    def items(cls, iterable: Iterable, *, timeout=None, **kwargs) -> Iterator:
        """Generate (key, result) pairs as completed from (key, future) pairs."""
        async def coro(key, future):
            return key, await future
        return cls.results(itertools.starmap(coro, iterable), timeout=timeout, **kwargs)

    def run(self, *args, **kwargs):
        """Synchronously call and run coroutine or asynchronous iterator."""
        coro = self(*args, **kwargs)
        if isinstance(coro, collections.AsyncIterable):
            return looped(coro)
        return asyncio.get_event_loop().run_until_complete(coro)


class looped:
    """Wrap an asynchronous iterable into an iterator.

    Analogous to loop.run_until_complete for coroutines.
    """
    def __init__(self, aiterable: AsyncIterable, *, loop=None) -> None:
        self.anext = aiterable.__aiter__().__anext__
        self.loop = loop or asyncio.get_event_loop()
        self.future = asyncio.ensure_future(self.anext(), loop=self.loop)

    def __del__(self):  # suppress warning
        self.future.cancel()  # pragma: no cover

    def __iter__(self):
        return self

    def __next__(self):
        try:
            result = self.loop.run_until_complete(self.future)
        except StopAsyncIteration:
            raise StopIteration
        self.future = asyncio.ensure_future(self.anext(), loop=self.loop)
        return result


class command(subprocess.Popen):
    """Asynchronous subprocess with a future compatible interface."""
    def __init__(self, *args, **kwargs):
        super().__init__(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)

    def check(self, args, stdout, stderr):
        if self.returncode:
            raise subprocess.CalledProcessError(self.returncode, args, stdout, stderr)
        return stdout

    @classmethod
    async def coroutine(cls, *args, shell=False, **kwargs):
        """Create a subprocess coroutine, suitable for timeouts."""
        create = asyncio.create_subprocess_shell if shell else asyncio.create_subprocess_exec
        self = await create(*args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        return cls.check(self, args, *(await self.communicate()))

    def result(self, **kwargs):
        """Return stdout or raise stderr."""
        return self.check(self.args, *self.communicate(**kwargs))

    def pipe(self, *args, **kwargs):
        """Pipe stdout to the next command's stdin."""
        return type(self)(*args, stdin=self.stdout, **kwargs)

    def __iter__(self):
        return iter(self.result().splitlines())


class Results(queue.Queue):
    def put(self, pid, value):
        pid, status = os.waitpid(pid, 0)
        super().put((status, value))

    def get(self):
        status, value = super().get()
        if status:
            raise OSError(status, value)
        return not status


def forked(values: Iterable, max_workers: int = None) -> Generator:
    """Generate each value in its own child process and wait in the parent."""
    max_workers = max_workers or os.cpu_count() or 1  # same default as ProcessPoolExecutor
    workers, results = 0, Results()
    task = threaded(max_workers=max_workers)(results.put)
    for value in values:
        while workers >= max_workers:
            workers -= results.get()
        pid = os.fork()
        if pid:
            workers += bool(task(pid, value))
        else:  # pragma: no cover
            yield value
            os._exit(0)
    while workers:
        workers -= results.get()


def decorated(base: type, **decorators) -> type:
    """Return subclass with decorated methods."""
    namespace = {name: decorators[name](getattr(base, name)) for name in decorators}
    return type(base.__name__, (base,), namespace)
