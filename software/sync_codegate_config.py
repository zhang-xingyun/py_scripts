# coding:utf-8
import os
import subprocess
import time


def pull_gate_config():
    gitlab_config_dir_path = "/var/opt/gitlab/data/custom_hooks/config/"
    code_check_config_dir_path = \
        "/var/opt/gitlab/data/custom_hooks/code_check_config/"
    os.chdir(gitlab_config_dir_path)
    do_cmd('git pull')
    time.sleep(1)
    os.chdir(code_check_config_dir_path)
    do_cmd('git pull')


def do_cmd(cmd):
    p = subprocess.Popen(cmd,
                         shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    try:
        while True:
            buff = p.stdout.readlines()
            if len(buff) == 0 and not p.poll():
                break
            time.sleep(1)
    except Exception:
        print('end')


def run():
    pull_gate_config()
