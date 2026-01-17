import random
import string
from typing import Tuple

__all__ = ["random_string", "replace_string_prefix"]


def random_string(length: int = 16) -> str:
    """Generate a random string.

    Args:
        length (int, optional): length of the string. Defaults to 16.

    Returns:
        str: random string
    """
    return "".join(
        random.choices(string.ascii_letters + string.digits, k=length)
    )


def replace_string_prefix(string: str, prefix_tuple: Tuple[str, str]):
    """Replaces the prefix of a given string with a new prefix.

    Args:
        string (str): The input string that needs to have its prefix replaced.
        prefix_tuple (Tuple[str, str]): A tuple of two strings. \
            The first string is the source prefix that needs to be replaced, \
            and the second string is the new prefix that will replace it.

    Raises:
        ValueError: If the size of prefix_tuple is not 2 or \
            if the input string does not start with the source prefix.

    Returns:
        str: A new string with the old prefix replaced by the new prefix.
    """

    if len(prefix_tuple) != 2:
        raise ValueError(
            "size of prefix_tuple must be 2, provided: %d"
            % (len(prefix_tuple))
        )  # noqa

    src_prefix, dst_prefix = prefix_tuple
    if not string.startswith(src_prefix):
        raise ValueError(
            'path "%s" not startswith "%s"' % (string, src_prefix)
        )

    dst_string = dst_prefix + string[len(src_prefix) :]
    return dst_string
