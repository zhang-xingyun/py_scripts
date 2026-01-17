__all__ = ["SkipDataException", "SkipCorruptedDataException"]


class SkipDataException(Exception):
    """Skip data , raise this exception."""

    def __init__(self, message="Skipping data"):
        self.message = message
        super().__init__(self.message)


class SkipCorruptedDataException(SkipDataException):
    """Skip corrupted data , raise this exception."""

    def __init__(self, message="Skipping corrupted data"):
        self.message = message
        super().__init__(self.message)
