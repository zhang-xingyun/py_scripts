import requests
from gitlab_app import models
from django.db.models import Q
import re
import json
import logging

logging.basicConfig(
    format='%(levelname)s:%(asctime)s : %(lineno)d :%(message)s',
    datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)


class SyncModule(object):

    def __init__(self):
        host = 'https://repo-relation.test.com'
        self.login_url = host + '/api/api/login/'
        self.repo_url = host + '/api/api/scm/module/'
        self.authorization = "JWT " + self.get_authorization()
        self.type = {
            0: "仓库组",
            1: "仓库",
            2: "仓库+分支",
            3: "仓库+路径",
            4: "仓库+分支+路径",
        }

    def get_authorization(self):
        data = {
            "username": "",
            "password": "",
            "captcha": "",
            "captchaKey": None
        }
        response = requests.post(self.login_url, data=data)
        return response.json()['data']['access']

    def get_module_list(self):
        num = 50
        page = 1
        headers = {
            'Authorization': self.authorization
        }
        module_repo = dict()
        while True:
            params = {
                'limit': num,
                'page': page
            }
            print(params)
            response = requests.get(self.repo_url,
                                    params=params,
                                    headers=headers)
            response = response.json()
            for data in response['data']['data']:
                repo_group = list()
                group_link = list()
                repo = list()
                repo_link = list()
                branch = None
                path = None
                module = list()
                type = data['type']
                if type == 0:
                    if data['repo_group_info']:
                        for d in data['repo_group_info']:
                            repo_group.append(str(d['group_id']))
                            group_link.append(d['web_url'])
                elif type == 1:
                    if data['repo_info']:
                        for d in data['repo_info']:
                            repo.append(str(d['repo_id']))
                            repo_link.append(d['web_url'])
                elif type == 2:
                    if data['repo_info']:
                        for d in data['repo_info']:
                            repo.append(str(d['repo_id']))
                            repo_link.append(d['web_url'])
                        if data['branch']:
                            branch = data['branch']
                elif type == 3:
                    if data['repo_info']:
                        for d in data['repo_info']:
                            repo.append(str(d['repo_id']))
                            repo_link.append(d['web_url'])
                        if data['path']:
                            path = data['path']
                elif type == 4:
                    if data['repo_info']:
                        for d in data['repo_info']:
                            repo.append(str(d['repo_id']))
                            repo_link.append(d['web_url'])
                        if data['branch']:
                            branch = data['branch']
                        if data['path']:
                            path = data['path']
                else:
                    pass
                if data['module_ins_info']:
                    for d in data['module_ins_info']:
                        module_tmp = dict()
                        module_tmp['name'] = d['name']
                        module.append(module_tmp)
                if type == 0:
                    pass
                else:
                    for rep in repo:
                        if int(rep) not in module_repo.keys():
                            module_repo[int(rep)] = list()
                        tmp = dict()
                        tmp['module'] = module[0]['name']
                        tmp['type'] = type
                        tmp['repo'] = rep
                        tmp['branch'] = branch
                        tmp['path'] = path
                        module_repo[int(rep)].append(tmp)

            if len(response['data']['data']) < num:
                break
            page += 1
        return module_repo

    def sync_commit(self):
        module_repo = self.get_module_list()
        module_repo_list = list(module_repo.keys())
        logging.info("Module repo num:" + str(len(module_repo_list)))
        no_module_commit = models.Commit.objects.filter(
            ~Q(repo__repo_id__in=module_repo_list) and ~Q(module_list='[]'))
        for commit in no_module_commit:
            commit.module_list = '[]'
            commit.save()
        for repo in module_repo_list:
            logging.info("start to handle repo:" + str(repo))
            module_commits = models.Commit.objects.filter(
                repo__repo_id=repo)
            for module_commit in module_commits:
                file_list = json.loads(module_commit.file_list)
                for file in file_list:
                    file['module_list'] = set()
                module_set = set()
                for relation in module_repo[repo]:
                    if relation['type'] == 1:
                        module_set.add(relation['module'])
                        for file in file_list:
                            file['module_list'].add(relation['module'])
                    elif relation['type'] == 2:
                        branches = [branch.branch_name for branch in
                                    module_commit.branches.all()]
                        if relation['branch'] in branches:
                            module_set.add(relation['module'])
                            for file in file_list:
                                file['module_list'].add(relation['module'])
                    elif relation['type'] == 3:
                        path_rule = relation['path']
                        if not path_rule.startswith("^"):
                            path_rule = "^" + path_rule
                        for file in file_list:
                            pattern = re.compile(path_rule)
                            if pattern.search(file['file']):
                                module_set.add(relation['module'])
                                file['module_list'].add(relation['module'])
                    elif relation['type'] == 4:
                        branches = [branch.branch_name for branch in
                                    module_commit.branches.all()]
                        if relation['branch'] not in branches:
                            break
                        path_rule = relation['path']
                        if not path_rule.startswith("^"):
                            path_rule = "^" + path_rule
                        for file in file_list:
                            pattern = re.compile(path_rule)
                            if pattern.search(file['file']):
                                module_set.add(relation['module'])
                                file['module_list'].add(relation['module'])
                    else:
                        pass
                module_commit.module_list = json.dumps(list(module_set),
                                                       ensure_ascii=False)
                for file in file_list:
                    file['module_list'] = list(file['module_list'])
                module_commit.file_list = json.dumps(file_list,
                                                     ensure_ascii=False)
                module_commit.save()

    def sync_bug_introduce(self):
        module_repo = self.get_module_list()
        module_repo_list = list(module_repo.keys())
        logging.info("Module repo num:" + str(len(module_repo_list)))
        no_module_commit = models.CodeReviewBugIntroduce.objects.filter(
            ~Q(repo_id__in=module_repo_list) and ~Q(module_list='[]'))
        for commit in no_module_commit:
            commit.module_list = '[]'
            commit.save()
        for repo in module_repo_list:
            logging.info("start to handle repo:" + str(repo))
            module_commits = models.Commit.objects.filter(
                repo__repo_id=repo)
            bug_introduce_commits = \
                models.CodeReviewBugIntroduce.objects.filter(
                    repo_id=repo)
            for bug_introduce_commit in bug_introduce_commits:
                bug_introduce_file = bug_introduce_commit.file_path
                commit = bug_introduce_commit.commit
                for module_commit in module_commits:
                    if module_commit.commit_hash == commit:
                        file_list = json.loads(module_commit.file_list)
                        for file in file_list:
                            if file['file'] == bug_introduce_file:
                                bug_introduce_commit.module_list = \
                                    file['module_list']
                                bug_introduce_commit.save()
                                break
                        break


def run():
    er = SyncModule()
    # er.get_module_list()
    er.sync_commit()
    er.sync_bug_introduce()
