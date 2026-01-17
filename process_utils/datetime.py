import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Union

import numpy as np

logger = logging.getLogger(__name__)

__all__ = [
    "TimeZone",
    "get_time_start_end_from_datestr",
    "ts2timestr",
    "format_time",
    "get_timestamps_by_frequency",
    "format_timestamp",
    "generate_timestamp_by_unit",
]


@dataclass
class TimeZone:
    """Time zone."""

    UTC0 = timezone.utc
    UTC8 = timezone(timedelta(hours=8))


def get_time_start_end_from_datestr(
    start_datestr, end_datestr, tzinfo=TimeZone.UTC8
):
    """Get start and end time from date string.

    Args:
        start_datestr (str): start date string, e.g. 20210101.
        end_datestr (str): end date string, e.g. 20210101.
        tzinfo (timezone, optional): timezone.
            Defaults to timezone(timedelta(hours=8)), UTC+8.

    Returns:
        int, int: start time, end time.
    """
    date_time = datetime.strptime(start_datestr, "%Y%m%d")
    year, month, day = date_time.year, date_time.month, date_time.day
    start_time = int(
        datetime(year, month, day, 00, 00, 00, tzinfo=tzinfo).timestamp()
        * 1000
    )
    date_time = datetime.strptime(end_datestr, "%Y%m%d")
    year, month, day = date_time.year, date_time.month, date_time.day
    end_time = int(
        datetime(year, month, day, 23, 59, 59, tzinfo=tzinfo).timestamp()
        * 1000
    )
    return start_time, end_time


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
    if isinstance(x, int) or isinstance(x, np.int64):
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


def _get_timestamp_unit(ts: int):
    assert isinstance(ts, int), f"Unsupported timestamp type: {type(ts)}"
    if len(str(ts)) == 10:
        return "second"
    elif len(str(ts)) == 13:
        return "millisecond"
    elif len(str(ts)) == 16:
        return "microsecond"
    else:
        raise ValueError(f"Unsupported timestamp length: {len(ts)}")


def _convert_ts_unit(
    ts: int,
    source_ts_unit: Literal["second", "millisecond", "microsecond"],
    target_ts_unit: Literal["second", "millisecond", "microsecond"],
):
    assert isinstance(ts, int), f"Unsupported timestamp type: {type(ts)}"
    if source_ts_unit == target_ts_unit:
        return ts
    if source_ts_unit == "second" and target_ts_unit == "millisecond":
        return ts * 1000
    elif source_ts_unit == "second" and target_ts_unit == "microsecond":
        return ts * 1000 * 1000
    elif source_ts_unit == "millisecond" and target_ts_unit == "second":
        return ts // 1000
    elif source_ts_unit == "microsecond" and target_ts_unit == "second":
        return ts // 1000 // 1000
    elif source_ts_unit == "millisecond" and target_ts_unit == "microsecond":
        return ts * 1000
    elif source_ts_unit == "microsecond" and target_ts_unit == "millisecond":
        return ts // 1000


def generate_timestamp_by_unit(
    ts: Union[datetime, int],
    target_ts_unit: Literal["second", "millisecond", "microsecond"],
):
    if isinstance(ts, datetime):
        ts = int(ts.timestamp() * 1000) + ts.microsecond
    source_ts_unit = _get_timestamp_unit(ts)
    return _convert_ts_unit(ts, source_ts_unit, target_ts_unit)


def format_timestamp(
    x: Union[int, str, datetime],
    pattern: str = "%Y-%m-%d %H:%M:%S",
    ts_unit: Literal["second", "millisecond", "microsecond"] = "millisecond",
    tzinfo: TimeZone = TimeZone.UTC8,
) -> str:
    """Get timestamp in ts unit format.

    Args:
        x (Union[int, str, datetime]): time to be formated
        pattern (str, optional):  pattern of input time. This is only useful \
            when input time is str type. Defaults to "%Y-%m-%d %H:%M:%S".
        ts_unit (Literal[&quot;second&quot;, &quot;millisecond&quot;, &quot;microsecond&quot;], optional): format ts unit. Defaults to "millisecond".  # noqa
        tzinfo (timezone, optional): timezone.
            Defaults to timezone(timedelta(hours=8)), UTC+8.

    """
    if isinstance(x, str):
        x = datetime.strptime(x, pattern)
    if isinstance(x, datetime) and tzinfo:
        x = x.replace(tzinfo=tzinfo)
    assert isinstance(x, int) or isinstance(
        x, datetime
    ), f"Unsupported timestamp type: {type(x)}"
    return generate_timestamp_by_unit(x, ts_unit)


def get_timestamps_by_frequency(
    start_timestamp: int,
    end_timestamp: int,
    frequency: Union[int, float],
    with_ms: bool = True,
    contain_end: bool = True,
):
    """Generate a list of timestamps within a given range based on \
        a specified frequency.

    Args:
        start_timestamp (Union[int, float]): The starting timestamp of \
            the range.
        end_timestamp (Union[int, float]): The ending timestamp of \
            the range.
        frequency (Union[int, float]): The frequency(1/s) at which timestamps \
            should be generated.
        with_ms (bool, optional): If input timestamps and output timestamps \
            contain ms. Defaults to True.
        contain_end (bool, optional): Determines whether the end_timestamp \
            should be included in the result. Defaults to True.

    Returns:
        List: A list of timestamps generated based on the given frequency.
    """
    if start_timestamp > end_timestamp:
        warning_message = (
            f"start_timestamp {start_timestamp} cannot be "
            f"greater than end_timestamp {end_timestamp}."
        )
        logger.warning(warning_message)
        return []
    if frequency <= 0:
        warning_message = (
            f"Illegal frequency {frequency}. The frequency "
            "needs to be greater than 0."
        )
        logger.warning(warning_message)
        return []

    if with_ms:
        start_timestamp /= 1000
        end_timestamp /= 1000

    total_nums = int((end_timestamp - start_timestamp) * frequency) + int(
        contain_end
    )
    interval = 1 / float(frequency)
    timestamps = [start_timestamp + interval * t for t in range(total_nums)]

    if with_ms:
        timestamps = list(map(lambda x: int(x * 1000), timestamps))

    return timestamps


def get_dates_list(start_date: str, end_date: str):
    """Generate a list of dates between start_date and end_date. closed interval.

    Args:
        start_date (str): The starting date. Like "20231111".
        end_date (str): The ending date. Like "20231112".

    Returns:
        List(str): A list of dates.
    """

    start_date = datetime.strptime(start_date, "%Y%m%d")
    end_date = datetime.strptime(end_date, "%Y%m%d")

    middle_dates = []
    current_date = start_date
    while current_date <= end_date:
        middle_dates.append(current_date.strftime("%Y%m%d"))
        current_date += timedelta(days=1)

    return middle_dates
