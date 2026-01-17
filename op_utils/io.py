import collections
import glob
import hashlib
import json
import logging
import os
import os.path as osp
import time
import uuid
from tempfile import NamedTemporaryFile, _TemporaryFileWrapper
from typing import Iterator, List, Optional

import requests
from hatbc.aidi.dmp_client import DmpClient
from hatbc.filestream.bucket.client import is_dmp_url
from hatbc.resource_manager import get_resource
from hatbc.utils import _as_list, deprecated_warning
from hatbc.workflow.operator import Operator
from hatbc.workflow.trace import make_traceable

from hdflow.utils.path import (
    dmp_url_to_local_path,
    is_weburl,
    local_path_to_url,
    url_to_local_path,
)

__all__ = [
    "read_json",
    "read_multiline_json",
    "write_json",
    "write_multiline_json",
    "write_multiple_json",
    "ContinuousJsonWriter",
    "write_to",
    "SimpleJsonDataIter",
    "get_simple_json_dataiter",
    "get_simple_json_dataiter_form_dir",
    "calculate_file_md5",
]

logger = logging.getLogger(__name__)


def _get_unique_stamp() -> str:
    """Get a unique stamp.

    Returns:
        str: unique stamp.
    """
    return f"{int(time.time())}_{uuid.uuid4().hex}"


class CacheFile:
    def __init__(self, url: str):
        self.url = url
        self._cache_file: _TemporaryFileWrapper = None

    @property
    def filename(self) -> str:
        return osp.basename(self.url)

    @property
    def cache_file(self) -> _TemporaryFileWrapper:
        if self._cache_file is None:
            if is_weburl(self.url):
                self._cache_file = NamedTemporaryFile(
                    suffix=osp.basename(self.url)
                )
                req = requests.get(url=self.url)
                if not req.ok:
                    raise FileNotFoundError(self.url)
                self._cache_file.write(req.content)
                self._cache_file.flush()
            else:
                filepath = osp.abspath(url_to_local_path(self.url))
                self._cache_file = _TemporaryFileWrapper(
                    file=open(filepath, mode="rb"),
                    name=filepath,
                    delete=False,
                )

        return self._cache_file

    def is_same(self, url: str) -> bool:
        return url == self.url

    @property
    def file(self):
        return self.cache_file.file

    @property
    def name(self) -> str:
        return self.cache_file.name

    def __enter__(self):
        self.cache_file.__enter__()
        return self

    def __exit__(self, exc, value, tb):
        result = self.cache_file.__exit__(exc=exc, value=value, tb=tb)
        return result

    def __iter__(self) -> Iterator:
        return self.cache_file.__iter__()


@make_traceable
def read_json(path):
    """Read json file.

    Args:
        path (str): path of json file.
    """
    return json.load(open(path, "r"))


@make_traceable
def read_multiline_json(path):
    class _IterableJsonData(collections.abc.Iterable):
        def __init__(self, json_path: str):
            self._json_path = json_path

        def __iter__(self):
            with open(self._json_path) as fin:
                for line in fin:
                    data = json.loads(line)
                    yield data

    return _IterableJsonData(path)


@make_traceable
def write_multiline_txt(dataiter, path):
    with open(path, "w") as fout:
        for data in dataiter:
            fout.write(data)
            fout.write("\n")


@make_traceable
def write_json(data, path, indent=None):
    json.dump(data, open(path, "w"), indent=indent)


@make_traceable
def write_multiline_json(dataiter, output_path):
    with open(output_path, "w") as fout:
        for data in dataiter:
            fout.write(json.dumps(data) + "\n")


@make_traceable
def write_multiple_json(dataiters, out_paths=None, *, out_dir=None):
    logger.info("Writing multiple json files...")

    if not (bool(out_paths) ^ bool(out_dir)):
        raise ValueError("Either out_paths or out_dir must be specified.")
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        out_paths = [
            os.path.join(out_dir, f"{_get_unique_stamp()}_{i}.json")
            for i in range(len(dataiters))
        ]

    if len(dataiters) != len(out_paths):
        raise ValueError("dataiters and out_paths must have the same length.")

    for dataiter, out_path in zip(dataiters, out_paths):
        write_multiline_json(dataiter, out_path)

    logger.info(f"Write json files to {out_paths}.")
    return out_paths


class ContinuousJsonWriter(Operator):
    _instance = None

    def __init__(self, append_when_file_exists=False):
        super().__init__()
        self._append_when_file_exists = append_when_file_exists
        # NOTE: don't use fid here, because the operator
        # may not be cleand, and then the result cannot
        # be flushed....
        self._opend = set()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def forward(self, dataiter, output_path):
        if output_path not in self._opend:
            if self._append_when_file_exists and os.path.exists(output_path):
                fid = open(output_path, "a")
            else:
                fid = open(output_path, "w")
            self._opend.add(output_path)
        else:
            fid = open(output_path, "a")
        with fid:
            for data in dataiter:
                data_j = json.dumps(data)
                fid.write(data_j + "\n")


