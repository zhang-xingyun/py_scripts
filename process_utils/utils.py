"""Utils for building functions / classes.

The content in this file is not bind with any specific module. They are used to
simplify the process of building functions / classes.

"""
import collections
import functools
import logging
import socket
import time
import uuid
from contextlib import closing

import torch
from hatbc.data import from_sequence
from hatbc.data.executor.utils import initialize_ray
from hatbc.workflow import GraphTracer, get_traced_graph, make_traceable
from hatbc.workflow.proxy import Variable
from tqdm import tqdm as _tqdm

__all__ = [
    "get_unique_stamp",
    "to_cpu",
    "find_free_port",
    "move_data",
    "dict_values_to_variable",
    "tqdm",
    "trace_into_graph",
    "compare_version",
]

logger = logging.getLogger(__name__)


def get_unique_stamp() -> str:
    """Get a unique stamp.

    Returns:
        str: unique stamp.
    """
    return f"{int(time.time())}_{uuid.uuid4().hex}"


from_sequence = make_traceable(from_sequence)


def to_cpu(data):
    """Move data to cpu.

    Args:
        result: data to be moved.

    Returns:
        data: data in cpu.
    """
    if data is None:
        return data

    if hasattr(data, "detach"):
        data.detach()
    if hasattr(data, "to"):
        data = data.to("cpu")
        return data

    if isinstance(data, collections.abc.Mapping):
        return {k: to_cpu(v) for k, v in data.items()}
    elif isinstance(data, collections.abc.Sequence):
        return [to_cpu(v) for v in data]

    return data


def find_free_port() -> int:
    """Find a free port.

    Returns:
        int: free port.
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def move_data(data, to_cpu: bool = True):
    if isinstance(data, torch.Tensor) and to_cpu:
        return data.cpu()
    return data


def dict_values_to_variable(obj):
    assert isinstance(obj, dict)
    new_obj = dict(
        ((key_i, Variable(key_i, value_i)) for key_i, value_i in obj.items())
    )
    return new_obj


initialize_ray = make_traceable(initialize_ray)


def tqdm(iterable, *args, **kwargs):
    """Wrapped tqdm.

    Ray will cause tqdm to write a newline when updating progress bar.
    """
    import ray

    if ray.is_initialized():
        try:
            return ray.experimental.tqdm_ray.tqdm(iterable, *args, **kwargs)
        except Exception:
            pass  # noqa

    return _tqdm(iterable, *args, **kwargs)


def trace_into_graph(imperative: bool = False):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            with GraphTracer(imperative=imperative):
                output = fn(*args, **kwargs)
                return get_traced_graph(output)

        return wrapped

    return decorator


def compare_version(version1: str, version2: str):
    """Compare two version, -1 for lower, 0 for equal, 1 for higher."""
    v1 = [int(v) for v in version1.split(".")]
    v2 = [int(v) for v in version2.split(".")]
    while v1 and v1[-1] == 0:
        v1.pop()
    while v2 and v2[-1] == 0:
        v2.pop()
    v1, v2 = tuple(v1), tuple(v2)

    return 1 if v1 > v2 else 0 if v1 == v2 else -1
