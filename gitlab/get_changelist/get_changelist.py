import os
import sys
import subprocess
import logging
import argparse
import numpy as np
from openpyxl import Workbook


def command_run(command):
    ret = subprocess.run(command, shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, encoding="utf-8")
    if ret.returncode == 0:
        return ret.stdout
    else:
        logging.error(
            'Command: {} . Run error! Please check script!'.format(command))
        return


def get_tag_commit(tag):
    command = 'git --no-pager log --pretty=format:%h -n 1 {}'.format(tag)
    commit_id = command_run(command)
    if commit_id:
        logging.info('tag: {}, commit_id: {}'.format(tag, commit_id))
        return commit_id
    else:
        logging.error(
            'Unable to get tag commit id, \
                Please check tag name,branch or build environment!!!'
        )
        return


def get_commit_list(source_tag_commit_id, target_tag_commit_id, branch):
    data = list()
    command = '''git log --pretty=format:"%h|%s|%ae|%ad" origin/{} | \
        sed -n '/^{}/,/^{}/p' | \
            sed '$d' > tempfile'''.format(
        branch, source_tag_commit_id, target_tag_commit_id)
    command_run(command)

    command1 = "cat tempfile | awk -F'|' '{{print $1}}'"
    commit = command_run(command1).split('\n')

    command2 = "cat tempfile | awk -F'|' '{{print $2}}'"
    subject = command_run(command2).split('\n')

    command3 = "cat tempfile | awk -F'|' '{{print $3}}'"
    author = command_run(command3).split('\n')

    command4 = "cat tempfile | awk -F'|' '{{print $4}}'"
    time_list = command_run(command4).split('\n')

    if len(commit) != len(subject) != len(author) != len(time_list):
        logging.error('Abnormal data!!!')
        return

    data.append(commit)
    data.append(subject)
    data.append(author)
    data.append(time_list)
    return data


def get_change_list(source_id, target_id, branch):
    logging.info('branch name: {}'.format(branch))
    command = 'git log  --pretty=format:"%h" origin/{}'.format(branch)
    ret_list = command_run(command)
    if ret_list:
        commit_list = ret_list.split()
        if source_id not in commit_list or target_id not in commit_list:
            logging.error(
                "Source tag and target tag are not in the same branch, \
                    Does not support obtaining release notes")
            return
        else:
            data = get_commit_list(source_id,
                                   target_id, branch)
            return data
    else:
        logging.error(
            'Unable to get {} branch info, \
                Please check the branch name and \
                    build environment!!!'.format(branch))
        return


def to_execl(data):
    filename = 'changelist.xlsx'
    wb = Workbook()
    ws = wb.active
    label = [['commit_id'],
             ['subject'],
             ['author'],
             ['time']
             ]

    label = np.array(label)
    feature = np.array(data)

    label_input = []
    for l in range(len(label)):
        label_input.append(label[l][0])
    ws.append(label_input)

    for f in range(len(feature[0])):
        ws.append(feature[:, f].tolist())

    wb.save(filename)
    logging.info('{} has been generated'.format(filename))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--branch', help='please input branch name')
    parser.add_argument('-t', '--target_tag',
                        help='please input target tag name')
    args = parser.parse_args()
    source_tag = os.getenv('TAG_NAME')
    source_tag_commit_id = get_tag_commit(source_tag)
    if not source_tag_commit_id:
        return -1
    target_tag = args.target_tag
    target_tag_commit_id = get_tag_commit(target_tag)
    if not target_tag_commit_id:
        return -1
    branch = args.branch
    data = get_change_list(source_tag_commit_id, target_tag_commit_id, branch)
    if not data:
        return -1
    to_execl(data)


if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s:%(asctime)s: %(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S', level=logging.DEBUG)
    sys.exit(main())