@make_traceable
def write_to(data, path, mode="w"):
    with open(path, mode) as fout:
        fout.write(data)


class SimpleJsonDataIter(object):
    # TODO (weizhen.wu): docs

    def __init__(
        self,
        json_paths: List[str],
        dmp_client: Optional[DmpClient] = None,
        max_length: Optional[int] = None,
    ):
        self._json_paths = _as_list(json_paths)
        self._max_length = max_length
        if dmp_client is not None:
            deprecated_warning(
                "`dmp_client` is deprecated and will be removed in the future!"
            )

    def __iter__(self):
        cnt = 0
        for dataset_json_path in self._json_paths:
            if is_dmp_url(dataset_json_path):
                dataset_json_path = dmp_url_to_local_path(dataset_json_path)
            with open(dataset_json_path) as fin:
                for line in fin:
                    data = json.loads(line)
                    yield data
                    cnt += 1
                    if (
                        self._max_length is not None
                        and cnt >= self._max_length
                    ):  # noqa
                        return

    def __setstate__(self, state):
        self._json_paths = state["json_paths"]
        self._max_length = state["max_length"]

    def __getstate__(self):
        state = dict(
            json_paths=self._json_paths,
            max_length=self._max_length,
        )
        return state


class ModuleIDJsonDataIter(object):
    def __init__(
        self,
        json_paths: List[str],
        module_ids: List[int],
        dmp_client: Optional[DmpClient] = None,
        max_length: Optional[int] = None,
        sample_interval: Optional[int] = 1,
    ):
        if isinstance(json_paths, (list, tuple)):
            self.simple_dataiter = SimpleJsonDataIter(
                json_paths=json_paths,
                max_length=max_length,
                dmp_client=dmp_client,
            )
        else:
            self.simple_dataiter = json_paths

        self.module_ids = _as_list(module_ids)
        self.sample_interval = sample_interval

    def __iter__(self):
        idx = 0
        for data in self.simple_dataiter:
            if data["module_id"] in self.module_ids:
                idx += 1
                if idx % self.sample_interval == 0:
                    yield data

    def __setstate__(self, state):
        self.module_ids = state["module_ids"]
        self.simple_dataiter = state["simple_dataiter"]
        self.sample_interval = state["sample_interval"]

    def __getstate__(self):
        state = dict(
            module_ids=self.module_ids,
            simple_dataiter=self.simple_dataiter,
            sample_interval=self.sample_interval,
        )
        return state


@make_traceable
def get_simple_json_dataiter(json_paths, max_length=None, dmp_client=None):
    if dmp_client is None:
        dmp_client = get_resource(DmpClient)
    return SimpleJsonDataIter(
        json_paths=json_paths, max_length=max_length, dmp_client=dmp_client
    )


@make_traceable
def get_module_id_json_dataiter(
    json_paths,
    module_ids,
    max_length=None,
    seperated_iter_by_module: Optional[bool] = False,
    sample_interval: Optional[int] = 1,
):
    if seperated_iter_by_module:
        return [
            ModuleIDJsonDataIter(
                json_paths=json_paths,
                module_ids=i,
                max_length=max_length,
                sample_interval=sample_interval,
            )
            for i in module_ids
        ]
    return ModuleIDJsonDataIter(
        json_paths=json_paths,
        module_ids=module_ids,
        max_length=max_length,
        sample_interval=sample_interval,
    )


@make_traceable
def get_simple_json_dataiter_form_dir(
    json_dir, max_length=None, dmp_client=None
):
    if is_dmp_url(json_dir):
        local_json_dir = dmp_url_to_local_path(json_dir)
    else:
        local_json_dir = json_dir
    assert os.path.isdir(
        local_json_dir
    ), f"{local_json_dir} is not a directory"
    json_paths = glob.glob(os.path.join(local_json_dir, "*.json"))
    return get_simple_json_dataiter(json_paths, max_length, dmp_client)


class ListImageDataIter(object):
    def __init__(self, directory, max_length=None):
        self.directory = url_to_local_path(directory)
        self.max_length = max_length

    def __iter__(self):
        cnt = 0
        for file_name in os.listdir(self.directory):
            file_url = os.path.join(self.directory, file_name)
            data = {
                "image_url": local_path_to_url(file_url, allow_invalid=True),
                "image_key": file_name,
            }
            yield data
            cnt += 1
            if self.max_length is not None and cnt >= self.max_length:  # noqa
                return


@make_traceable
def get_list_image_dataiter(directory, max_length=None):
    return ListImageDataIter(directory, max_length)


@make_traceable
def calculate_file_md5(
    file_path,
    hash_factory=hashlib.md5,
    chunk_num_blocks=8192,
    verbose=False,
):
    if verbose:
        logger.info(f"calculate MD5 for file:{file_path}")
    h = hash_factory()
    with open(file_path, "rb") as f:
        for chunk in iter(
            lambda: f.read(chunk_num_blocks * h.block_size), b""
        ):
            h.update(chunk)
    return h.hexdigest()
