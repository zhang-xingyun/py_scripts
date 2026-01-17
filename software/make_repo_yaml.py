# coding:utf-8
import os
import hashlib
import subprocess
import time
from git import Repo as rp
import shutil

import yaml
from gitlab_app.models import ProjectModule, CodeReviewFilePathRule, Repo, \
    Group

jira_check = '(^[a-zA-Z][a-zA-Z0-9_]+-[1-9][0-9]*)'

commit_message_map = {
    'ss_commit_message': '^(.+: )+(feat|fix|bugfix|hotfix|docs|style|refactor|'
                         'perf|test|chore) \\[.*\\] .+',
    'normal_commit_message': '^(feat|fix|bugfix|hotfix|docs|style|refactor'
                             '|perf|test|chore)\\(.*\\): \\[.*\\] [A-Z]+.*'
}

ss_repo_id = ['2167', '4631', '5892', '8196', '7897', '8344']
all_branches_message_check_repo_id = ['7976']


def get_check_msg_branch(repo_id):
    check_msg_branch = ['^master$', '^develop$', '^main$', '^release-.+',
                        '^sprint-.+', '^dev-.+', '^rel-.+']
    if str(repo_id) in all_branches_message_check_repo_id:
        check_msg_branch = ['^master$', '^develop$', '^main$', '^release-.+',
                            '^sprint-.+', '^feature-.+', '^feat-.+',
                            '^bugfix-.+', '^hotfix-.+', '^cicd-.+', '^test-.+',
                            '^tool-.+', '^dev-.+', '^rel-.+']
    return check_msg_branch


