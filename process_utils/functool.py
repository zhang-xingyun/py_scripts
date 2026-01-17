import collections

import toolz
from hatbc.workflow.trace import _make_function_traceable, make_traceable

__all__ = [
    "filter",
    "map",
    "flatten",
    "compose",
    "starmap",
    "filter_curry",
    "map_curry",
]

_base_types = (str, int, float, bool, type(None), bytes)


@make_traceable
def flatten(
    data, *, return_iter=True, flatten_types=(collections.abc.Iterable,)
):
    """Flatten data.

    Args:
        data: data to be flattened.
        return_iter: whether to return an iterator.
        flatten_types: types to be flattened.

    Returns:
        data: flattened data.
    """
    if not isinstance(data, flatten_types) or isinstance(data, _base_types):
        return [data]

    if isinstance(data, flatten_types):
        data = (
            item
            for sub_data in data
            for item in flatten(sub_data, flatten_types=flatten_types)
        )

    if return_iter:
        return data

    return list(data)


def curry_high_order_function(
    high_func, first_func, return_iter=True, *args, **kwargs
):
    """Curry high order function.

    Args:
        high_func: high order function.
        first_func: first class function to be passed to high_func.
        return_iter: whether to return an iterator.
        *args: args to be passed to the first class function. `args` will be
            passed to `first_func` start from the first argument. If the first
            argument of `first_func` is the data to be processed, DO NOT use
            this argument, use `kwargs` instead.
        **kwargs: kwargs to be passed to the first class function.

    Returns:
        func: curried function.
    """
    if isinstance(first_func, type):
        assert callable(first_func), f"{first_func} is not callable."
        first_func = first_func.__call__

    _high_fn = toolz.curry(high_func)
    _first_fn = toolz.curry(first_func, *args, **kwargs)

    if return_iter:
        return _high_fn(_first_fn)

    return toolz.compose(list, _high_fn(_first_fn))


@make_traceable
def filter_curry(func, *args, **kwargs):
    return curry_high_order_function(filter, func, *args, **kwargs)


@make_traceable
def map_curry(func, *args, **kwargs):
    return curry_high_order_function(map, func, *args, **kwargs)


filter = _make_function_traceable(filter)

map = _make_function_traceable(map)

compose = _make_function_traceable(toolz.compose_left)

starmap = _make_function_traceable(toolz.curried.map)
