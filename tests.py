import asyncio
import time
from concurrent import futures
import pytest
from futured import futured, threaded, processed, asynced

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


def test_results():
    assert next(futured.results([threaded(sleep)(0)])) == 0
    assert next(asynced.results([asleep(0)])) == 0


def test_map():
    for coro in (threaded(sleep), processed(sleep), asleep):
        assert timer(coro.map(delays)) == delays
        assert timer(coro.map(delays, timeout=None)) == sorted(delays)
        with pytest.raises(futures.TimeoutError):
            list(coro.map(delays, timeout=0))
