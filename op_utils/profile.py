import cProfile
import functools
import logging
import time

__all__ = [
    "profile",
    "cprofile",
]


logger = logging.getLogger(__name__)


def cprofile(output_file):
    """A decorator uses cProfile to profile a function.

    Use `snakeviz` for visualizing the result file.

    Args:
        output_file (str): The file path to save the profiling result.

    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):

            pr = cProfile.Profile()
            pr.enable()
            result = func(*args, **kwargs)
            pr.disable()
            pr.dump_stats(output_file)
            return result

        return wrapper

    return decorator


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
