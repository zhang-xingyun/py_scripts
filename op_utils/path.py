import logging
import os
import os.path as osp
import shutil
import uuid
from typing import Optional

import hatbc.filestream.io as fs
from aidisdk.utils.env import env_job_id, running_in_cluster
from hatbc.aidi.dmp_client import DmpClient
from hatbc.filestream.bucket import get_bucket_client
from hatbc.filestream.bucket.client import BucketClient
from hatbc.filestream.file_helper import FileHelper
from hatbc.resource_manager import get_resource
from hatbc.utils import deprecated_warning
from hatbc.workflow.trace import make_traceable

logger = logging.getLogger(__name__)


@make_traceable
def dirname(path: str):
    return os.path.dirname(path)


@make_traceable
def basename(path: str):
    return os.path.basename(path)


@make_traceable
def makedirs(
    path: str,
    exist_ok: Optional[bool] = False,
    client: Optional[BucketClient] = None,
):
    try:
        local_path = url_to_local_path(path)
        os.makedirs(local_path, exist_ok=exist_ok)
    except PermissionError:
        client = client or BucketClient()
        bucket_url = local_path_to_url(path)
        if client.exists(bucket_url) and not exist_ok:
            raise OSError(f"Path eixist, can`t create target path: {path}")
        if not client.exists(bucket_url):
            client.mkdir(bucket_url, recursive=True)


@make_traceable
def rm(path, ignore_errors=False, onerror=None):
    return shutil.rmtree(path, ignore_errors=ignore_errors, onerror=onerror)


@make_traceable
def exists(path):
    return os.path.exists(path)


@make_traceable
def join(*paths):
    return os.path.join(*paths)


@make_traceable
def get_tmpdir(file_helper=None):
    if file_helper is None:
        file_helper = get_resource(FileHelper)
    return file_helper.get_tmp_dir(with_time_suffix=True)


@make_traceable
def dmp_url_to_local_path(path, dmp_client=None, *, allow_fail: bool = True):
    deprecated_warning(
        "dmp_url_to_local_path is deprecated. Use url_to_local_path instead."
    )
    return url_to_local_path(path, allow_invalid_bucket_url=allow_fail)


@make_traceable
def local_path_to_dmp_url(path, dmp_client=None, allow_invalid: bool = False):
    deprecated_warning(
        "local_path_to_dmp_url is deprecated. Use local_path_to_url instead."
    )
    return local_path_to_url(path, allow_invalid=allow_invalid)


@make_traceable
def transform_to_dmp_path(path, bkt_client=None, allow_invalid: bool = False):
    deprecated_warning(
        "transform_to_dmp_path is deprecated. Use local_path_to_url instead."
    )
    return local_path_to_url(path, allow_invalid=allow_invalid)


@make_traceable
def transform_to_local_path(path, bkt_client=None):
    deprecated_warning(
        "transform_to_local_path is deprecated. Use url_to_local_path instead."
    )
    return url_to_local_path(path, allow_invalid_bucket_url=True)


@make_traceable
def url_to_local_path(
    path,
    bucket_client=None,
    *,
    allow_invalid_bucket_url: bool = True,
    check_visiable: bool = True,
):
    bucket_client = get_bucket_client()

    if bucket_client.valid_url(path):
        return bucket_client.url_to_local(path, check_visiable=check_visiable)
    elif allow_invalid_bucket_url:
        return path
    else:
        raise ValueError(f"Invalid dmp url: {path}")


@make_traceable
def local_path_to_url(
    path, bucket_client=None, *, allow_invalid: bool = False
):
    bucket_client = get_bucket_client()
    if not bucket_client.valid_url(path):
        try:
            path = bucket_client.local_to_url(path)
        except FileNotFoundError as e:
            if allow_invalid:
                return path
            else:
                raise e
    return path


@make_traceable
def is_valid_url(path, bucket_client=None):
    bucket_client = get_bucket_client()
    return bucket_client.valid_url(path)


@make_traceable
def is_dmp_path(path, dmp_client=None):
    if dmp_client is None:
        dmp_client = get_resource(DmpClient)
    return dmp_client.is_dmp_url(path)


@make_traceable
def check_dir_empty(dirname, allow_not_exist=True):
    """Check whether a directory is empty or not.

    Parameters
    ----------
    dirname : str
        Directory
    allow_not_exist : bool, optional
        Whether allow directory not exist or not, by default True
    """
    if not fs.exists(dirname):
        if not allow_not_exist:
            raise FileNotFoundError(f"{dirname} does not exists")
    else:
        ret = fs.listdir(dirname)
        assert len(ret) == 0, f"{dirname} is not empty! Has files {ret}"


@make_traceable
def to_unique_local_dir(url: str):
    """Convert dmp url to unique local path.

    Args:
        url (str): The dmp url

    Returns:
        local_path (str): A unique local path.
    """
    local_path = url_to_local_path(url)
    if running_in_cluster():
        suffix = env_job_id()
    else:
        suffix = uuid.uuid4().hex
    random_path = f"{local_path}_{suffix}"
    logger.info(f"Change local_path from {local_path} to {random_path}.")
    return random_path


@make_traceable
def to_unique_local_filepath(url: str):
    """Convert dmp url to unique file path.

    Args:
        url (str): The dmp url

    Returns:
        local_path (str): A unique file path.
    """
    local_path = url_to_local_path(url)
    filename = f"{uuid.uuid4().hex}_{basename(local_path)}"
    filepath = join(dirname(local_path), filename)
    logger.info(f"Change local_path from {local_path} to {filepath}.")
    return filepath


def upload2bucket(local: str, url: str, client: Optional[BucketClient] = None):
    local = url_to_local_path(local)
    url = local_path_to_url(url)
    if local == url_to_local_path(url):
        return url

    if osp.isdir(local):
        for filename in os.listdir(local):
            upload2bucket(
                osp.join(local, filename), osp.join(url, filename), client
            )
    else:
        makedirs(path=osp.dirname(url), exist_ok=True)
        client = client or BucketClient()
        if not client.exists(url=url):
            logger.info(f"Upload to Bucket: {local} >> {url}")
            client.upload(local, url)

    return url


@make_traceable
def is_sinked(url: str) -> bool:
    stat = os.stat(url_to_local_path(url))
    du = stat.st_blocks * stat.st_blksize
    if stat.st_size != 0 and du == 0:
        return True
    else:
        return False


def is_weburl(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")
