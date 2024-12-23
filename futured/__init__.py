import asyncio
import contextlib
import itertools
import operator
import os
import subprocess
import types
from collections.abc import AsyncIterable, Callable, Iterable, Iterator
from concurrent import futures
from functools import partial
from typing import Union


class futured(partial):
    """A partial function which returns futures."""

    as_completed: Callable = NotImplemented

    def __get__(self, instance, owner):
        return self if instance is None else types.MethodType(self, instance)

    @classmethod
    def results(cls, fs: Iterable, *, as_completed=False, **kwargs) -> Iterator:
        """Generate results concurrently from futures, by default in order.

        Args:
            fs: iterable of futures
            as_completed kwargs: generate results as completed with options, e.g., timeout
        """
        tasks = cls.as_completed(fs, **kwargs) if (as_completed or kwargs) else list(fs)
        return map(operator.methodcaller('result'), tasks)

    @classmethod
    def items(cls, pairs: Iterable, **kwargs) -> Iterator:
        """Generate key, result pairs as completed from futures.

        Args:
            pairs: key, future pairs
            **kwargs: as completed options, e.g., timeout
        """
        keys = dict(map(reversed, pairs))  # type: ignore
        return ((keys[future], future.result()) for future in cls.as_completed(keys, **kwargs))

    def map(self, *iterables: Iterable, **kwargs) -> Iterator:
        """Asynchronously map function.

        Args:
            **kwargs: keyword options for [results][futured.futured.results]
        """
        return self.results(map(self, *iterables), **kwargs)

    def starmap(self, iterable: Iterable, **kwargs) -> Iterator:
        """Asynchronously starmap function.

        Args:
            **kwargs: keyword options for [results][futured.futured.results]
        """
        return self.results(itertools.starmap(self, iterable), **kwargs)

    def mapzip(self, iterable: Iterable, **kwargs) -> Iterator:
        """Generate arg, result pairs as completed.

        Args:
            **kwargs: keyword options for [items][futured.futured.items]
        """
        return self.items(((arg, self(arg)) for arg in iterable), **kwargs)

    @classmethod
    @contextlib.contextmanager
    def waiting(cls, *fs, **kwargs):
        """Return context manager which waits on [results][futured.futured.results]."""
        fs = list(fs)
        try:
            yield fs
        finally:
            fs[:] = cls.results(fs, **kwargs)

    class tasks(set):
        """A set of futures which iterate as completed, and can be updated while iterating."""

        TimeoutError = futures.TimeoutError

        def __init__(self, fs: Iterable, *, timeout=None):
            super().__init__(fs)
            self.timeout = timeout
            self.it = self.iter()

        def wait(self, fs: list) -> Iterable:
            return futures.wait(fs, self.timeout, return_when='FIRST_COMPLETED').done

        def iter(self):
            while self:
                done = self.wait(list(super().__iter__()))
                if not done:
                    raise self.TimeoutError
                self.difference_update(done)
                yield from done

        def __iter__(self):
            return self

        def __next__(self):
            return next(self.it)


class executed(futured):
    """Extensible base class for callables which require a `submit` method."""

    as_completed = futures.as_completed
    Executor = futures.Executor

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

        from distributed import as_completed, Client as Executor  # type: ignore


