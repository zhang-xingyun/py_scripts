import hashlib
import itertools
import logging
import os
import random
from datetime import datetime
from functools import reduce
from typing import Any, Dict, List, NoReturn, Optional, Union

from hatbc.filestream.bucket import BucketClient
from hatbc.utils import _as_list
from hatbc.workflow.engine.simple_parallel import SimpleParallelContext
from hatbc.workflow.proxy import Variable
from hatbc.workflow.trace import make_traceable

from hdflow.utils.path import local_path_to_url, url_to_local_path

__all__ = [
    "add",
    "make_list",
    "merge_dict",
    "choose_by_worker",
    "get_worker_output_path",
    "dict_values_to_variable",
    "identity_pass",
    "add_timestamp",
    "grouper",
    "md5",
    "join_op",
    "stack_iterables",
    "ts2timestr",
    "format_time",
    "run_once",
    "merge_list",
    "compare_version",
]


logger = logging.getLogger(__name__)


@make_traceable
def add(lhs, rhs):
    return lhs + rhs


@make_traceable
def sub(lhs, rhs):
    return lhs - rhs


@make_traceable
def make_list(*data):
    return list(data)


@make_traceable
def merge_list(*input_lists):
    return list(reduce(lambda x, y: x + y, input_lists))


@make_traceable
def sub_list(lsh: Union[List[Any], Any], rsh: Union[List[Any], Any]):
    lsh = _as_list(lsh)
    rsh = _as_list(rsh)
    return [val for val in lsh if val not in rsh]


@make_traceable
def merge_dict(*dicts):
    merged_results = dict()
    for d in dicts:
        merged_results.update(d)
    return merged_results


@make_traceable
def as_str(obj):
    return str(obj)


@make_traceable
def choose_by_worker(population: list, num: int = 1):
    ctx = SimpleParallelContext.get_current()
    if ctx is None:
        choices = random.choices(population, k=num)
    else:
        choices = list()
        for i in range(num):
            idx = (ctx.worker_id * num + i) % len(population)
            choice = population[idx]
            choices.append(choice)
    return choices


@make_traceable
def get_worker_output_path(output_path: str):
    ctx = SimpleParallelContext.get_current()
    if ctx is not None:
        worker_id = ctx.worker_id
        output_name, ext = os.path.splitext(output_path)
        output_path = "%s_%02d%s" % (output_name, worker_id, ext)
    return output_path


def dict_values_to_variable(obj):
    assert isinstance(obj, dict)
    new_obj = dict(
        ((key_i, Variable(key_i, value_i)) for key_i, value_i in obj.items())
    )
    return new_obj


@make_traceable
def identity_pass(x):
    return x


@make_traceable
def join_op(op1, op2):
    """Concatenate 2 non causal operators.

    Args:
        op1: operator to be kept
        op2: operator to be discarded

    Returns:
        op1: operator to be kept
    """
    identity_pass(op2)
    return op1


def add_timestamp(name):
    time = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}_{time}"


def ts2timestr(timestamp, with_ms=False, ts_offset=28800):
    """Timestamp to time string.

    Args:
        timestamp (int): utc+0 timestamp
        with_ms (bool, optional): if ms is needed. Defaults to False.
        ts_offset(int): timestamp offset to specific timezone, default is utc+8

    Returns:
        str: a time str in format of YYYY-MM-DD HH:MM:SS.MS
    """
    timestamp_sec = timestamp // 1000 + ts_offset
    local_time = datetime.utcfromtimestamp(timestamp_sec)
    timestr = local_time.strftime("%Y-%m-%d %H:%M:%S")
    if with_ms:
        ms_str = "%03d" % (timestamp % 1000)
        timestr = ".".join([timestr, ms_str])
    return timestr


def format_time(
    x: Union[str, int], *, with_ms: bool = False, pattern: str = None
) -> str:
    """Get time string in `%Y-%m-%d %H:%M:%S`.

    Args:
        x (Union[str, int]): time to be formated
        with_ms (bool, optional): if inoput time contains ms. This is only \
            useful when input time is int type. Defaults to False.
        pattern (str, optional): pattern of input time. This is only useful \
            when input time is str type. Defaults to "%Y-%m-%d".

    Raises:
        TypeError: if input time is in unsupported type.

    Returns:
        str: time string
    """
    if isinstance(x, int):
        x = ts2timestr(x, with_ms)
    elif isinstance(x, str):
        if pattern:
            x = datetime.strptime(x, pattern).strftime("%Y-%m-%d %H:%M:%S")
    else:
        raise TypeError(
            f"Unsupported time value type: {type(x)}. "
            "Please input either `str` or `int`."
        )
    return x


def grouper(iterable, n, *, incomplete="fill", fillvalue=None):
    """Collect data into non-overlapping fixed-length chunks or blocks.

    grouper("ABCDEFG", 3, incomplete="fill", fillvalue="x") --> ABC DEF Gxx
    grouper("ABCDEFG", 3, incomplete="strict") --> ABC DEF ValueError
    grouper("ABCDEFG", 3, incomplete="ignore) --> ABC DEF

    """
    args = [iter(iterable)] * n
    if incomplete == "fill":
        return itertools.zip_longest(*args, fillvalue=fillvalue)
    if incomplete == "strict":
        return zip(*args, strict=True)
    if incomplete == "ignore":
        return zip(*args)
    else:
        raise ValueError("Expected fill, strict, or ignore")


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


@make_traceable
def md5(string: str):
    if not isinstance(string, str):
        string = str(string)
    md = hashlib.md5()
    encode = string.encode("UTF-8")
    md.update(encode)
    return md.hexdigest()


@make_traceable
def stack_iterables(*iterables):
    for iterable in iterables:
        for item in iterable:
            yield item


def run_once(f):
    def wrapper(*args, **kwargs):
        if not wrapper.has_run:
            wrapper.has_run = True
            return f(*args, **kwargs)

    wrapper.has_run = False
    return wrapper


@make_traceable
def add_to_bucket_whitelist(
    file_urls: Union[str, List[str]],
    whitelist_filename: Optional[str] = ".ltfs_whitelist",
    bucket_cilent: Optional[BucketClient] = None,
) -> NoReturn:
    if bucket_cilent is None:
        bucket_cilent = BucketClient()

    urls_mapping: Dict[str, List[str]] = dict()
    for url in _as_list(file_urls):
        url = local_path_to_url(url)
        bucket_name = (
            url.strip("dmpv2://").strip(os.path.sep).split(os.path.sep)[0]
        )
        if bucket_name not in urls_mapping:
            urls_mapping[bucket_name] = list()
        urls_mapping[bucket_name].append(url)

    for bucket_name, urls in urls_mapping.items():
        root = url_to_local_path(bucket_cilent.get_mount_root(bucket_name))
        whitelist_filepath = os.path.join(root, whitelist_filename)
        if os.path.exists(whitelist_filepath):
            with open(whitelist_filepath, "r") as fin:
                whitelist = {f.strip("\n") for f in fin if f.strip("\n")}
        else:
            whitelist = set()

        with open(whitelist_filepath, "a+") as fout:
            for url in urls:
                file = os.path.relpath(url_to_local_path(url), root)
                logger.warning(
                    f"Add {url} to whitelist of bucket({bucket_name})"
                )
                if file not in whitelist:
                    fout.write(f"{file}\n")

    return urls_mapping
