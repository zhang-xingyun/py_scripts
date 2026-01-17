"""Utils for building functions / classes.

The content in this file is not bind with any specific module. They are used to
simplify the process of building functions / classes.

"""
import itertools
from collections.abc import Sequence
from types import GeneratorType
from typing import Optional, Tuple

from hatbc.workflow import make_traceable

__all__ = [
    "array_cls",
    "get_shape",
    "is_shape_consistent",
    "equal_or_contain",
    "as_list",
    "get_item",
]

array_cls = (list, tuple)


@make_traceable
def get_len(data: Sequence) -> int:
    return len(data)


@make_traceable
def get_item(data: Sequence, idx: Optional[int], as_list: bool = True):
    res = data[idx]
    if not as_list:
        return res
    return [res]


@make_traceable
def get_shape(data: Sequence) -> Tuple:
    """Get the shape of a sequence.

    Args:
        data (Sequence): input sequence.

    Returns:
        Tuple: shape of the sequence.
    """
    shape = ()
    if not isinstance(data, Sequence) or len(data) == 0:
        return shape

    if not is_shape_consistent(data):
        raise ValueError("Input data is not consistent.")

    d0 = data[0]
    if isinstance(d0, Sequence):
        if any(len(d) != len(d0) for d in data):
            raise ValueError(
                "Input data has inconsistent length in the one dimension."
            )
        shape = (len(data),) + get_shape(d0)
    else:
        shape = (len(data),)

    return shape


def is_shape_consistent(data: Sequence) -> bool:
    """Check if the shape of a sequence is consistent.

    Args:
        data (Sequence): input sequence.

    Returns:
        bool: True if the shape is consistent.

    Examples:
        >>> is_shape_consistent([1, 2, 3])
        True
        >>> is_shape_consistent([[1, 2, 3], [4, 5, 6]])
        True
        >>> is_shape_consistent([[1, 2, 3], [4, 5]])
        True
        >>> is_shape_consistent([[1, 2, 3], [4, 5, [6]]])
        False
    """
    if isinstance(data, GeneratorType):
        raise TypeError(
            "For thread safty and memory usage, this function doesn't accept "
            "generator."
        )

    if not isinstance(data, Sequence) or len(data) == 0:
        return True

    is_seq = isinstance(data[0], Sequence)
    if not all(is_seq == isinstance(d, Sequence) for d in data):
        return False

    if not is_seq:
        return True

    return is_shape_consistent(list(itertools.chain(*data)))


def equal_or_contain(source, target):
    """Check if source is equal to target or contains target.

    Args:
        source: source sequence or object.
        target: target object.

    Returns:
        bool: True if source is equal to target or contains target.

    Examples:
        >>> equal_or_contain([1, 2, 3], 1)
        True
        >>> equal_or_contain([1, 2, 3], [1, 2])
        True
        >>> equal_or_contain(1, 1)
        True
        >>> equal_or_contain(1, 2)
        False
        >>> equal_or_contain([1, 2, 3], [1, 3, 4])
        False
    """
    if not isinstance(source, array_cls) and not isinstance(target, array_cls):
        return source == target
    if not isinstance(source, array_cls) and isinstance(target, array_cls):
        return False
    if isinstance(source, array_cls) and not isinstance(target, array_cls):
        return target in source
    if isinstance(source, array_cls) and isinstance(target, array_cls):
        return all(t in source for t in target)


def as_list(data, keep_none=False) -> list:
    """Convert data to list.

    Examples:
        >>> as_list(1)
        [1]
        >>> as_list([1, 2, 3])
        [1, 2, 3]
        >>> as_list((1, 2, 3))
        [1, 2, 3]

    Args:
        data: input data.
        keep_none: keep None or not. set false to return [] if data is None.
            Otherwise return [None].

    Returns:
        list: list of data.
    """
    if not keep_none and data is None:
        return []
    if isinstance(data, array_cls):
        return list(data)

    return [data]
