import time
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class TimerResult:
    elapsed_ms: float = 0.0


@contextmanager
def timer():
    start = time.perf_counter()
    result = TimerResult()
    try:
        yield result
    finally:
        result.elapsed_ms = (time.perf_counter() - start) * 1000.0
