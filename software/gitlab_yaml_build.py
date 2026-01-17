# -*- coding: utf-8 -*-

import os
from git import Repo
import yaml
import shutil

if os.path.isdir('./tmp/'):
    shutil.rmtree('./tmp/')
clone_repo = Repo.clone_from(
    url='git@gitlab.test.com:code_check_config.git',
    to_path='./tmp/')


def read_attr(attr: dict):
    for k, v in attr.items():
        if isinstance(v, dict):

            return read_attr(v)


file_list = os.listdir('./tmp/repo_yaml')
for file in file_list:
    with open(f'./tmp/repo_yaml/{file}', 'r') as f:
        resp = yaml.safe_load(f)
        res = read_attr(resp)

shutil.rmtree('./tmp/')
