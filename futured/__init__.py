import asyncio
import contextlib
import itertools
import operator
import os
import subprocess
import types
from collections.abc import AsyncIterable, Callable, Collection, Iterable, Iterator
from concurrent import futures
from functools import partial
from typing import Self


class futured(partial):
    """A partial function which returns futures."""

    as_completed: Callable = NotImplemented  # type: ignore

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
        return map(operator.methodcaller("result"), tasks)

    @classmethod
    def items(cls, pairs: Iterable, **kwargs) -> Iterator:
        """Generate key, result pairs as completed from futures.

        Args:
            pairs: key, future pairs
            **kwargs: as completed options, e.g., timeout
        """
        keys = dict(map(reversed, pairs))
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

    class tasks(set):
        """A set of futures which tracks completion.

        The context manager waits for all tasks.
        """

        as_completed: Callable = NotImplemented  # type: ignore

        def __init__(self, fs: Iterable = (), *, timeout=None):
            super().__init__(fs)
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            for _ in self.as_completed():
                ...

        def pop(self):
            """Remove and return next completed task."""
            for task in self.as_completed():
                self.remove(task)
                return task
            raise KeyError("pop from an empty set")


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
        self.func.__self__.__exit__(*args)  # type: ignore

    class tasks(futured.tasks):
        __doc__ = futured.tasks.__doc__

        def as_completed(self):
            return futures.as_completed(self, self.timeout)


class threaded(executed):
    """A partial function executed in its own thread pool."""

    Executor = futures.ThreadPoolExecutor


class processed(executed):
    """A partial function executed in its own process pool."""

    Executor = futures.ProcessPoolExecutor


with contextlib.suppress(ImportError):

    class distributed(executed):
        """A partial function executed by a dask distributed client."""

        from distributed import Client as Executor, as_completed  # noqa


class asynced(futured):
    """A partial async coroutine."""

    @staticmethod
    def as_completed(fs: Collection, loop=None, **kwargs) -> Iterator:
        """Replaces `asyncio.as_completed`, which requires a running loop."""
        loop = loop or asyncio.new_event_loop()
        while fs:
            coro = asyncio.wait(fs, return_when=asyncio.FIRST_COMPLETED, **kwargs)
            done, fs = loop.run_until_complete(coro)
            if not done:
                raise asyncio.TimeoutError
            yield from done

    @classmethod
    def results(cls, fs: Iterable, *, as_completed=False, **kwargs) -> Iterator:
        loop = asyncio.new_event_loop()
        tasks = list(map(loop.create_task, fs))
        if as_completed or kwargs:
            tasks = cls.as_completed(tasks, loop, **kwargs)
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
        task = loop.create_task(anext())  # type: ignore
        while True:
            try:
                result = loop.run_until_complete(task)
            except StopAsyncIteration:
                return
            task = loop.create_task(anext())  # type: ignore
            yield result

    class tasks(futured.tasks):
        __doc__ = futured.tasks.__doc__

        def __init__(self, coros: Iterable = (), **kwargs):
            self.loop = asyncio.new_event_loop()
            super().__init__(map(self.loop.create_task, coros), **kwargs)

        def as_completed(self):
            return asynced.as_completed(self, self.loop, timeout=self.timeout)

        def add(self, coro):  # type: ignore
            super().add(self.loop.create_task(coro))


with contextlib.suppress(ImportError):
    import gevent.pool

    class greened(futured):
        """A partial gevent greenlet."""

        def __new__(cls, *args, **kwargs):
            if args:
                return futured.__new__(cls, gevent.spawn, *args, **kwargs)
            return partial(futured.__new__, cls, gevent.pool.Pool(**kwargs).spawn)

        @classmethod
        def results(cls, fs: Iterable, *, as_completed=False, **kwargs) -> Iterator:
            fs = list(fs)
            if as_completed or kwargs:
                fs = gevent.iwait(fs, **kwargs)
            return map(operator.methodcaller("get"), fs)

        @classmethod
        def items(cls, pairs: Iterable, **kwargs) -> Iterator:
            keys = dict(map(reversed, pairs))
            return ((keys[future], future.get()) for future in gevent.iwait(keys, **kwargs))

        class tasks(futured.tasks):
            __doc__ = futured.tasks.__doc__

            def as_completed(self):
                count = 0
                for task in gevent.iwait(self, self.timeout):
                    count += 1
                    yield task
                if count < len(self):
                    raise gevent.Timeout


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
        self = await create(*args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)  # type: ignore
        return cls.check(self, args, *(await self.communicate()))  # type: ignore

    def result(self, **kwargs) -> str | bytes:
        """Return stdout or raise stderr."""
        return self.check(self.args, *self.communicate(**kwargs))

    def pipe(self, *args, **kwargs) -> Self:
        """Pipe stdout to the next command's stdin."""
        return type(self)(*args, stdin=self.stdout, **kwargs)

    def __or__(self, other: Iterable) -> Self:
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
