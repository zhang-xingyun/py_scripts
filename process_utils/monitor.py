import os
from dataclasses import dataclass
from typing import List, Optional, Union

import psutil

__all__ = ["ProcessMemoryInfo", "get_process_memory"]


@dataclass
class ProcessMemoryInfo:
    pid: int
    cmdline: str
    total_memory_rss_in_gb: float
    total_memory_percent: float

    @classmethod
    def from_process(
        cls, process: Union[int, psutil.Process]
    ) -> "ProcessMemoryInfo":
        if isinstance(process, int):
            process = psutil.Process(process)
        total_memory_rss = process.memory_info().rss / 1024 / 1024 / 1024
        total_memory_percent = process.memory_percent()
        return cls(
            pid=process.pid,
            cmdline=process.cmdline(),
            total_memory_rss_in_gb=round(total_memory_rss, 4),
            total_memory_percent=round(total_memory_percent, 4),
        )

    def __eq__(self, other):
        flag = type(self) is type(other)
        if flag:
            flag &= self.pid == other.pid
        return flag

    def __hash__(self) -> int:
        return hash(self.pid)


def get_process_memory(
    pid: Optional[int] = None, with_children: Optional[bool] = True
) -> List[ProcessMemoryInfo]:
    """Get process and its children process memory info.

    Parameters
    ----------
    pid : int, optional
        Process id, by default current process.
    with_children : bool, optional
        Include children process or not, by default True

    Returns
    -------
    List[ProcessMemoryInfo]
        Memory info for each process.
    """

    if pid is None:
        pid = os.getpid()

    process = psutil.Process(pid)

    outputs = [ProcessMemoryInfo.from_process(process)]

    if with_children:
        for child in process.children(recursive=True):
            try:
                child_outputs = get_process_memory(child.pid)
                outputs.extend(child_outputs)
            except Exception:
                pass

    # remove duplicate process
    outputs = list(set(outputs))
    outputs.sort(key=lambda x: x.pid)

    return outputs
