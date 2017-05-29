import asyncio
import os
import subprocess
import time
from concurrent import futures
import pytest
from futured import futured, threaded, processed, asynced, command, forked

delays = [0.2, 0.1, 0.0]


def timer(results):
    start = time.time()
    try:
        return list(results)
    finally:
        assert (time.time() - start) < sum(delays)


def sleep(delay):
    time.sleep(delay)
    return delay


@asynced
def asleep(delay):
    return asyncio.sleep(delay, result=delay)


class wrapper:
    @threaded
    def method(self):
        pass


def test_class():
    assert wrapper().method().result() is None


def test_results():
    assert next(futured.results([threaded(sleep)(0)])) == 0
    assert next(asynced.results([asleep(0)])) == 0


def test_map():
    for coro in (threaded(sleep), processed(sleep), asleep):
        assert timer(coro.map(delays)) == delays
        assert timer(coro.map(delays, timeout=None)) == sorted(delays)
        with pytest.raises(futures.TimeoutError):
            list(coro.map(delays, timeout=0))


def test_subprocess():
    sleep = futured(command, 'sleep')
    assert timer(sleep.map(map(str, delays))) == [b''] * len(delays)
    with pytest.raises(subprocess.CalledProcessError):
        sleep().result()
    with pytest.raises(subprocess.TimeoutExpired):
        sleep('1').result(timeout=0)
    count = int(command('ls').pipe('wc', '-l').result().strip())
    assert count and count == len(list(command('ls')))


def test_forked():
    for index, delay in enumerate(forked(delays)):
        assert index == 0
        time.sleep(delay)
    with pytest.raises(UnboundLocalError):
        index
    with pytest.raises(OSError):
        for delay in forked(delays):
            os._exit(bool(delay))
