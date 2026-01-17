from typing import Any, Dict, List

__all__ = ["get_value_from", "correct_typo", "reverse_dict"]


def get_value_from(data: Dict, keys: List, default=None):
    """Get value from a dictionary.

    Args:
        data (dict): input dictionary.
        keys (list): list of keys.
        default: default value if key is not found.

    Returns:
        Any: value from the dictionary.
    """
    res = default
    for key in keys:
        if key in data:
            res = data[key]
            break
    return res


def reverse_dict(dict1: Dict) -> Dict:
    """Reverse dictionary's key and values.

    dict1 = {'a':[1,2], 'b':[1,2,3], 'c':[1]}
    dict2 = {1: ['a', 'b', 'c'], 2: ['a', 'b'], 3: ['b']}

    dict2 will be same type as dict1. (SortedDict, OrderedDict, dict, ...)

    Args:
        dict1 (Dict): dict to reverse

    Raises:
        TypeError: if input is not a dictionary

    Returns:
        Dict: reversed dict
    """
    if not isinstance(dict1, dict):
        raise TypeError("Input should be a dictionary.")

    dict2 = type(dict1)()
    for k, vs in dict1.items():
        for v in vs:
            dict2.setdefault(v, []).append(k)
    return dict2


def correct_typo(dict1: Dict, right_key: Any, wrong_keys: List) -> Dict:
    """Corrtect typo in dictionary key.

    The correction process is in-place.

    Args:
        dict1 (Dict): dict to be corrected
        right_key (Any): correct key
        wrong_keys (List): wrong keys

    Returns:
        Dict: corrected dict
    """
    for k in wrong_keys:
        if dict1.get(right_key):
            break
        dict1[right_key] = dict1.pop(k, None)
    return dict1
