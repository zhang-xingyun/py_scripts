# -*- coding: utf-8 -*-
import datetime
import re
import os
import subprocess
import sys
import time
import threading
import shutil
import json

import pickle
from configparser import ConfigParser

import gitlab
from jira import JIRA
from gitlab_app import models


class ProjectPkl(object):

    def __init__(self):
        self.projects_attributes = dict()
        self.projects_jira_attributes = dict()
        path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gitlab_cfg = os.path.join(path, 'python-gitlab.cfg')
        self.gl = gitlab.Gitlab.from_config('trigger', [gitlab_cfg])
        self.gl.auth()
        self.get_single_project_thread = 1
        self.cr_report_pw = ''
        self.if_get_commits = True
        self.personal_projects_attributes = dict()
        self.public_projects_attributes = dict()
        self.groups_attributes = dict()
        self.exclude_repo = [7690, 6113, 1359, 6936, 5827, 4863, 1625,
                             1764, 2931, 3195, 4623, 4868, 5733, 7167,
                             7371, 7601, 7604]
        self.raw_data_path = '/opt/gitlab_report/raw_data2/'
        self.raw_data_repo_path = '/opt/gitlab_report/raw_data2/repo/'
        self.raw_data_group_path = '/opt/gitlab_report/raw_data2/group/'
        self.jira_issue_path = '/opt/gitlab_report/jira_data2/issue/'
        self.get_single_project_thread = 4
        self.git_cmd_thread = 120
        self.ph_reg = r"Differential Revision: https://cr.test.com/D(\d+)"
        self.jira_reg = r"([A-Z][A-Z0-9_]+-[1-9][0-9]*)"
        self.branch_rule = '^master$|^develop$|^main$|^release-.+|^sprint-.+' \
                           '|^feature-.+|^bugfix-.+|^hotfix-.+|^cicd-.+|' \
                           '^test-.+|^tool-.+|^dev-.+|^rel-.+|^feat-.+'
        self.jira_conn = None
        self._init_jira()
        self.issue_folder = 'issue'
        self.save_path = self._init_folder()
        self.select_commit_time_map = {
            '8710': '2021/01/01',
            '8344': '2022/01/01',
            '8196': '2021/06/01',
            '8677': '2022/01/01',
            '8292': '2022/01/01',
        }

    def _init_jira(self):
        try:
            cp = ConfigParser()
            cp.read('python-gitlab.cfg')
            auth_key = cp.get('jira', 'auth_key')
            token = cp.get('jira', 'token')
            url = cp.get('jira', 'url')
            self.jira_conn = JIRA(url, auth=(auth_key, token))
        except Exception:
            pass

    def _init_folder(self):

        if not os.path.exists(self.raw_data_path):
            os.makedirs(self.raw_data_path)
        if not os.path.exists(self.raw_data_repo_path):
            os.makedirs(self.raw_data_repo_path)
        if not os.path.exists(self.jira_issue_path):
            os.makedirs(self.jira_issue_path)
        return {
            'raw_data_path': self.raw_data_path,
            'raw_data_repo_path': self.raw_data_repo_path,
            'jira_issue_path': self.jira_issue_path,
            'raw_data_group_path': self.raw_data_group_path,
        }

    @staticmethod
    def save_pkl(file_name, data):
        f_obj = open(file_name, 'wb')
        pickle.dump(data, f_obj)
        f_obj.close()

    def get_jira_projects(self):
        if self.jira_conn:
            project_list = self.jira_conn.projects()
            for project in project_list:
                self.projects_jira_attributes[project.key] = project.raw
            raw_data_path = self.save_path['raw_data_path']
            self.save_pkl(raw_data_path + 'jira_project.pkl',
                          self.projects_jira_attributes)

    def get_jira_issues(self):
        jira_issue_path = self.save_path['jira_issue_path']
        for project_key in self.projects_jira_attributes.keys():

            issue_raw = dict()
            sql = 'project=' + str(project_key) + ' AND Created >= "2015-1-1"'
            issues_in_proj = self.jira_conn.search_issues(
                sql, maxResults=-1)

            for issue in issues_in_proj:
                issue_raw[issue.key] = issue.raw
            issue_path = jira_issue_path + '%s.pkl' % project_key
            self.save_pkl(issue_path, issue_raw)
        self.projects_jira_attributes = dict()

    def get_projects(self):
        try:
            projects = self.gl.projects.list(all=True,
                                             retry_transient_errors=True)
            for project in projects:
                self.projects_attributes[
                    project.attributes['id']] = project.attributes
            raw_data_path = self.save_path['raw_data_path']
            project_file = raw_data_path + 'projects_attributes.pkl'
            self.save_pkl(project_file, self.projects_attributes)
            self.projects_attributes = dict()
        except:
            print("gitHttpError get_projects")

    def get_groups(self):
        try:
            groups = self.gl.groups.list(all=True, retry_transient_errors=True)
            for group in groups:
                self.groups_attributes[
                    group.attributes['id']] = group.attributes
            raw_data_path = self.save_path['raw_data_path']
            group_file = raw_data_path + 'groups_attributes.pkl'
            self.save_pkl(group_file, self.groups_attributes)
        except:
            print("gitHttpError get_groups")

    def get_personal_public_projects(self):
        raw_data_path = self.save_path['raw_data_path']

        projects = self.read_pkl(
            raw_data_path + 'projects_attributes.pkl')
        for project_id, project_data in projects.items():
            if project_data['namespace']['kind'] == 'user':
                self.personal_projects_attributes[project_id] = project_data
            else:
                self.public_projects_attributes[project_id] = project_data
        public_project_file = \
            raw_data_path + 'public_projects_attributes.pkl'
        personal_project_file = \
            raw_data_path + 'personal_projects_attributes.pkl'
        self.save_pkl(public_project_file, self.public_projects_attributes)
        self.save_pkl(personal_project_file, self.personal_projects_attributes)

    @staticmethod
    def read_pkl(file_name):
        try:
            f_obj = open(file_name, 'rb')
            return pickle.load(f_obj)
        except Exception:
            print(file_name, 'not read')
            return {}

    def get_events(self, project_url, project_id, repo_folder):
        try:
            project = self.gl.projects.get(
                project_id, retry_transient_errors=True)
        except Exception as e:
            print('error event project exception', project_url, e)
            return
        try:
            events = project.events.list(all=True, retry_transient_errors=True)
        except Exception as e:
            print('error event event exception', project_url, e)
            return
        events_attributes = list()
        for event in events:
            events_attributes.append(event.attributes)
        self.save_pkl(repo_folder + 'events_attributes.pkl', events_attributes)

    def get_branch_and_tag(self, project_url, project_id, repo_folder):
        try:
            project = self.gl.projects.get(
                project_id, retry_transient_errors=True)
        except Exception as e:
            print('error branch project exception', project_url, e)
            return
        # get branches
        try:
            branches = project.branches.list(
                all=True, retry_transient_errors=True)
        except Exception as e:
            print('error branch branch exception', project_url, e)
            return
        # get tags
        # try:
        #     tags = project.tags.list(all=True, retry_transient_errors=True)
        # except Exception as e:
        #     print('error tag exception', project_url, e)
        #     return
        branches_attributes = dict()
        for branch in branches:
            if re.search(self.branch_rule, branch.attributes['name']):
                branches_attributes[branch.name] = branch.attributes
        # for tag in tags:
        #     self.update_tag_list_in_sql(project_id, tag.attributes)
        self.save_pkl(repo_folder + 'branches_attributes.pkl',
                      branches_attributes)

    def get_mrs(self, project_url, project_id, repo_folder):
        try:
            project = self.gl.projects.get(
                project_id, retry_transient_errors=True)
        except Exception as e:
            print('error mr project exception', project_url, e)
            return
        try:
            mrs = project.mergerequests.list(
                all=True, retry_transient_errors=True)
        except Exception as e:
            print('error mr mr exception', project_url, e)
            return
        mrs_attributes = list()
        for mr in mrs:
            tmp_mr = dict()
            tmp_mr['data'] = mr.attributes
            tmp_mr['discussion'] = list()
            tmp_mr['pipeline'] = list()
            tmp_mr['participant'] = list()
            tmp_mr['awardemojis'] = list()
            try:
                mr_discussion = mr.discussions.list(
                    all=True, retry_transient_errors=True)
                for discussion in mr_discussion:
                    if 'notes' not in discussion.attributes.keys():
                        continue
                    tmp_mr['discussion'].extend(discussion.attributes['notes'])
            except Exception as e:
                print('error mr discussion exception', project_url, e)
            try:
                mr_participants = mr.participants(
                    all=True, retry_transient_errors=True)
                for participant in mr_participants:
                    tmp_mr['participant'].append(participant)
            except Exception as e:
                print('error mr participant exception', project_url, e)
            try:
                mr_pipelines = mr.pipelines(
                    all=True, retry_transient_errors=True)
                for pipeline in mr_pipelines:
                    tmp_mr['pipeline'].append(pipeline)
            except Exception as e:
                print('error mr pipeline exception', project_url, e)

            awardemojis = mr.awardemojis.list(
                all=True, retry_transient_errors=True)
            for emoji in awardemojis:
                emoji_attr = emoji.attributes
                tmp_mr['awardemojis'].append(
                    {'id': emoji_attr['id'], 'name': emoji_attr['name']})

            mrs_attributes.append(tmp_mr)
        if mrs_attributes:
            self.save_pkl(repo_folder + 'mrs_attributes.pkl', mrs_attributes)

    def get_issues(self, project_url, project_id, repo_folder):
        try:
            project = self.gl.projects.get(
                project_id, retry_transient_errors=True)
        except Exception as e:
            print('error issue project exception', project_url, e)
            return
        try:
            issues = project.issues.list(all=True, retry_transient_errors=True)
        except Exception as e:
            print('error issue issue exception', project_url, e)
            return
        issues_attributes = list()
        for issue in issues:
            issues_attributes.append(issue.attributes)
        self.save_pkl(repo_folder + 'issues_attributes.pkl', issues_attributes)

    def get_members(self, project_url, project_id, repo_folder):
        try:
            project = self.gl.projects.get(
                project_id, retry_transient_errors=True)
        except Exception as e:
            print('error member project exception', project_url, e)
            return
        try:
            members = project.members.all(
                all=True, retry_transient_errors=True)
        except Exception as e:
            print('error member member exception', project_url, e)
            return
        members_attributes = list()
        for member in members:
            members_attributes.append(member.attributes)
        self.save_pkl(repo_folder + 'members_attributes.pkl',
                      members_attributes)

    def get_single_project(self, project_keys, projects):
        while True:
            try:
                project_id = project_keys.pop()
            except Exception as e:
                print(e)
                if len(project_keys) == 0:
                    break
                continue

            group_full_path = projects[project_id]['namespace']['full_path']
            if group_full_path.find('/3rd') > 0 or \
                    group_full_path.find('/thirdparty') > 0 or \
                    group_full_path.find('/third_party') > 0 or \
                    group_full_path.find('/third-party') > 0 or \
                    group_full_path.find('/3rdparty') > 0 or \
                    group_full_path.find('third_party') == 0:
                continue
            if projects[project_id]['archived']:
                continue

            raw_data_repo_path = self.save_path['raw_data_repo_path']
            repo_folder = raw_data_repo_path + str(project_id) + '/'
            if not os.path.exists(repo_folder):
                os.makedirs(repo_folder)

            # self.get_events(projects[project_id]
            #                 ['web_url'], project_id, repo_folder)
            self.get_branch_and_tag(projects[project_id]
                                    ['web_url'], project_id, repo_folder)
            self.get_mrs(projects[project_id]['web_url'],
                         project_id, repo_folder)
            # self.get_issues(projects[project_id]
            #                 ['web_url'], project_id, repo_folder)
            # self.get_members(projects[project_id]['web_url'],
            #                  project_id, repo_folder)

    def get_project_raw(self):
        raw_data_path = self.save_path['raw_data_path']
        projects = self.read_pkl(
            raw_data_path + 'public_projects_attributes.pkl')
        project_keys = list(projects.keys())
        for i in self.exclude_repo:
            if i in project_keys:
                project_keys.remove(i)

        # threadLock = threading.Lock()
        threads = list()
        for i in range(self.get_single_project_thread):
            tr = threading.Thread(
                target=self.get_single_project, args=(project_keys, projects))
            threads.append(tr)
        for i in threads:
            i.start()
        for i in threads:
            i.join()

    def get_group_members(self, group_url, group_id, group_folder):
        print(time.ctime(), 'get_group_members', group_id)
        try:
            group = self.gl.groups.get(
                group_id, retry_transient_errors=True)
        except Exception as e:
            print('error member group exception', group_url, e)
            return
        try:
            members = group.members.all(
                all=True, retry_transient_errors=True)
        except Exception as e:
            print('error group member exception', group_url, e)
            return
        members_attributes = list()
        for member in members:
            members_attributes.append(member.attributes)
        self.save_pkl(group_folder + 'members_attributes.pkl',
                      members_attributes)

    def get_single_group(self, group_keys, groups):
        while True:
            try:
                group_id = group_keys.pop()
            except Exception as e:
                print(e)
                if len(group_keys) == 0:
                    break
                continue
            raw_data_group_path = self.raw_data_group_path
            group_folder = raw_data_group_path + str(group_id) + '/'
            if not os.path.exists(group_folder):
                os.makedirs(group_folder)
            self.get_group_members(groups[group_id]['web_url'],
                                   group_id, group_folder)

    def get_group_raw(self):
        raw_data_path = self.save_path['raw_data_path']
        groups = self.read_pkl(
            raw_data_path + 'groups_attributes.pkl')
        groups_keys = list(groups.keys())
        # groups_keys = [3528]

        # threadLock = threading.Lock()
        threads = list()
        for i in range(self.get_single_project_thread):
            tr = threading.Thread(
                target=self.get_single_group, args=(groups_keys, groups))
            threads.append(tr)
        for i in threads:
            i.start()
        for i in threads:
            i.join()

    def get_commits(self):
        file_path = self.save_path
        raw_data_path = file_path['raw_data_path']
        raw_data_repo_path = file_path['raw_data_repo_path']
        projects_attributes = self.read_pkl(
            raw_data_path + 'public_projects_attributes.pkl')
        for project_id, project_data in projects_attributes.items():
            # if project_id != 8189:
            #     continue
            print(project_id, project_data['web_url'])
            # start_time = int(time.time())
            repo_folder = raw_data_repo_path + str(project_id) + '/'
            if not os.path.exists(repo_folder):
                os.mkdir(repo_folder)

            ssh_url_to_repo = project_data['ssh_url_to_repo']
            tmp_repo = repo_folder + 'tmp_repo'

            if os.path.exists(tmp_repo):
                try:
                    shutil.rmtree(tmp_repo)
                except PermissionError as e:
                    print('PermissionError', tmp_repo, e.strerror)
                    continue
            git_repo_cmd = 'git clone %s %s' % (ssh_url_to_repo, tmp_repo)
            ret, output = self.runcmd(git_repo_cmd)
            if not ret:
                print(git_repo_cmd, 'clone error', ssh_url_to_repo)
                continue

            current_folder = os.getcwd()
            os.chdir(tmp_repo)
            commit_attr_file = repo_folder + 'commit_attributes.pkl'
            commit_attributes = self.get_total_commit_list(project_id,
                                                           ssh_url_to_repo,
                                                           commit_attr_file,
                                                           repo_folder)
            self.update_total_commit_list(project_id, ssh_url_to_repo)
            os.chdir(current_folder)
            self.save_pkl(
                raw_data_repo_path + str(
                    project_id) + '/commit_attributes.pkl', commit_attributes)
            shutil.rmtree(tmp_repo)
            del commit_attributes
            '''
            self.save_pkl(repo_folder + 'counts.pkl', counts)
            self.save_pkl(repo_folder + 'commits.pkl', commits)
            self.save_pkl(repo_folder + 'single_commits.pkl', single_commits)
            '''

            # end_time = int(time.time())
            # run_time = int(end_time - start_time)
            # print('run_time', str(run_time), ssh_url_to_repo)

    def get_latest_commit_in_storage(self, repo_in_db):
        print(str(repo_in_db))
        commit_list = models.Commit.objects.filter(
            repo=repo_in_db[0]).order_by('-id')
        # print(str(commit_list))
        if commit_list:
            # print("最新的提交是：" + str(commit_list))
            return commit_list[0].commit_hash
        else:
            return list()

    def indexOfArray(self, value, array):
        if value in array:
            try:
                index = array.index(value)
            except BaseException:
                index = len(array)
            return index
        else:
            return len(array)

    def update_total_commit_list(self, project_id, ssh_url_to_repo):
        command = 'git --no-pager log --all --since="2020/01/01" ' \
                  '--pretty=format:"%H"'
        repo_in_db = models.Repo.objects.filter(repo_id=project_id)
        # print(1, repo_in_db)
        if repo_in_db:
            # latest_commit_in_storage = self.get_latest_commit_in_storage(
            #     repo_in_db)
            # print("latest commit in storage is: " + str(
            #     latest_commit_in_storage))
            # ret, commit_id_list = self.runcmd(command)
            # if ret and commit_id_list:
            #     commit_id_list = commit_id_list.split('\n')
            #     index = self.indexOfArray(latest_commit_in_storage,
            #                               commit_id_list)
            #     commit_id_list = commit_id_list[0:index]
            #     print(
            #         str(project_id) + ': ' + ' 发现新的提交：' +
            #         str(commit_id_list))
            #     for commit_id in reversed(commit_id_list):
            #         commit_info = self.get_single_commit_info(project_id,
            #             commit_id, ssh_url_to_repo)
            #         # print(str(commit_info))
            #         jira_key = jira_project_name = jira_type =
            #         fixVersions = ''
            #         component_list = list()
            #         jsonDec = json.decoder.JSONDecoder()
            #         if commit_info:
            #             author = None
            #             author_in_sql = models.People.objects.filter(
            #                 user_id=commit_info['author'])
            #             if author_in_sql:
            #                 author = author_in_sql[0]
            #                 # print("author:" + str(author))
            #             # Jira信息直接写入commit中，后期看情况决定是否jira
            #             信息保存进数据库，commit做索引。
            #             if commit_info['jira_ids']:
            #                 jira_key, jira_project_name, jira_type, \
            #                     fixVersions, component_list =
            #                     self.get_jira_data(
            #                         commit_info['jira_ids'][0])
            #             try:
            #                 # models.Commit.objects.filter()
            #                 models.Commit.objects.get_or_create(
            #                     commit_hash=commit_info['commit_hash'],
            #                     author=author,
            #                     author_date=commit_info['author_date'],
            #                     submitter=commit_info['submitter'],
            #                     submitter_date=commit_info['submitter_date'],
            #                     submitter_week=commit_info['submitter_week'],
            #                     submitter_month=commit_info['submitter_month'],
            #                     files=commit_info['files'],
            #                     additions=commit_info['additions'],
            #                     deletions=commit_info['deletions'],
            #                     cr_ph=commit_info['cr_ph'],
            #                     cr_id_skip=commit_info['cr_id_skip'],
            #                     is_3rd_skip=commit_info['3rd_skip'],
            #                     no_3rd_skip=commit_info['no_3rd_skip'],
            #                     postfix_list=json.dumps(
            #                         commit_info['postfix_list'],
            #                         ensure_ascii=False),
            #                     jira_ids=json.dumps(commit_info['jira_ids'],
            #                                         ensure_ascii=False),
            #                     jira_type=jira_type,
            #                     fix_version=fixVersions,
            #                     jira_key=jira_key,
            #                     component_list=json.dumps(component_list,
            #                                               ensure_ascii=False),
            #                     jira_project_name=jira_project_name,
            #                     repo=repo_in_db[0],
            #                     # 从数据库中检索出来方法：
            #
            #                 )
            #                 print("insert successful: ")
            #                 # obj[0].branches.add(1)
            #             except Exception as e:
            #                 print('Insert data error: ', str(commit_info))
            #                 print('Error info:' + str(e))
            # else:
            #     print(commit_id_list, 'error', ssh_url_to_repo)
            # 对commit数据库里每条commit对应的分支进行刷新。
            # commit_in_db = models.Commit.objects.filter(
            #     repo_id=repo_in_db[0].id).order_by('-id')
            # print(2, commit_in_db)
            commit_branch_map = self.get_branch_commit_map(project_id)
            self.save_pkl(self.raw_data_repo_path + str(project_id) +
                          '/commit_branch_map.pkl', commit_branch_map)
            # print("commit_branch_map:" + str(commit_branch_map))
            # for c in commit_in_db:
            #     try:
            #         if c.branches:
            #             c.branches.clear()
            #         else:
            #             print("无绑定分支：" + str(c.commit_hash))
            #         if c.commit_hash in commit_branch_map.keys():
            #             for id in list(commit_branch_map[c.commit_hash]):
            #                 c.bracnhes.add(id)
            #         c.save()
            #         print('添加分支信息成功: ')
            #     except Exception as e:
            #         print('添加分支信息失败: ', str(e))

    def get_total_commit_list(self, project_id, ssh_url_to_repo,
                              commit_attr_file, repo_folder):
        command = 'git --no-pager log --all ' \
                  '--since="2015/01/01" --pretty=format:"%H"'
        commit_attr_item = dict()
        if os.path.exists(commit_attr_file):
            commit_attr_item = self.read_pkl(commit_attr_file)

        merge_item = self.get_pro_merge_list(repo_folder)
        branch_item = self.get_branch_commit_map(project_id)
        ret, commit_id_str = self.runcmd(command)
        if ret and commit_id_str:
            commit_id_list = commit_id_str.split('\n')
            if len(commit_id_list) > 5000:
                commit_id_list = commit_id_list[:5000]
            for commit_id in reversed(commit_id_list):
                if commit_attr_item.get(commit_id):
                    continue
                commit_info = self.get_single_commit_info(
                    project_id, commit_id, ssh_url_to_repo)
                commit_file_info = self.get_single_commit_file_info(
                    project_id, commit_id, ssh_url_to_repo)
                merge_info = merge_item.get(commit_id)
                branch_info = branch_item.get(commit_id)
                # commit_detail = self.get_commit_detail(commit_id)
                commit_attr_item[commit_id] = {
                    'commit_info': commit_info,
                    'commit_file_info': commit_file_info,
                    'commit_id': commit_id,
                    'merge_info': merge_info,
                    'branch_info': branch_info,
                    'commit_detail': {},
                    'project_id': project_id
                }
            return commit_attr_item
        else:
            print('error commit', ssh_url_to_repo)
            return {}

    def get_branch_commit_map(self, project_id):
        branches_list = self.get_total_branch_list()
        commit_branch_map = dict()
        for branch in branches_list:
            since_date = self.select_commit_time_map.get(str(project_id),
                                                         '2015/01/01')
            command = f'git rev-list --since="{since_date}" origin/' + \
                      branch
            ret, commit_id_list = self.runcmd(command)
            if ret and commit_id_list:
                commit_id_list = list(filter(None, commit_id_list.split('\n')))
                for commit_id in reversed(commit_id_list):
                    if commit_id not in commit_branch_map.keys():
                        commit_branch_map[commit_id] = set()
                    commit_branch_map[commit_id].add(branch)
            else:
                print(commit_id_list, 'error branch', str(branch))
        return commit_branch_map

    def get_single_commit_info(self, project_id, commit_id, ssh_url_to_repo):
        commit_show_cmd = ' '.join(
            ['git', '--no-pager', 'show', '--format=fuller',
             '--stat', commit_id])

        ret, commit_message_raw = self.runcmd(commit_show_cmd)
        if not ret:
            print(commit_show_cmd, 'error', ssh_url_to_repo)
            commit_message_raw = ''
        return commit_message_raw

    def get_single_commit_file_info(self, project_id, commit_id, ssh_url_to_repo):
        commit_show_cmd = ' '.join(
            ['git', '--no-pager', 'show', '--format=tformat:',
             '--numstat', commit_id])

        ret, commit_message_raw = self.runcmd(commit_show_cmd)
        if not ret:
            print(commit_show_cmd, 'error', ssh_url_to_repo)
            commit_message_raw = ''
        return commit_message_raw

    def get_total_branch_list(self):
        total_branch_list = list()
        command = 'git branch -r'
        ret, branch_list = self.runcmd(command)
        if ret and branch_list:
            for branch in branch_list.split('\n'):
                branch_name = branch[9:]
                if re.search(self.branch_rule, branch_name):
                    total_branch_list.append(branch_name)
            return total_branch_list
        return total_branch_list

    @staticmethod
    def runcmd(command):
        try:
            ret = subprocess.run(
                command, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            print(f'run cmd {command} exception err: {e} ')
            return False, ''
        if ret.returncode != 0:
            print("runcmd error:", command, ret)
            return False, ''.join(map(chr, ret.stdout))
        return True, ''.join(map(chr, ret.stdout))

    def get_pro_merge_list(self, repo_folder):
        merge_item = {}
        try:
            merge_list = self.read_pkl(repo_folder + 'mrs_attributes.pkl')
            for attr in merge_list:
                merge = attr['data']
                if merge.get('sha') and merge.get('state') == 'merged':
                    # merge['approvals'] = i.approvals.get().attributes
                    merge_item[merge.get('sha')] = merge
            # merge_list = self.gl.projects.get(project_id).mergerequests.list(
            #     all=True, retry_transient_errors=True)
            # for i in merge_list:
            #     merge = i.attributes
            #     if merge.get('sha') and merge.get('state') == 'merged':
            #         merge['approvals'] = i.approvals.get().attributes
            #         merge_item[merge.get('sha')] = merge
            return merge_item

        except:
            return merge_item

    def get_commit_detail(self, commit_id):
        tmp_dict = dict()
        commit_show_cmd = ' '.join(
            ['git', '--no-pager', 'show', '--format=fuller',
             '--stat', commit_id])
        ret, commit_message_raw = self.runcmd(commit_show_cmd)
        if not ret:
            print(commit_show_cmd, 'error', commit_id)
            return tmp_dict
        commit_message = commit_message_raw.split('\n')
        if commit_message[1].find('Merge:') == 0:
            print("Merge commit: " + str(commit_message[1]))
            return tmp_dict
        author = commit_message[1].replace('Author:', '').strip()
        ret, author = self.parse_commit_author(author)
        if not ret:
            return tmp_dict
        author_date = commit_message[2].replace(
            'AuthorDate:', '').split('+')[0].strip()
        author_date = author_date.split('-')[0].strip()

        author_date = time.strftime("%Y-%m-%d", time.strptime(author_date))

        submitter = commit_message[3].replace(
            'Commit:', '').split('+')[0].strip()
        submitter_data = commit_message[4].replace(
            'CommitDate:', '').split('+')[0].strip()
        submitter_data = submitter_data.split('-')[0].strip()
        submitter_data = time.strftime(
            "%Y-%m-%d", time.strptime(submitter_data))
        files = 0
        additions = 0
        deletions = 0
        postfix_set = set()
        for i in range(6, len(commit_message) - 2):
            file = commit_message[i].split('|')[0].strip()
            postfix = os.path.splitext(file)[-1]
            if postfix:
                postfix_set.add(postfix)

        for i in commit_message[-2].split(','):
            tmp_i = i.strip()

            if tmp_i.find('changed') > 0:
                files = tmp_i.split()[0]
            if tmp_i.find('insertion') > 0:
                additions = tmp_i.split()[0]
            if tmp_i.find('deletion') > 0:
                deletions = tmp_i.split()[0]
        ph_case_info = re.findall(self.ph_reg, commit_message_raw)
        commit_info = self.parse_commit_info(commit_message[6])

        tmp_dict['author'] = author
        tmp_dict['author_date'] = author_date
        tmp_dict['submitter'] = submitter
        tmp_dict['submitter_date'] = submitter_data
        tmp_dict['files'] = files
        tmp_dict['additions'] = additions
        tmp_dict['deletions'] = deletions
        tmp_dict['commit_hash'] = commit_id
        tmp_dict['cr_ph'] = ph_case_info
        tmp_dict['jira_ids'] = commit_info['jira_ids']
        tmp_dict['cr_id_skip'] = commit_info['cr_id_skip']
        tmp_dict['3rd_skip'] = commit_info['3rd_skip']
        tmp_dict['no_3rd_skip'] = commit_info['no_3rd_skip']
        tmp_dict['postfix_list'] = list(postfix_set)
        tmp_dict['submitter_month'] = submitter_data[0:7]
        tmp_dict['submitter_week'] = datetime.datetime.strptime(
            submitter_data, '%Y-%m-%d').strftime('%Y-%W')
        return tmp_dict

    def parse_commit_info(self, commit_message_raw):
        output = dict()
        output['jira_ids'] = list()
        id_check_list = commit_message_raw[commit_message_raw.find(
            '[') + 1:commit_message_raw.find(']')].split(' ')
        for id_check in id_check_list:
            if re.match(self.jira_reg, id_check):
                output['jira_ids'].append(id_check)
        if commit_message_raw.find('cr_id_skip') > 0:
            output['cr_id_skip'] = True
        else:
            output['cr_id_skip'] = False
        if commit_message_raw.find('3rd_skip') > 0:
            output['3rd_skip'] = True
        else:
            output['3rd_skip'] = False
        if commit_message_raw.find('no_3rd_skip') > 0:
            output['no_3rd_skip'] = True
        else:
            output['no_3rd_skip'] = False
        return output

    @staticmethod
    def parse_commit_author(author):
        ret = True
        if author.find('test') < 0:
            ret = False
        if author.find('<') > 0:
            author = author.split('<')[1]
        if author.find('@') > 0:
            author = author.split('@')[0]
        return ret, author


def run():
    r = ProjectPkl()
    r.get_projects()
    r.get_personal_public_projects()
    # r.get_groups()
    r.get_project_raw()
    # r.get_group_raw()
    # r.get_jira_projects()
    # r.get_jira_issues()
    t1 = time.time()
    r.get_commits()
    t2 = time.time()
    print('耗時：', t2 - t1)

