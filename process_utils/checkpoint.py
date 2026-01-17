import os
import pickle
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Optional

from hatbc.database.mongodb_client import get_mongodb_client

__all__ = [
    "MongoDBProgressHandler",
    "FileProgressHandler",
    "DataFinishFlag",
]


@dataclass
class DataFinishFlag:
    data: Any


class ProgressHandler(ABC):
    """Abstract base class for progress handlers."""

    @abstractmethod
    def mark_processed(self, data: Any):
        """Mark the specified data as processed.

        Args:
            data (Any): The data to mark as processed.
        """

    @abstractmethod
    def is_processed(self, data: Any):
        """Check if the specified data is already processed.

        Args:
            data (Any): The data to check.

        Returns:
            bool: True if the data is processed, False otherwise.
        """

    @abstractmethod
    def save_checkpoint(self):
        """Save the current progress checkpoint."""

    @abstractmethod
    def load_checkpoint(self):
        """Load the progress checkpoint."""

    def close(self):
        """Close the progress handler and save the checkpoint."""
        self.save_checkpoint()


class MongoDBProgressHandler(ProgressHandler):
    """Progress handler that uses MongoDB to track progress.

    Args:
        collection (str): The name of the MongoDB collection to use.
        db (str, optional): The name of the MongoDB database to connect to.
            Defaults to 'auto_cv'.
        transform (Optional[Callable], optional): A transformation function
            to apply to the data before storing. Defaults to None.
    """

    def __init__(
        self,
        collection: str,
        db: str = "auto_cv",
        transform: Optional[Callable] = None,
    ):
        self.collection = collection
        self.db = db
        self.transform = transform

        self.client = get_mongodb_client(
            db=self.db,
            table=self.collection,
        )

    def mark_processed(self, data: Any):
        """Mark the specified data as processed.

        Args:
            data (Any): The data to mark as processed.
        """
        self.client.insert_one(self._apply_transform(data))

    def is_processed(self, data: Any):
        """Check if the specified data is already processed.

        Args:
            data (Any): The data to check.

        Returns:
            bool: True if the data is processed, False otherwise.
        """
        result = self.client.find_one(self._apply_transform(data))
        return result is not None

    def save_checkpoint(self):
        """Save the current progress checkpoint."""
        # MongoDB automatically persists the changes

    def load_checkpoint(self):
        """Load the progress checkpoint."""

    def close(self):
        """Close the client and save the checkpoint."""
        self.client.close()

    def _apply_transform(self, data: Any):
        data = deepcopy(data)
        if self.transform is not None:
            return self.transform(data)
        return data


class FileProgressHandler(ProgressHandler):
    """Progress handler that uses a file to track progress.

    Args:
        progress_file (Optional[str], optional): The path to the progress
            file. Defaults to None.
        transform (Optional[Callable], optional): A transformation function
            to apply to the data before storing. Defaults to None.
        ckpt_interval (int, optional): The interval (in number of processed
            items) at which to save the checkpoint. Defaults to 5.
    """

    def __init__(
        self,
        progress_file: Optional[str] = None,
        transform: Optional[Callable] = None,
        ckpt_interval: int = 5,
    ):
        self.progress_file = progress_file or "progress.pkl"
        self.transform = transform
        self.ckpt_interval = ckpt_interval

        self.load_checkpoint()

    def mark_processed(self, data: Any):
        """Mark the specified data as processed.

        Args:
            data (Any): The data to mark as processed.
        """
        self.progress.add(self._apply_transform(data))
        if len(self.progress) % self.ckpt_interval == 0:
            self.save_checkpoint()

    def is_processed(self, data: Any):
        """Check if the specified data is already processed.

        Args:
            data (Any): The data to check.

        Returns:
            bool: True if the data is processed, False otherwise.
        """
        return self._apply_transform(data) in self.progress

    def save_checkpoint(self):
        """Save the current progress checkpoint."""
        with open(self.progress_file, "wb") as f:
            pickle.dump(self.progress, f)

    def load_checkpoint(self):
        """Load the progress checkpoint."""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, "rb") as f:
                self.progress = pickle.load(f)
        else:
            self.progress = set()

    def _apply_transform(self, data: Any):
        data = deepcopy(data)
        if self.transform is not None:
            return self.transform(data)
        return data
