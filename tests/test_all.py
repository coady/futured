import asyncio
import contextlib
import os
import subprocess
import time
from concurrent import futures
import pytest
from parametrized import parametrized
from futured import futured, threaded, processed, asynced, command, forked, decorated

delays = [0.2, 0.1, 0.05]
workers = {'max_workers': len(delays)}


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


def test_results():
    with timed():
        assert threaded(sleep)(sum(delays)).running
    with threaded(sleep) as tsleep:
        assert next(futured.results([tsleep(0)])) == 0
    with pytest.raises(RuntimeError):
        tsleep(0)
    assert next(asynced.results([asleep(0)])) == 0
    assert asleep.run(0) == 0
    assert asynced.run(asyncio.sleep, 0) is None


@parametrized
def test_map(coro=[threaded(**workers)(sleep), processed(**workers)(sleep), asleep]):
    with timed():
        assert list(coro.map(delays)) == delays
    with timed():
        assert list(coro.map(delays, timeout=None)) == sorted(delays)
    with timed():
        assert list(coro.map(delays, as_completed=True)) == sorted(delays)
    with timed():
        assert list(coro.starmap((delay,) for delay in delays)) == delays
    for (key, value), delay in zip(coro.mapzip(delays), sorted(delays)):
        assert key == value == delay
    with pytest.raises((futures.TimeoutError, asyncio.TimeoutError)):
        list(coro.map(delays, timeout=0))


def test_command():
    sleep = futured(command, 'sleep')
    with timed():
        assert list(sleep.map(map(str, delays))) == [b''] * len(delays)
    with pytest.raises(subprocess.CalledProcessError):
        sleep().result()
    with pytest.raises(subprocess.TimeoutExpired):
        sleep('1').result(timeout=0)
    count = int(command('ls').pipe('wc', '-l').result().strip())
    assert count and count == len(list(command('ls')))
    line, = command('ls') | ('wc',)
    assert len(line.split()) == 3
    with pytest.raises(subprocess.CalledProcessError):
        asynced.run(command.coroutine, 'sleep')
    assert next(asynced(command.coroutine, 'sleep').map('0', timeout=None)) == b''
    assert asynced.run(command.coroutine, 'sleep 0', shell=True) == b''
    with pytest.raises(TypeError):
        list(sleep.mapzip('0'))


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


def test_context():
    sleep = threaded(time.sleep)
    with sleep.waiting(sleep(0)) as tasks:
        tasks.append(sleep(0))
        assert all(isinstance(task, futures.Future) for task in tasks)
    assert tasks == [None, None]
    with asynced.waiting(asyncio.sleep(0, result='first'), loop=None) as tasks:
        tasks.append(asyncio.sleep(0, result='second'))
    assert tasks == ['first', 'second']


def test_distributed():
    pytest.importorskip('distributed')
    from futured import distributed

    with distributed(time.sleep) as dsleep:
        results = dsleep.map(delays, as_completed=True)
        assert list(dsleep.map(delays)) == list(results) == [None] * len(delays)
    with pytest.raises(Exception):
        dsleep(0)
