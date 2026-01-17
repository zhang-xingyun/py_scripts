import logging

from hatbc.filestream.utils import url_to_local_path as url_to_local_path_fn
from hatbc.workflow.trace import make_traceable

logger = logging.getLogger(__name__)

__all__ = ["url_to_local_path"]


@make_traceable
def url_to_local_path(*args, **kwargs):
    return url_to_local_path_fn(*args, **kwargs)
