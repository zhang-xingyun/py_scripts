import functools
import logging
import time

logger = logging.getLogger(__name__)

__all__ = [
    "profile",
]


def profile(func):
    @functools.wraps(func)
    def wrapped_func(*args, **kwargs):
        st_time = time.time()
        res = func(*args, **kwargs)
        ed_time = time.time()
        cost_time = float(ed_time - st_time)
        logger.info(f"'{func.__name__}' cost: {cost_time:.3f} s")
        return res

    return wrapped_func
