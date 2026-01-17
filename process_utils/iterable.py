__all__ = ["BackupWrapper", "group"]


class BackupWrapper:
    def __init__(self, it) -> None:
        self._it = it
        self._bak = []

    def __iter__(self):
        return self

    def __next__(self):
        data = next(self._it)
        self._backup.append(data)
        return data

    def next_backup(self):
        return self._bak.pop(0)

    @property
    def backup(self):
        ret = self._bak
        self._bak = []
        return ret


def group(data_iter, batch_size: int, drop_last: bool = False):
    """Group iterable data into batches.

    Args:
        iterable: iterable to be grouped.
        batch_size: batch size.
        drop_last: drop last batch if it is not full.

    Yields:
        Iterable: grouped iterable.
    """
    batch = []
    for data in data_iter:
        batch.append(data)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch and not drop_last:
        yield batch
