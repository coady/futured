import asyncio
import operator
import os
import subprocess
import types
from concurrent import futures
from functools import partial

__version__ = '0.1'


class futured(partial):
    """A partial function which returns futures."""
    def __get__(self, instance, owner):
        return self if instance is None else types.MethodType(self, instance)

    @staticmethod
    def results(fs, **kwargs):
        """Generate results concurrently from futures, by default in order.

        :param fs: iterable of futures
        :param timeout: optional timeout generates results as completed
        """
        fs = list(fs)  # ensure futures are executing
        if kwargs:
            fs = futures.as_completed(fs, **kwargs)
        return map(operator.methodcaller('result'), fs)

    def map(self, *iterables, **kwargs):
        """Asynchronously map function.

        :param kwargs: keyword options for `results`_
        """
        return self.results(map(self, *iterables), **kwargs)


class executed:
    def __new__(cls, *args, **kwargs):
        return cls()(*args, **kwargs) if args else object.__new__(cls)

    def __call__(self, func, *args, **kwargs):
        return futured(self.submit, func, *args, **kwargs)


class threaded(executed, futures.ThreadPoolExecutor):
    """A partial function executed in its own thread pool."""


class processed(executed, futures.ProcessPoolExecutor):
    """A partial function executed in its own process pool."""


class asynced(futured):
    """A partial coroutine."""
    @staticmethod
    def results(fs, loop=None, **kwargs):
        """Generate results concurrently from coroutines or futures."""
        loop = loop or asyncio.get_event_loop()
        fs = [asyncio.ensure_future(future, loop=loop) for future in fs]
        if kwargs:
            fs = asyncio.as_completed(fs, loop=loop, **kwargs)
        return map(loop.run_until_complete, fs)

    def run(self, *args, **kwargs):
        """Synchronously call and run coroutine."""
        return asyncio.get_event_loop().run_until_complete(self(*args, **kwargs))


class command(subprocess.Popen):
    """Asynchronous subprocess with a future compatible interface."""
    def __init__(self, *args, **kwargs):
        super().__init__(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)

    def result(self, **kwargs):
        """Return stdout or raise stderr."""
        stdout, stderr = self.communicate(**kwargs)
        if self.returncode:
            raise subprocess.CalledProcessError(self.returncode, self.args, stdout, stderr)
        return stdout

    def pipe(self, *args, **kwargs):
        """Pipe stdout to the next command's stdin."""
        return type(self)(*args, stdin=self.stdout, **kwargs)

    def __iter__(self):
        return iter(self.result().splitlines())


def forked(values):
    """Generate each value in its own child process and wait in the parent."""
    procs = []
    for value in values:
        pid = os.fork()
        if pid:
            procs.append((pid, value))
        else:  # pragma: no cover
            yield value
            os._exit(0)
    for pid, value in procs:
        pid, status = os.waitpid(pid, 0)
        if status:
            raise OSError(status, value)


def decorated(base, **decorators):
    """Return subclass with decorated methods."""
    namespace = {name: decorators[name](getattr(base, name)) for name in decorators}
    return type(base.__name__, (base,), namespace)
