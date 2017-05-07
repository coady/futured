import asyncio
import operator
import subprocess
from concurrent import futures
from functools import partial

__version__ = '0.0'


class futured(partial):
    """A partial function which returns futures."""
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


def threaded(func, *args, **kwargs):
    """A partial function executed in a thread."""
    return futured(futures.ThreadPoolExecutor().submit, func, *args, **kwargs)


def processed(func, *args, **kwargs):
    """A partial function executed in a process."""
    return futured(futures.ProcessPoolExecutor().submit, func, *args, **kwargs)


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
