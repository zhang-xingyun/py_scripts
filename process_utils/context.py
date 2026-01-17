import logging
import os
import sys
from typing import Dict, List, Optional, Union

from hatbc.filestream.utils import url_to_local_path
from hatbc.utils import _as_list

logger = logging.getLogger(__name__)


__all__ = ["ModuleContainer", "EnvironContainer"]


class ModuleContainer:
    """Clean module added by import_module.

    Parameters
    ----------
    ignore_module_names : Optional[Union[str, List[str]]], optional
        ModuleName will not be cleaned, by default None
    """

    def __init__(
        self,
        ignore_module_names: Optional[Union[str, List[str]]] = None,
    ):
        if ignore_module_names is not None:
            self.ignore_module_names = set(_as_list(ignore_module_names))
        else:
            self.ignore_module_names = set()
        self.old_module_names = set()
        self.new_module_names = set()

    def __enter__(self):
        self.old_module_names = set(sys.modules.keys())

    def __exit__(self, exc_type, exc_val, exc_tb):
        for module_name in list(sys.modules.keys()):
            if (
                module_name not in self.ignore_module_names
                and module_name not in self.old_module_names
            ):
                sys.modules.pop(module_name)


class EnvironContainer:
    def __init__(self, update_environ: Optional[Dict]):
        self.update_envrion = update_environ
        self.old_envrion = dict()

    def __enter__(self):
        if self.update_envrion is None:
            return self

        # save old environ
        for k in self.update_envrion.keys():
            old_v = os.environ.get(k, None)
            if old_v is not None:
                self.old_envrion[k] = old_v

        # update environ
        os.environ.update(self.update_envrion)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.update_envrion is None:
            return True

        # delete environ new added
        for k in self.update_envrion.keys():
            del os.environ[k]

        # recover old envrion
        os.environ.update(self.old_envrion)


class WorkingRootContext:
    def __init__(self, target_root: str):
        self.origin_root = None
        self.target_root = os.path.abspath(url_to_local_path(target_root))
        assert os.path.exists(self.target_root), self.target_root

    def __enter__(self):
        self.origin_root = os.path.abspath(os.getcwd())
        os.chdir(self.target_root)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self.origin_root)
