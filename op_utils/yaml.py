import os
from typing import Any, Dict

import yaml
from yamlinclude import YamlIncludeConstructor


class GoToDir(object):
    def __init__(self, dirname: str):
        self._dirname = dirname
        self._old_cwd = None

    def __enter__(self):
        assert self._old_cwd is None
        self._old_cwd = os.getcwd()
        if len(self._dirname):
            os.chdir(self._dirname)

    def __exit__(self, ptype, value, trace):
        assert self._old_cwd is not None
        os.chdir(self._old_cwd)


class MyYamlIncludeConstructor(YamlIncludeConstructor):
    def _read_file(self, path, loader, encoding):
        dirname = os.path.dirname(path)
        basename = os.path.basename(path)
        with GoToDir(dirname):
            result = super()._read_file(basename, loader, encoding)
        return result


class IncludeLoader(yaml.SafeLoader):
    pass


MyYamlIncludeConstructor.add_to_loader_class(loader_class=IncludeLoader)


class MyYamlIncludeAndBaseConstructor(MyYamlIncludeConstructor):

    BASE_KEY = "_BASE_"

    @classmethod
    def _merge_a_into_b(cls, a: Dict[str, Any], b: Dict[str, Any]) -> None:
        # merge dict a into dict b. values in a will overwrite b.
        for k, v in a.items():
            if isinstance(v, dict) and k in b:
                assert isinstance(
                    b[k], dict
                ), "Cannot inherit key '{}' from base!".format(k)
                cls._merge_a_into_b(v, b[k])
            else:
                b[k] = v

    def _read_file(self, path, loader, encoding):
        result = super()._read_file(path, loader, encoding)
        if self.BASE_KEY in result:
            base_path = result.pop(self.BASE_KEY)
            base_path = os.path.join(os.path.dirname(path), base_path)
            base_result = load_yaml_with_include_and_base(base_path)
            self._merge_a_into_b(result, base_result)
            result = base_result
        return result


class IncludeAndBaseLoader(yaml.SafeLoader):
    pass


MyYamlIncludeAndBaseConstructor.add_to_loader_class(
    loader_class=IncludeAndBaseLoader
)


def load_yaml_with_include(path: str) -> Dict[str, Any]:
    dirname = os.path.dirname(path)
    basename = os.path.basename(path)
    with GoToDir(dirname):
        with open(basename) as fin:
            d = yaml.load(fin, Loader=IncludeLoader)
    return d


def load_yaml_with_include_and_base(path: str) -> Dict[str, Any]:
    """Just like `yaml.load(open(filename))`, but inherit attributes from its `_BASE_`.

    Args:
        path (str or file-like object): the file name or file of the
            current config. Will be used to find the base config file.

    Returns:
        (dict): the loaded yaml
    """  # noqa
    dirname = os.path.dirname(path)
    basename = os.path.basename(path)
    with GoToDir(dirname):
        with open(basename) as fin:
            d = yaml.load(fin, Loader=IncludeAndBaseLoader)
    return d
