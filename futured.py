import asyncio
import contextlib
import itertools
import operator
import os
import queue
import subprocess
import types
from concurrent import futures
from functools import partial
from typing import AsyncIterable, Callable, Iterable, Iterator

__version__ = '1.0'


class futured(partial):
    """A partial function which returns futures."""

    as_completed = NotImplemented

    def __get__(self, instance, owner):
        return self if instance is None else types.MethodType(self, instance)

    @classmethod
    def results(cls, fs: Iterable, *, as_completed=False, **kwargs) -> Iterator:
        """Generate results concurrently from futures, by default in order.

        :param fs: iterable of futures
        :param as_completed, kwargs: generate results as completed with options, e.g., timeout
        """
        fs = list(fs)  # ensure futures are executing
        if as_completed or kwargs:
            fs = cls.as_completed(fs, **kwargs)
        return map(operator.methodcaller('result'), fs)

    @classmethod
    def items(cls, iterable: Iterable, **kwargs) -> Iterator:
        """Generate key, result pairs as completed from futures.

        :param iterable: key, future pairs
        :param kwargs: as completed options, e.g., timeout
        """
        fs = []
        for key, future in iterable:
            future._key = key
            fs.append(future)
        return ((future._key, future.result()) for future in cls.as_completed(fs, **kwargs))

    def map(self, *iterables, **kwargs) -> Iterator:
        """Asynchronously map function.

        :param kwargs: keyword options for :meth:`results`
        """
        return self.results(map(self, *iterables), **kwargs)

    def starmap(self, iterable: Iterable, **kwargs) -> Iterator:
        """Asynchronously starmap function.

        :param kwargs: keyword options for :meth:`results`
        """
        return self.results(itertools.starmap(self, iterable), **kwargs)

    def mapzip(self, iterable: Iterable, **kwargs) -> Iterator:
        """Generate arg, result pairs as completed.

        :param kwargs: keyword options for :meth:`items`
        """
        return self.items(((arg, self(arg)) for arg in iterable), **kwargs)

    @classmethod
    @contextlib.contextmanager
    def waiting(cls, *fs, **kwargs):
        """Return context manager which waits on :meth:`results`."""
        fs = list(fs)
        try:
            yield fs
        finally:
            fs[:] = cls.results(fs, **kwargs)


class executed(futured):
    """Extensible base class for callables which require a ``submit`` method."""

    as_completed = futures.as_completed
    Executor = NotImplemented

    def __new__(cls, *args, **kwargs):
        if args:
            return futured.__new__(cls, cls.Executor().submit, *args, **kwargs)
        return partial(futured.__new__, cls, cls.Executor(**kwargs).submit)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.func.__self__.__exit__(*args)


class threaded(executed):
    """A partial function executed in its own thread pool."""

    Executor = futures.ThreadPoolExecutor


class processed(executed):
    """A partial function executed in its own process pool."""

    Executor = futures.ProcessPoolExecutor


with contextlib.suppress(ImportError):

    class distributed(executed):
        """A partial function executed by a dask distributed client."""

        from distributed import as_completed, Client as Executor


class asynced(futured):
    """A partial coroutine."""

    @classmethod
    def results(cls, fs: Iterable, *, loop=None, as_completed=False, **kwargs) -> Iterator:
        """Generate results concurrently from coroutines or futures."""
        loop = loop or asyncio.get_event_loop()
        fs = [asyncio.ensure_future(future, loop=loop) for future in fs]
        if as_completed or kwargs:
            fs = asyncio.as_completed(fs, loop=loop, **kwargs)
        return map(loop.run_until_complete, fs)

    @staticmethod
    async def pair(key, future):
        return key, await future

    @classmethod
    def items(cls, iterable: Iterable, **kwargs) -> Iterator:
        """Generate (key, result) pairs as completed from (key, future) pairs."""
        return cls.results(itertools.starmap(cls.pair, iterable), as_completed=True, **kwargs)

    def run(self: Callable, *args, **kwargs):
        """Synchronously call and run coroutine or asynchronous iterator."""
        coro = self(*args, **kwargs)
        if isinstance(coro, AsyncIterable):
            return looped(coro)
        return asyncio.get_event_loop().run_until_complete(coro)


class looped:
    """Wrap an asynchronous iterable into an iterator.

    Analogous to loop.run_until_complete for coroutines.
    """

    def __init__(self, aiterable: AsyncIterable, *, loop=None):
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

    def pipe(self, *args, **kwargs) -> 'command':
        """Pipe stdout to the next command's stdin."""
        return type(self)(*args, stdin=self.stdout, **kwargs)

    def __or__(self, other: Iterable) -> 'command':
        """Alias of :meth:`pipe`."""
        return self.pipe(*other)

    def __iter__(self):
        """Return output lines."""
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


def forked(values: Iterable, max_workers: int = None) -> Iterator:
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
