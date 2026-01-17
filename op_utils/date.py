import datetime
import time
from typing import List

__all__ = [
    "get_date_list",
    "get_today_date_str",
]


def get_date_list(
    start_date,
    end_date,
    date_str_format="%Y-%m-%d",
    except_date_list=(),
    reverse=False,
):

    strp_date_start = datetime.datetime.strptime(
        start_date + " 00:00:00", "%Y%m%d %H:%M:%S"
    )
    strp_date_end = datetime.datetime.strptime(
        end_date + " 23:59:59", "%Y%m%d %H:%M:%S"
    )
    assert (
        strp_date_end > strp_date_start
    ), "Please make sure date-end is older than date-start."

    except_date_list = [
        datetime.datetime.strptime(date + " 00:00:00", "%Y%m%d %H:%M:%S")
        for date in except_date_list
    ]

    date_list = []
    date = strp_date_start
    while date < strp_date_end:
        if date not in except_date_list:
            date_list.append(date.strftime(date_str_format))
        date = date + datetime.timedelta(1)

    if reverse:
        date_list = date_list[::-1]

    return date_list


def get_today_date_str(output_date_format="%Y%m%d"):
    now = datetime.datetime.now()
    return now.strftime(output_date_format)


def format_date_time(items: List[str]) -> str:
    """Generate a string of format date time from a list .

    Args:
        items (List[str]): A list of date, time, millisec, \
            format is like ['20221031', '144829', '990'].

    Returns:
        str: A string of format date time like '2022-10-31 14:48:29', \
            can be used to query pack.
    """
    timestamp = ""
    get_timestamp_flag = 0

    def _checktime(item):
        try:
            if len(item) == 8:
                time.strptime(
                    item[:4] + " " + item[4:6] + " " + item[6:8], "%Y %m %d"
                )
            elif len(item) == 6:
                time.strptime(
                    item[:2] + " " + item[2:4] + " " + item[4:6], "%H %M %S"
                )
            else:
                return False
            return True
        except BaseException:
            return False

    for item in items:
        if len(item) == 8 and _checktime(item):
            timestamp = (
                timestamp + item[:4] + "-" + item[4:6] + "-" + item[6:8]
            )
            timestamp = timestamp + " "
            items.remove(item)
            get_timestamp_flag += 1
            break

    for item in items:

        if len(item) == 6 and _checktime(item):
            timestamp = (
                timestamp + item[:2] + ":" + item[2:4] + ":" + item[4:6]
            )
            get_timestamp_flag += 1
            break

    return timestamp if get_timestamp_flag == 2 else "InValidTimeStamp"