def write_repo_yaml():
    dir_path = "/data/wwwroot/storage/code_check_config/"
    # dir_path = r"C:\Users\robot\Documents\code\gitlab_data\\" + \
    #            "storage\code_check_config"
    os.chdir(dir_path)
    do_cmd('git pull')
    rule_list = CodeReviewFilePathRule.objects.all()
    repo_set = set()
    for rule in rule_list:
        rule_attr = rule.repo.values()
        for repo in rule_attr:
            repo_set.add(repo['id'])
    repo_id_list = list(repo_set)
    repo_list = Repo.objects.filter(id__in=repo_id_list).all()
    # model_info = get_model_hash()
    try:
        shutil.rmtree('repo_yaml')
    except FileNotFoundError:
        pass
    path_index = 1
    os.makedirs('repo_yaml')
    for repo in repo_list:
        prop_id = repo.repo_id
        lint_status_check_branch = list()
        jira_id_skip_check_branch = list()
        jira_type_check_branch = list()
        not_allowed_rat_check_branch = list()
        not_allowed_jira_closed_check_branch = list()
        commit_body_format_check_branch = list()
        setting = {
            'lint_status_check': False,
            'jira_id_skip_check': False,
            'jira_type_check': False,
            'not_allowed_rat_check': False,
            'not_allowed_jira_closed_check': False,
            'commit_body_format_check': False,
        }
        rule_list = CodeReviewFilePathRule.objects.filter(repo=repo)
        if len(rule_list) == 0:
            continue
        check_msg_branch = get_check_msg_branch(prop_id)
        if str(prop_id) in ss_repo_id:
            commit_message_type = commit_message_map['ss_commit_message']
        else:
            commit_message_type = commit_message_map['normal_commit_message']
        repo_rule_item = {
            'rule': {
                'code_commit': {
                    'review_by_file_path': [],
                    'force_cr_people_check': [],
                },
                'web_code_commit': {},
                'merge_request': {
                    'merge_request_cr_people_check': [],
                    'merge_by_file_path': [],
                }
            },
            'setting': {
                'normal_commit_message': commit_message_type
            }

        }
        if prop_id in [7620, 7572, 7573, 7624]:
            main_list = []
            repo_rule_item['rule']['merge_request'][
                'merge_request_cr_people_check'].append({
                'global_rule_' + md5_str: [
                    {
                        'allow': {
                            'branch_name': 'master',
                            'maintainers': main_list,
                            'maintainers_num': 1,
                            'approvers': None,
                            'approvers_num': 0,
                            'action': 'allow'
                        }
                    },
                    {
                        'block': {
                            'branch_name': 'master',
                            'action': 'block'
                        },
                    }
                ]})

        for rule in rule_list:
            check_msg_branch.extend(rule.branch.split(','))
            if rule.lint_block_check:
                setting['lint_status_check'] = True
                lint_status_check_branch.extend(rule.branch.split(','))
            if rule.cr_id_skip_check:
                setting['jira_id_skip_check'] = True
                jira_id_skip_check_branch.extend(rule.branch.split(','))
            if rule.jira_type_check:
                setting['jira_type_check'] = True
                jira_type_check_branch.extend(rule.branch.split(','))
            if rule.not_allowed_rat_check:
                setting['not_allowed_rat_check'] = True
                not_allowed_rat_check_branch.extend(rule.branch.split(','))
            if rule.not_allowed_jira_closed_check:
                setting['not_allowed_jira_closed_check'] = True
                not_allowed_jira_closed_check_branch.extend(rule.branch.split(','))
            if rule.commit_body_format_check:
                setting['commit_body_format_check'] = True
                commit_body_format_check_branch.extend(rule.branch.split(','))
                commit_body_format_check_branch = sorted(
                    set(commit_body_format_check_branch))
            file_path = rule.file_path.replace(' ', '')
            # if not file_path:
            #     file_path = '.*'
            branch = rule.branch.replace(' ', '').replace('，', '') \
                if rule.branch else ''
            branch = branch.split(',')
            branch = sorted(set(branch))

            committer = None
            committer_num = 0
            if rule.maintainer:
                committer = (rule.maintainer.replace(' ', '').replace('，', '')
                             if rule.maintainer else '').split(',')
                committer_num = rule.maintainer_num if rule.maintainer_num \
                    else 0

            maintainer = None
            maintainer_num = 0
            if rule.commiter:
                maintainer = (rule.commiter.replace(' ', '').replace('，', '')
                              if rule.commiter else '').split(',')
                maintainer_num = rule.commiter_num if rule.commiter_num else 0

            supervisor = None
            supervisor_num = 0
            if rule.supervisor:
                supervisor = (rule.supervisor.replace(' ', '').replace('，', '')
                              if rule.supervisor else '').split(',')
                supervisor_num = rule.supervisor_num if rule.supervisor_num else 0

            ph_reviewer = None
            ph_reviewer_num = 0
            if rule.ph_reviewer:
                ph_reviewer = (rule.ph_reviewer.replace(' ', '').replace('，', '')
                              if rule.ph_reviewer else '').split(',')
                ph_reviewer_num = rule.ph_reviewer_num if rule.ph_reviewer_num else 0

            superuser = None
            superuser_num = 0
            if rule.superuser:
                superuser = (rule.superuser.replace(' ', '').replace('，', '')
                              if rule.superuser else '').split(',')
                superuser_num = rule.superuser_num if rule.superuser_num else 0

            for path in file_path.split(','):
                path_index += 1
                if not path:
                    continue
                if path != '.*':
                    allow = {
                        'branch_name': branch,
                        'maintainers': maintainer,
                        'maintainers_num': maintainer_num,
                        'approvers': committer,
                        'approvers_num': committer_num,
                        'superusers': superuser,
                        'superusers_num': superuser_num,
                        'supervisors': supervisor,
                        'supervisors_num': supervisor_num,
                        'ph_reviewers':  ph_reviewer,
                        'ph_reviewers_num': ph_reviewer_num,
                        'action': 'allow'
                    }
                    if rule.approvers_change_files_count:
                        allow['approvers_change_files_count'] = \
                            rule.approvers_change_files_count
                    if rule.approvers_change_rows:
                        allow['approvers_change_rows'] = \
                            rule.approvers_change_rows
                    # if rule.supervisors_change_files_count:
                    #     allow['supervisors_change_files_count'] = \
                    #         rule.supervisors_change_files_count
                    # if rule.supervisors_change_rows:
                    #     allow['supervisors_change_rows'] = \
                    #         rule.supervisors_change_rows
                    repo_rule_item['rule']['code_commit'][
                        'review_by_file_path'].append({path: [{
                            'allow': allow}, {
                            'block': {
                                'branch_name': branch,
                                'action': 'block',
                                'check_path': path.split(','),
                            }}]
                        })
                    repo_rule_item['rule']['merge_request'][
                        'merge_by_file_path'].append({path: [{
                            'allow': allow}, {
                            'block': {
                                'branch_name': branch,
                                'action': 'block',
                                'check_path': path.split(','),
                            }}]
                        })
                else:
                    if maintainer is None and committer is None and supervisor is None and ph_reviewer is None and superuser is None:
                        branch.extend(check_msg_branch)
                        branch = sorted(set(branch))
                        repo_rule_item['rule']['code_commit'][
                            'force_cr_rule_check'] = [
                            {
                                'global_rule': [
                                    {
                                        'allow': {
                                            'branch_name': branch,
                                            'force_cr': True,
                                            'force_cr_num': rule.commiter_num
                                            if rule.commiter_num else 0,
                                            'action': 'allow',
                                        }
                                    },
                                    {
                                        'block': {
                                            'branch_name': branch,
                                            'action': 'block'
                                        }
                                    }
                                ]
                            }
                        ]
                        repo_rule_item['setting'][
                            'force_cr_num'] = rule.commiter_num if rule.commiter_num else 0
                        repo_rule_item['setting']['force_mr_cr_num'] = rule.maintainer_num if rule.maintainer_num else repo_rule_item['setting']['force_cr_num']
                    else:
                        m = hashlib.md5()
                        m.update(str(path_index).encode())
                        md5_str = m.hexdigest()
                        allow = {
                            'branch_name': branch,
                            'maintainers': maintainer,
                            'maintainers_num': maintainer_num,
                            'approvers': committer,
                            'approvers_num': committer_num,
                            'superusers': superuser,
                            'superusers_num': superuser_num,
                            'supervisors': supervisor,
                            'supervisors_num': supervisor_num,
                            'ph_reviewers':  ph_reviewer,
                            'ph_reviewers_num': ph_reviewer_num,
                            'action': 'allow'
                        }
                        if rule.approvers_change_files_count:
                            allow['approvers_change_files_count'] = \
                                rule.approvers_change_files_count
                        if rule.approvers_change_rows:
                            allow['approvers_change_rows'] = \
                                rule.approvers_change_rows
                        # if rule.supervisors_change_files_count:
                        #     allow['supervisors_change_files_count'] = \
                        #         rule.supervisors_change_files_count
                        # if rule.supervisors_change_rows:
                        #     allow['supervisors_change_rows'] = \
                        #         rule.supervisors_change_rows
                        repo_rule_item['rule']['code_commit'][
                            'force_cr_people_check'].append({
                                'global_rule_' + md5_str: [
                                    {
                                        'allow': allow
                                    },
                                    {
                                        'block': {
                                            'branch_name': branch,
                                            'action': 'block'
                                        }
                                    }
                                ]
                            })
                        repo_rule_item['rule']['merge_request'][
                            'merge_request_cr_people_check'].append({
                                'global_rule_' + md5_str: [
                                    {
                                        'allow': allow
                                    },
                                    {
                                        'block': {
                                            'branch_name': branch,
                                            'action': 'block'
                                        },
                                    }
                                ]})
        if setting['lint_status_check']:
            repo_rule_item['rule']['code_commit']['lint_status_check'] = [
                {
                    'global_rule': [
                        {
                            'allow_branch_name_rule': {
                                'branch_name': lint_status_check_branch,
                                'lint_block': True,
                                'action': 'allow'
                            }
                        },
                        {
                            'block_branch_name_rule': {
                                'branch_name': lint_status_check_branch,
                                'action': 'block',
                                'lint_block': True,
                            }
                        }
                    ]
                }
            ]
        if setting['jira_id_skip_check']:
            check_cr_id_skip_item = [{
                'global_rule': [
                    {
                        'allow': {
                            'branch_name': jira_id_skip_check_branch,
                            'cr_id_skip': setting['jira_id_skip_check'],
                            'jira_id_rule': jira_check,
                            'action': 'allow',
                        }
                    }, {
                        'block': {
                            'branch_name': jira_id_skip_check_branch,
                            'jira_id_rule': 'cr_id_skip',
                            'action': 'block',
                        }
                    }
                ]
            }]
            repo_rule_item['rule']['code_commit'][
                'jira_id_skip_check'] = check_cr_id_skip_item
            repo_rule_item['rule']['merge_request'][
                'jira_id_skip_check'] = check_cr_id_skip_item
            repo_rule_item['rule']['web_code_commit'][
                'jira_id_skip_check'] = check_cr_id_skip_item
        if setting['jira_type_check']:
            jira_type_check_item = [{
                'global_rule': [
                    {
                        'allow': {
                            'branch_name': jira_type_check_branch,
                            'jira_type': setting['jira_type_check'],
                            'cr_id_skip': False,
                            'action': 'allow',
                        }
                    }, {
                        'block': {
                            'branch_name': jira_type_check_branch,
                            'cr_id_skip': False,
                            'action': 'block',
                        }
                    }
                ]
            }]
            repo_rule_item['rule']['code_commit'][
                'jira_type_check'] = jira_type_check_item
            repo_rule_item['rule']['merge_request'][
                'jira_type_check'] = jira_type_check_item
            repo_rule_item['rule']['web_code_commit'][
                'jira_type_check'] = jira_type_check_item
        if setting['not_allowed_rat_check']:
            not_allowed_rat_check_item = [{
                'global_rule': [
                    {
                        'allow': {
                            'branch_name': not_allowed_rat_check_branch,
                            'jira_id_rule': 'global_conf[\'setting\'][\'jira_check\']',
                            'cr_id_skip': True,
                            'action': 'allow',
                        }
                    }, {
                        'block': {
                            'branch_name': not_allowed_rat_check_branch,
                            'action': 'block',
                        }
                    }
                ]
            }]
            repo_rule_item['rule']['code_commit'][
                'not_allowed_rat_check'] = not_allowed_rat_check_item
            repo_rule_item['rule']['merge_request'][
                'not_allowed_rat_check'] = not_allowed_rat_check_item
            repo_rule_item['rule']['web_code_commit'][
                'not_allowed_rat_check'] = not_allowed_rat_check_item

        if setting['not_allowed_jira_closed_check']:
            not_allowed_jira_closed_check_item = [{
                'global_rule': [
                    {
                        'allow': {
                            'branch_name': not_allowed_jira_closed_check_branch,
                            'cr_id_skip': True,
                            'action': 'allow',
                        }
                    }, {
                        'block': {
                            'branch_name': not_allowed_jira_closed_check_branch,
                            'action': 'block',
                        }
                    }
                ]
            }]
            repo_rule_item['rule']['code_commit'][
                'not_allowed_jira_closed_check'] = not_allowed_jira_closed_check_item
            repo_rule_item['rule']['merge_request'][
                'not_allowed_jira_closed_check'] = not_allowed_jira_closed_check_item
            # repo_rule_item['rule']['web_code_commit'][
            #     'not_allowed_jira_closed_check'] = not_allowed_jira_closed_check_item

        if setting['commit_body_format_check']:
            commit_body_format_check_item = [{
                'global_rule': [
                    {
                        'allow': {
                            'branch_name': 'global_conf[\'setting\'][\'check_msg_branch\']',
                            'commit_message_rule': 'global_conf[\'setting\'][\'normal_commit_message\']',
                            'commit_body_format_check_branch_rule': commit_body_format_check_branch,
                            'action': 'allow',
                        }
                    }, {
                        'block': {
                            'branch_name': 'global_conf[\'setting\'][\'check_msg_branch\']',
                            'action': 'block',
                        }
                    }
                ]
            }]
            repo_rule_item['rule']['code_commit'][
                'commit_message_rule_check'] = commit_body_format_check_item
            # repo_rule_item['rule']['merge_request'][
            #     'commit_message_rule_check'] = commit_body_format_check_item
            # repo_rule_item['rule']['web_code_commit'][
            #     'commit_message_rule_check'] = commit_body_format_check_item
        check_msg_branch = sorted(set(check_msg_branch))
        check_msg_branch = [x.strip() for x in check_msg_branch if x.strip()]
        repo_rule_item['setting']['check_msg_branch'] = check_msg_branch
        file = open(f"repo_yaml/{prop_id}.yaml", 'w', encoding='utf-8')
        yaml.dump(repo_rule_item, file)
        file.close()

    git_push()


def get_model_hash():
    model_item = dict()
    model_list = ProjectModule.objects.all()
    for model in model_list:
        model_id = model.id
        model_maintainer = model.maintainer
        model_item[model_id] = model_maintainer
    return model_item


def get_maintainer(model_item, model_attr):
    maintainer_list = list()
    for attr in model_attr:
        maintainer_list.extend(
            model_item.get(attr['id'], '').replace('，', ',').split(','))
    return list(set(maintainer_list))


def git_push():
    git = rp(r'/data/wwwroot/storage/code_check_config')
    if git.untracked_files or git.index.diff(None):
        do_cmd('git add --all')
        do_cmd('git commit -m "feat(yaml): [TMGSW-62] Create Yaml"')
        do_cmd('git push -u origin master')
    else:
        print("No file changed!")


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
    write_repo_yaml()
