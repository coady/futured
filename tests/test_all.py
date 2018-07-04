import asyncio
import contextlib
import os
import subprocess
import time
from concurrent import futures
import pytest
from futured import futured, threaded, processed, asynced, command, forked, decorated

delays = [0.2, 0.1, 0.0]


@contextlib.contextmanager
def timed():
    start = time.time()
    try:
        yield
    finally:
        assert (time.time() - start) < sum(delays)


def sleep(delay):
    time.sleep(delay)
    return delay


@asynced
def asleep(delay):
    return asyncio.sleep(delay, result=delay)


class sleeps:
    def __init__(self):
        self.delays = iter(delays)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await asleep(next(self.delays) / 2)
        except StopIteration:
            raise StopAsyncIteration


def test_class():
    fstr = decorated(str, lower=threaded)
    assert fstr('Test').lower().result() == 'test'
    st, = fstr.lower.map(['Test'])
    assert st == 'test'


@pytest.parametrized
def test_executors(executed=[threaded, processed]):
    executor = executed(max_workers=1)
    assert executor._max_workers == 1
    assert executor(sleep).func.__self__ is executor


def test_results():
    assert next(futured.results([threaded(sleep)(0)])) == 0
    assert next(asynced.results([asleep(0)])) == 0
    assert asleep.run(0) == 0
    assert asynced.run(asyncio.sleep, 0) is None


@pytest.parametrized
def test_map(coro=[threaded(sleep), processed(max_workers=len(delays))(sleep), asleep]):
    with timed():
        assert list(coro.map(delays)) == delays
    with timed():
        assert list(coro.map(delays, timeout=None)) == sorted(delays)
    for (key, value), delay in zip(coro.mapzip(delays), sorted(delays)):
        assert key == value == delay
    with pytest.raises(futures.TimeoutError):
        list(coro.map(delays, timeout=0))


def test_subprocess():
    sleep = futured(command, 'sleep')
    with timed():
        assert list(sleep.map(map(str, delays))) == [b''] * len(delays)
    with pytest.raises(subprocess.CalledProcessError):
        sleep().result()
    with pytest.raises(subprocess.TimeoutExpired):
        sleep('1').result(timeout=0)
    count = int(command('ls').pipe('wc', '-l').result().strip())
    assert count and count == len(list(command('ls')))
    with pytest.raises(subprocess.CalledProcessError):
        asynced.run(command.coroutine, 'sleep')
    assert next(asynced(command.coroutine, 'sleep').map('0', timeout=None)) == b''
    assert asynced.run(command.coroutine, 'sleep 0', shell=True) == b''


def test_forked():
    for index, delay in enumerate(forked(delays)):
        assert index == 0
        time.sleep(delay)
    with pytest.raises(UnboundLocalError):
        index
    with pytest.raises(OSError):
        for delay in forked(delays):
            os._exit(bool(delay))
    with timed():
        for delay in forked(delays, max_workers=2):
            time.sleep(delay)
    with pytest.raises(AssertionError), timed():
        for delay in forked(delays, max_workers=1):
            time.sleep(delay)


def test_iteration():
    with timed():
        for x, y in zip(asynced.run(sleeps), asynced.run(sleeps)):
            assert x == y


async def tasked():
    async with asynced.wait() as tasks:
        tasks.add(asyncio.sleep, 0)
    return tasks


def test_context():
    sleep = threaded(time.sleep)
    with sleep.wait() as tasks:
        tasks['first'] = sleep(0.1)
        tasks.add(sleep, 0)
        assert list(tasks) == ['first', 1]
    assert tasks == {'first': None, 1: None}
    with asynced.wait(loop=None) as tasks:
        tasks.add(asyncio.sleep, 0.1)
        tasks['second'] = asyncio.sleep(0)
        assert list(tasks) == [0, 'second']
    assert tasks == {0: None, 'second': None}
    assert asynced.run(tasked) == {0: None}