class asynced(futured):
    """A partial async coroutine."""

    @classmethod
    def results(cls, fs: Iterable, *, as_completed=False, **kwargs) -> Iterator:
        if as_completed or kwargs:
            return map(operator.methodcaller('result'), cls.tasks(fs, **kwargs))
        loop = asyncio.new_event_loop()
        tasks = list(map(loop.create_task, fs))
        return map(loop.run_until_complete, tasks)

    @staticmethod
    async def pair(key, future):
        return key, await future

    @classmethod
    def items(cls, pairs: Iterable, **kwargs) -> Iterator:
        return cls.results(itertools.starmap(cls.pair, pairs), as_completed=True, **kwargs)

    def run(self: Callable, *args, **kwargs):
        """Synchronously call and run coroutine or asynchronous iterator."""
        coro = self(*args, **kwargs)
        return asynced.iter(coro) if isinstance(coro, AsyncIterable) else asyncio.run(coro)

    @staticmethod
    def iter(aiterable: AsyncIterable, loop=None):
        """Wrap an asynchronous iterable into an iterator.

        Analogous to `asyncio.run` for coroutines.
        """
        loop = loop or asyncio.new_event_loop()
        anext = aiterable.__aiter__().__anext__
        task = loop.create_task(anext())
        while True:
            try:
                result = loop.run_until_complete(task)
            except StopAsyncIteration:
                return
            task = loop.create_task(anext())
            yield result

    class tasks(futured.tasks):
        __doc__ = futured.tasks.__doc__
        TimeoutError = asyncio.TimeoutError

        def __init__(self, coros: Iterable, **kwargs):
            self.loop = asyncio.new_event_loop()
            super().__init__(map(self.loop.create_task, coros), **kwargs)

        def add(self, coro):
            super().add(self.loop.create_task(coro))

        def wait(self, fs: list) -> Iterable:
            coro = asyncio.wait(fs, timeout=self.timeout, return_when='FIRST_COMPLETED')
            return self.loop.run_until_complete(coro)[0]


with contextlib.suppress(ImportError):
    import gevent.pool  # type: ignore

    class greened(futured):
        """A partial gevent greenlet."""

        def __new__(cls, *args, **kwargs):
            if args:
                return futured.__new__(cls, gevent.spawn, *args, **kwargs)
            return partial(futured.__new__, cls, gevent.pool.Pool(**kwargs).spawn)

        @classmethod
        def results(cls, fs: Iterable, *, as_completed=False, **kwargs) -> Iterator:
            tasks = cls.tasks(fs, **kwargs) if (as_completed or kwargs) else list(fs)
            return map(operator.methodcaller('get'), tasks)

        @classmethod
        def items(cls, pairs: Iterable, **kwargs) -> Iterator:
            keys = dict(map(reversed, pairs))  # type: ignore
            return ((keys[future], future.get()) for future in cls.tasks(keys, **kwargs))

        class tasks(futured.tasks):
            __doc__ = futured.tasks.__doc__
            TimeoutError = gevent.Timeout

            def wait(self, fs: list) -> Iterable:
                return gevent.wait(fs, self.timeout, count=1)


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

    def result(self, **kwargs) -> Union[str, bytes]:
        """Return stdout or raise stderr."""
        return self.check(self.args, *self.communicate(**kwargs))

    def pipe(self, *args, **kwargs) -> 'command':
        """Pipe stdout to the next command's stdin."""
        return type(self)(*args, stdin=self.stdout, **kwargs)

    def __or__(self, other: Iterable) -> 'command':
        """Alias of [pipe][futured.command.pipe]."""
        return self.pipe(*other)

    def __iter__(self):
        """Return output lines."""
        return iter(self.result().splitlines())


def forked(values: Iterable, max_workers: int = 0) -> Iterator:
    """Generate each value in its own child process and wait in the parent."""
    max_workers = max_workers or os.cpu_count() or 1  # same default as ProcessPoolExecutor
    workers: dict = {}

    def wait():
        pid, status = os.wait()
        if pid in workers:
            value = workers.pop(pid)
            if status:
                raise OSError(status, value)

    for value in values:
        while len(workers) >= max_workers:
            wait()
        if pid := os.fork():
            workers[pid] = value
        else:  # pragma: no cover
            yield value
            os._exit(0)
    while workers:
        wait()


def decorated(base: type, **decorators: Callable) -> type:
    """Return subclass with decorated methods."""
    namespace = {name: decorators[name](getattr(base, name)) for name in decorators}
    return type(base.__name__, (base,), namespace)
