import re

from gitlab_app.PhPolicy import PhInfo


def handle_repo_list(_repo_list):
    data = list()
    for remote_url in _repo_list:
        git_dir = re.search(r'gitlab\.test\.com[:/](.*?)(\.git|)$',
                            remote_url)
        if git_dir:
            git_dir = git_dir.group(1)
            data.append(git_dir)
        else:
            data.append(remote_url)

    return data


def run(*args):
    action = 'update'
    if args:
        action = args[0]
    ph = PhInfo(action)
    ph.find_repo_with_ssh_url()
