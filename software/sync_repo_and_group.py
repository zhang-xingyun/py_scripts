import gitlab
import pickle
import os
import time
import datetime
import argparse
import textwrap
import requests
import sys
import shutil
import subprocess
import threading
import mechanize
from http import cookiejar
from lxml import etree
import re
import json
from jira import JIRA

from django.shortcuts import render
from django.apps import apps
from django.db import connection
from gitlab_app import models
from gitlab_app import people
from gitlab_app import PH


class GetData():
    def __init__(self):
        self.gl = None
        self.cr_report_pw = ''
        self.if_get_commits = True
        self.projects_attributes = dict()
        self.personal_projects_attributes = dict()
        self.public_projects_attributes = dict()
        self.groups_attributes = dict()
        # too much commit exclude
        self.exclude_repo = [7690, 6113, 1359, 6936, 5827, 4863, 1625,
                             1764, 2931, 3195, 4623, 4868, 5733, 7167,
                             7371, 7601, 7604]
        self.raw_data_path = '/opt/gitlab_report/raw_data/'
        self.raw_data_repo_path = '/opt/gitlab_report/raw_data/repo/'
        self.jira_issue_path = '/opt/gitlab_report/jira_data/'
        self.get_single_project_thread = 4
        self.git_cmd_thread = 120
        self.ph_reg = r"Differential Revision: https://cr.test.com/D(\d+)"
        self.jira_reg = r"([A-Z][A-Z0-9_]+-[1-9][0-9]*)"
        self.branch_rule = '^master$|^develop$|^main$|^release-.+|' \
                           '^sprint-.+|^feature-.+|^bugfix-.+|^hotfix-.+|' \
                           '^cicd-.+|^test-.+|^tool-.+|^dev-.+|^rel-.+|' \
                           '^feat-.+'
        # self.jira_data = dict()
        # self.jira_ignore = list()
        # self.jira_conn = JIRA('https://jira.test.com:8443',
        #                         auth=('external', 'HC-dKKa5KhrJ.0'))

    def init_folder(self):
        path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gitlab_cfg = os.path.join(path, 'python-gitlab.cfg')
        self.gl = gitlab.Gitlab.from_config('trigger', [gitlab_cfg])
        self.gl.auth()
        if not os.path.exists(self.raw_data_path):
            os.makedirs(self.raw_data_path)
        if not os.path.exists(self.raw_data_repo_path):
            os.makedirs(self.raw_data_repo_path)
        # if os.path.exists(self.raw_data_path + 'jira.pkl'):
        #    self.jira_data = self.read_pkl(self.raw_data_path + 'jira.pkl')

    def get_groups(self):
        print(time.ctime(), 'get_groups')
        groups = self.gl.groups.list(all=True, retry_transient_errors=True)
        for group_single in groups:
            try:
                group = self.gl.groups.get(
                    group_single.attributes['id'], retry_transient_errors=True)
                self.groups_attributes[
                    group.attributes['id']] = group.attributes
                self.update_group_in_sql(group.attributes)
            except Exception as e:
                print("get group error:" + str(e))
        gourp_file = self.raw_data_path + 'groups_attributes.pkl'
        self.save_pkl(gourp_file, self.groups_attributes)
        print('total group number is %d' % len(self.groups_attributes))

    def get_projects(self):
        print(time.ctime(), 'get_projects')
        projects = self.gl.projects.list(all=True, retry_transient_errors=True,
                                         per_page=80)
        for project in projects:
            self.projects_attributes[project.attributes['id']] = \
                project.attributes
            print("id is: " + str(project.attributes['id']))
            self.update_repo_in_sql(project)
        project_file = self.raw_data_path + 'projects_attributes.pkl'
        self.save_pkl(project_file, self.projects_attributes)

        print('total project number is %d' % len(self.projects_attributes))

    def update_group_in_sql(self, attr):
        # members = self.parse_group_member(attr['id'])
        repos = list()
        try:
            group_attr = self.gl.groups.get(attr['id']).attributes
        except BaseException:
            return
        # if 'projects' in group_attr.keys():
        #     repos = [g['id'] for g in group_attr['projects']]
        #     print(repos)
        if 'projects' in group_attr.keys():
            repos = [g['id'] for g in group_attr['projects']]
        item = {
            'name': attr['name'],
            'full_name': attr['full_name'],
            'full_path': attr['full_path'],
            'parent_id': attr['parent_id'],
            'visibility': attr['visibility'],
            'repos': self.json_encode(repos),
            # 'apply_user': attr[''],
            # 'apply_dept': attr[''],
            # 'apply_comments': attr[''],
            # 'apply_project_manager': attr[''],
            # 'apply_date': attr[''],
            'web_url': attr['web_url'],
            'create_date': attr['created_at'].split('T')[0],
            # 'project_name': attr['name'],
            # 'maintainer': self.json_encode(members.get('Maintainer',
            # list())),
            # 'developer': self.json_encode(members.get('Developer', list())),
            # 'reporter': self.json_encode(members.get('Reporter', list())),
            # 'guest': self.json_encode(members.get('Guest', list())),
            # 'owner': self.json_encode(members.get('Owner', list())),
        }
        try:
            group_in_db = models.Group.objects.update_or_create(item,
                                                                group_id=attr[
                                                                    'id'])
        except Exception as e:
            print('Insert group error: ', str(e))

    def update_repo_in_sql(self, project):
        try:
            repo_in_db = models.Repo.objects.filter(
                repo_id=project.attributes['id'])
            if repo_in_db:
                repo_in_db[0].name = project.attributes['name']
                repo_in_db[0].create_date = \
                    project.attributes['created_at'].split('T')[0]
                repo_in_db[0].project_last_activity_at = \
                    project.attributes['last_activity_at'].split('T')[0]
                repo_in_db[0].web_url = project.attributes['web_url']
                repo_in_db[0].archived = project.attributes['archived']
                repo_in_db[0].ssh_url_to_repo = \
                    project.attributes['ssh_url_to_repo']
                repo_in_db[0].save()
            else:
                newrepo = models.Repo(
                    repo_id=project.attributes['id'],
                    name=project.attributes['name'],
                    project='',
                    repo_access_level='',
                    apply_date='',
                    create_date=project.attributes['created_at'].split('T')[0],
                    project_last_activity_at=project.attributes[
                        'last_activity_at'].split('T')[0],
                    apply_dept='',
                    apply_project_manager='',
                    apply_user='',
                    apply_comments='',
                    repo_subgroup_url='',
                    web_url=project.attributes['web_url'],
                    project_name='',
                    archived=project.attributes['archived'],
                    ssh_url_to_repo=project.attributes['ssh_url_to_repo'],
                )
                newrepo.save()
        except Exception as e:
            print("插入数据失败:", str(e))
        else:
            # 如果是插入数据， 一定要提交数据， 不然数据库中找不到要插入的数据;
            print("插入数据成功;")

    def get_personal_public_projects(self):
        projects = self.read_pkl(
            self.raw_data_path + 'projects_attributes.pkl')
        # groups = self.read_pkl(self.raw_data_path + 'groups_attributes.pkl')
        for project_id, project_data in projects.items():
            # print(project_data['namespace']['parent_id'])
            # if project_data['namespace']['parent_id'] in groups.keys():
            if project_data['namespace']['kind'] == 'user':
                self.personal_projects_attributes[project_id] = project_data
            else:
                self.public_projects_attributes[project_id] = project_data
        public_project_file = \
            self.raw_data_path + 'public_projects_attributes.pkl'
        personal_project_file = \
            self.raw_data_path + 'personal_projects_attributes.pkl'
        self.save_pkl(public_project_file, self.public_projects_attributes)
        self.save_pkl(personal_project_file, self.personal_projects_attributes)

    def get_branch_and_tag(self, project_url, project_id, repo_folder):
        print(time.ctime(), 'get_branches', project_id)
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
        try:
            tags = project.tags.list(all=True, retry_transient_errors=True)
        except Exception as e:
            print('error tag exception', project_url, e)
            return
        branches_attributes = dict()
        for branch in branches:
            if re.search(self.branch_rule, branch.attributes['name']):
                branches_attributes[branch.name] = branch.attributes
                self.update_branch_list_in_sql(project_id, branch.attributes)
        for tag in tags:
            self.update_tag_list_in_sql(project_id, tag.attributes)
        self.save_pkl(repo_folder + 'branches_attributes.pkl',
                      branches_attributes)
        self.save_pkl(repo_folder + 'tags_attributes.pkl',
                      tags_attributes)

    def get_events(self, project_url, project_id, repo_folder):
        print(time.ctime(), 'get_events', project_id)
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
            # print(str(event.attributes))
            events_attributes.append(event.attributes)
        self.save_pkl(repo_folder + 'events_attributes.pkl', events_attributes)

    def get_mrs(self, project_url, project_id, repo_folder):
        print(time.ctime(), 'get_mrs', project_id)
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
            mrs_attributes.append(tmp_mr)
        self.save_pkl(repo_folder + 'mrs_attributes.pkl', mrs_attributes)

    def get_issues(self, project_url, project_id, repo_folder):
        print(time.ctime(), 'get_issues', project_id)
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
        print(time.ctime(), 'get_members', project_id)
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
            print(project_id, 'get_single_project',
                  projects[project_id]['web_url'])
            repo_folder = self.raw_data_repo_path + str(project_id) + '/'
            if not os.path.exists(repo_folder):
                os.makedirs(repo_folder)
            group_full_path = projects[project_id]['namespace']['full_path']
            if group_full_path.find('/3rd') > 0 or \
                    group_full_path.find('/thirdparty') > 0 or \
                    group_full_path.find('/third_party') > 0 or \
                    group_full_path.find('/third-party') > 0 or \
                    group_full_path.find('/3rdparty') > 0 or \
                    group_full_path.find('third_party') == 0:
                print('3rd ignore', projects[project_id]['web_url'])
                continue
            if projects[project_id]['archived']:
                print('archived project ignore',
                      projects[project_id]['web_url'])
                continue
            self.get_events(projects[project_id]
                            ['web_url'], project_id, repo_folder)
            self.get_branch_and_tag(projects[project_id]
                                    ['web_url'], project_id, repo_folder)
            self.get_mrs(projects[project_id]['web_url'],
                         project_id, repo_folder)
            self.get_issues(projects[project_id]
                            ['web_url'], project_id, repo_folder)
            self.get_members(projects[project_id]['web_url'],
                             project_id, repo_folder)

    def get_project_raw(self):
        projects = self.read_pkl(
            self.raw_data_path + 'public_projects_attributes.pkl')
        project_keys = list(projects.keys())
        # project_keys = [8189, 7099, 8247, 4641, 2167]
        for i in self.exclude_repo:
            if i in project_keys:
                project_keys.remove(i)
        # for project_id, project_data in projects.items():
        #    group_full_path = project_data['namespace']['full_path']
        #    if group_full_path.find('/3rd') > 0 or \
        #       group_full_path.find('/thirdparty') > 0 or \
        #       group_full_path.find('/third_party') > 0 or \
        #       group_full_path.find('/third-party') > 0 or \
        #       group_full_path.find('/3rdparty') > 0 or \
        #       group_full_path.find('third_party') == 0 :
        #       #group_full_path.find('/experimental') > 0:
        #        print('3rd ignore', project_data['web_url'])
        #        project_keys.remove(project_id)
        # debug
        # project_keys = [7972]
        # debug end
        threadLock = threading.Lock()
        threads = list()
        for i in range(self.get_single_project_thread):
            tr = threading.Thread(
                target=self.get_single_project, args=(project_keys, projects))
            threads.append(tr)
        for i in threads:
            i.start()
        for i in threads:
            i.join()

    def runcmd(self, command):
        # print('run cmd---- ', command)
        try:
            ret = subprocess.run(
                command, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            print(e)
            print('run cmd exception change to gpk ---- ', command)
            return (False, '')
        if ret.returncode != 0:
            # print('error', command, ret.stdout)
            print("error:", command, ret.returncode)
            # sys.exit(1)
            return (False, ''.join(map(chr, ret.stdout)))
        return (True, ''.join(map(chr, ret.stdout)))

    def parse_loc_count(self, loc_info):
        print(time.ctime(), 'parse_loc_count')
        tmp_dict = dict()
        for line in loc_info.split('\n'):
            line_parse = line.split()
            if len(line_parse) != 6:
                continue
            if line_parse[0] == 'Language':
                continue
            # print(line_parse)
            if line_parse[0] not in tmp_dict.keys():
                tmp_dict[line_parse[0]] = dict()
            tmp_dict[line_parse[0]]['Files'] = line_parse[1]
            tmp_dict[line_parse[0]]['Lines'] = line_parse[2]
            tmp_dict[line_parse[0]]['Blank'] = line_parse[3]
            tmp_dict[line_parse[0]]['Comment'] = line_parse[4]
            tmp_dict[line_parse[0]]['Code'] = line_parse[5]
        return tmp_dict

    def run_thread(self, cls, commit_id_list, commit_list,
                   single_commits, ssh_url_to_repo):
        while True:
            try:
                commit_id = commit_id_list.pop()
                if commit_id in single_commits.keys():
                    # print('commit exist')
                    commit_list.append(single_commits[commit_id])
                    # print(len(commit_list))
                    continue
            except BaseException:
                if len(commit_id_list) == 0:
                    break
                continue
            # print(commit_id)
            commit_show_cmd = ' '.join(
                ['git', '--no-pager', 'show', '--format=fuller',
                 '--stat', commit_id])
            # print('----------------------------------------------------')
            # print(commit_show_cmd)
            ret, commit_message_raw = self.runcmd(commit_show_cmd)
            if not ret:
                print(commit_show_cmd, 'error', ssh_url_to_repo)
                continue
            # print(commit_message_raw)
            commit_message = commit_message_raw.split('\n')
            # print(commit_message)
            if commit_message[1].find('Merge:') == 0:
                continue
            #
            author = commit_message[1].replace('Author:', '').strip()
            # if author.find('horizon') < 0 and \
            #   author.find('hogpu') < 0 and \
            #   author.find('hogpu') < 0 :
            #    continue
            author_date = commit_message[2].replace(
                'AuthorDate:', '').split('+')[0].strip()
            author_date = author_date.split('-')[0].strip()
            # print(author_date)
            author_date = time.strftime("%Y-%m-%d", time.strptime(author_date))
            # except Exception as e:
            #    print(e,'1111111111111111111111111111111')
            #    print(commit_message_raw)
            #
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
            # print(str(postfix_set))
            for i in commit_message[-2].split(','):
                tmp_i = i.strip()
                # print(tmp_i)
                if tmp_i.find('changed') > 0:
                    files = tmp_i.split()[0]
                if tmp_i.find('insertion') > 0:
                    additions = tmp_i.split()[0]
                if tmp_i.find('deletion') > 0:
                    deletions = tmp_i.split()[0]
            ph_case_info = re.findall(self.ph_reg, commit_message_raw)
            # print(ph_case_info)
            commit_info = self.parse_commit_info(
                commit_message[6], commit_id, ssh_url_to_repo)
            # print(author,date,files,additions,deletions)
            # print(commit_info)
            tmp_dict = dict()
            tmp_dict['author'] = author
            tmp_dict['author_date'] = author_date
            tmp_dict['submitter'] = submitter
            tmp_dict['submitter_data'] = submitter_data
            tmp_dict['files'] = files
            tmp_dict['additions'] = additions
            tmp_dict['deletions'] = deletions
            tmp_dict['commit'] = commit_id
            tmp_dict['cr_ph'] = ph_case_info
            tmp_dict['jira_data'] = commit_info['jira_ids']
            tmp_dict['cr_id_skip'] = commit_info['cr_id_skip']
            tmp_dict['3rd_skip'] = commit_info['3rd_skip']
            tmp_dict['no_3rd_skip'] = commit_info['no_3rd_skip']
            tmp_dict['postfix_list'] = list(postfix_set)
            commit_list.append(tmp_dict)
            single_commits[commit_id] = tmp_dict

            # print(tmp_dict)
            # print('++++++++++++++++++++++++++++++++++++++++')

    def parse_commit_info(self, commit_message_raw, commit_id,
                          ssh_url_to_repo):
        output = dict()
        output['jira_ids'] = list()
        id_check_list = commit_message_raw[commit_message_raw.find(
            '[') + 1:commit_message_raw.find(']')].split(' ')
        for id_check in id_check_list:
            if re.match(self.jira_reg, id_check):
                output['jira_ids'].append(id_check)
        #
        if commit_message_raw.find('cr_id_skip') > 0:
            output['cr_id_skip'] = True
        else:
            output['cr_id_skip'] = False
        #
        if commit_message_raw.find('3rd_skip') > 0:
            output['3rd_skip'] = True
        else:
            output['3rd_skip'] = False
        #
        if commit_message_raw.find('no_3rd_skip') > 0:
            output['no_3rd_skip'] = True
        else:
            output['no_3rd_skip'] = False
        return output

    def commit_parse_thread(self, cls, commit_id_list, single_commits,
                            ssh_url_to_repo):
        print(time.ctime(), 'commit_id_list', len(commit_id_list))
        # print(commit_id_list[0])
        # while len(commit_id_list) != 0:
        #    print(commit_id_list.pop())
        threads = list()
        data = dict()
        output = list()
        for i in range(self.git_cmd_thread):
            data[i] = list()
            tr = threading.Thread(target=self.run_thread, args=(
                cls, commit_id_list, data[i], single_commits, ssh_url_to_repo))
            threads.append(tr)
        for i in threads:
            i.start()
        for i in threads:
            i.join()
        for i, j in data.items():
            # print(i,len(j))
            output.extend(j)
        return output

    def get_mysql_connection(self, project_id, table_type):
        # RuntimeWarning: Model '__main__.logclasslog_' was already registered.
        # Reloading models is not advised as it can lead to inconsistencies
        # most notably with related models.
        # 如上述警告所述, Django 不建议重复加载 Model 的定义.
        # 作为 demo 可以直接通过get_log_model获取，无视警告.
        # 所以这里先通过 all_models 获取已经注册的 Model,
        # 如果获取不到， 再生成新的模型.
        if table_type == 'commit':
            try:
                cls = apps.get_model('__main__', 'Commit_%s' % project_id)
            except LookupError:
                cls = models.get_commit_model(project_id)
        elif table_type == 'branch_commit':
            try:
                cls = apps.get_model('__main__',
                                     'Branch_commit_%s' % project_id)
                cls.objects.filter().delete()
                # cls.delete()
                # cls = models.get_branch_commit_model(project_id)
            except LookupError:
                cls = models.get_branch_commit_model(project_id)
        else:
            try:
                cls = apps.get_model('__main__', 'Branch_%s' % project_id)
            except LookupError:
                cls = models.get_branch_model(project_id)

        if not cls.is_exists():
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(cls)
        return cls
        # commit = cls(level=10, msg="Hello")
        # commit.save()

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

    def parse_commit_author(self, author):
        tmp_author = author
        ret = True
        if tmp_author.find('test') < 0:
            ret = False
        if tmp_author.find('<') > 0:
            tmp_author = tmp_author.split('<')[1]
        if tmp_author.find('@') > 0:
            tmp_author = tmp_author.split('@')[0]
        return ret, tmp_author

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
        if repo_in_db:
            latest_commit_in_storage = self.get_latest_commit_in_storage(
                repo_in_db)
            print("latest commit in storage is: " + str(
                latest_commit_in_storage))
            ret, commit_id_list = self.runcmd(command)
            if ret and commit_id_list:
                commit_id_list = commit_id_list.split('\n')
                index = self.indexOfArray(latest_commit_in_storage,
                                          commit_id_list)
                commit_id_list = commit_id_list[0:index]
                print(
                    str(project_id) + ': ' + ' 发现新的提交：' + str(commit_id_list))
                for commit_id in reversed(commit_id_list):
                    commit_info = self.get_single_commit_info(
                        commit_id, ssh_url_to_repo)
                    # print(str(commit_info))
                    jira_key = jira_project_name = jira_type = fixVersions = ''
                    component_list = list()
                    jsonDec = json.decoder.JSONDecoder()
                    if commit_info:
                        author = None
                        author_in_sql = models.People.objects.filter(
                            user_id=commit_info['author'])
                        if author_in_sql:
                            author = author_in_sql[0]
                            # print("author:" + str(author))
                        # Jira信息直接写入commit中，后期看情况决定是否jira信息保存进数据库，commit做索引。
                        if commit_info['jira_ids']:
                            jira_key, jira_project_name, jira_type, \
                                fixVersions, component_list = \
                                self.get_jira_data(
                                    commit_info['jira_ids'][0])
                        try:
                            # models.Commit.objects.filter()
                            models.Commit.objects.get_or_create(
                                commit_hash=commit_info['commit_hash'],
                                author=author,
                                author_date=commit_info['author_date'],
                                submitter=commit_info['submitter'],
                                submitter_date=commit_info['submitter_date'],
                                submitter_week=commit_info['submitter_week'],
                                submitter_month=commit_info['submitter_month'],
                                files=commit_info['files'],
                                additions=commit_info['additions'],
                                deletions=commit_info['deletions'],
                                cr_ph=commit_info['cr_ph'],
                                cr_id_skip=commit_info['cr_id_skip'],
                                is_3rd_skip=commit_info['3rd_skip'],
                                no_3rd_skip=commit_info['no_3rd_skip'],
                                postfix_list=json.dumps(
                                    commit_info['postfix_list'],
                                    ensure_ascii=False),
                                jira_ids=json.dumps(commit_info['jira_ids'],
                                                    ensure_ascii=False),
                                jira_type=jira_type,
                                fix_version=fixVersions,
                                jira_key=jira_key,
                                component_list=json.dumps(component_list,
                                                          ensure_ascii=False),
                                jira_project_name=jira_project_name,
                                repo=repo_in_db[0],
                                # 从数据库中检索出来方法：

                            )
                            print("insert successful: ")
                            # obj[0].branches.add(1)
                        except Exception as e:
                            print('Insert data error: ', str(commit_info))
                            print('Error info:' + str(e))
            else:
                print(commit_id_list, 'error', ssh_url_to_repo)
            # 对commit数据库里每条commit对应的分支进行刷新。
            commit_in_db = models.Commit.objects.filter(
                repo_id=repo_in_db[0].id).order_by('-id')
            branches_in_db = models.Branch.objects.filter(
                repo_id=repo_in_db[0].id)
            commit_branch_map = self.get_branch_commit_map(project_id,
                                                           branches_in_db)
            # print("commit_branch_map:" + str(commit_branch_map))
            for c in commit_in_db:
                try:
                    if c.branches:
                        c.branches.clear()
                    else:
                        print("无绑定分支：" + str(c.commit_hash))
                    if c.commit_hash in commit_branch_map.keys():
                        for id in list(commit_branch_map[c.commit_hash]):
                            c.branches.add(id)
                    c.save()
                    print('添加分支信息成功: ')
                except Exception as e:
                    print('添加分支信息失败: ', str(e))

    def get_single_commit_info(self, commit_id, ssh_url_to_repo):
        # print(commit_id)
        tmp_dict = dict()
        commit_show_cmd = ' '.join(
            ['git', '--no-pager', 'show', '--format=fuller',
             '--stat', commit_id])
        # print('----------------------------------------------------')
        # print(commit_show_cmd)
        ret, commit_message_raw = self.runcmd(commit_show_cmd)
        if not ret:
            print(commit_show_cmd, 'error', ssh_url_to_repo)
            return tmp_dict
        # print(commit_message_raw)
        commit_message = commit_message_raw.split('\n')
        print(commit_message)
        if commit_message[1].find('Merge:') == 0:
            print("Merge commit: " + str(commit_message[1]))
            return tmp_dict
        #
        author = commit_message[1].replace('Author:', '').strip()
        # if author.find('horizon') < 0 and \
        #   author.find('hogpu') < 0 and \
        #   author.find('hogpu') < 0 :
        #    continue
        ret, author = self.parse_commit_author(author)
        if not ret:
            return tmp_dict
        author_date = commit_message[2].replace(
            'AuthorDate:', '').split('+')[0].strip()
        author_date = author_date.split('-')[0].strip()
        # print(author_date)
        author_date = time.strftime("%Y-%m-%d", time.strptime(author_date))
        # except Exception as e:
        #    print(e,'1111111111111111111111111111111')
        #    print(commit_message_raw)
        #
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
        # print(str(postfix_set))
        for i in commit_message[-2].split(','):
            tmp_i = i.strip()
            # print(tmp_i)
            if tmp_i.find('changed') > 0:
                files = tmp_i.split()[0]
            if tmp_i.find('insertion') > 0:
                additions = tmp_i.split()[0]
            if tmp_i.find('deletion') > 0:
                deletions = tmp_i.split()[0]
        ph_case_info = re.findall(self.ph_reg, commit_message_raw)
        # print(ph_case_info)
        commit_info = self.parse_commit_info(
            commit_message[6], commit_id, ssh_url_to_repo)
        # print(author,date,files,additions,deletions)
        # print(commit_info)

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
        # commit_list.append(tmp_dict)
        # single_commits[commit_id] = tmp_dict
        return tmp_dict

    def update_tag_list_in_sql(self, project_id, attributes):
        try:
            events = list()
            events_file_path = self.raw_data_path + '/repo/' + str(
                project_id) + '/events_attributes.pkl'
            if os.path.exists(events_file_path):
                events = self.read_pkl(events_file_path)
            freeze = False
            if attributes['protected']:
                if not attributes['developers_can_push'] and \
                        not attributes['developers_can_merge'] and \
                        not attributes['can_push'] and \
                        not attributes['default']:
                    freeze = True
            # if self.raw_projects[project_id]['archived']:
            #     freeze = True
            tag_create = 'more_unknown'
            author_username = 'more_unknown'
            for event in events:
                if event['action_name'] == 'pushed new' and \
                        event['push_data']['ref'] == attributes['name']:
                    tag_create = event['created_at'].split('T')[0]
                    author_username = event['author_username']
            repo_in_db = models.Repo.objects.filter(repo_id=project_id)
            print(str(repo_in_db))
            # models.Branch.objects.all().delete()
            tag_in_db = models.Tag.objects.filter(repo=repo_in_db[0],
                                                  tag_name=attributes['name'])
            print("tag_name:" + attributes['name'])
            print(str(tag_in_db))
            if tag_in_db:
                tag_in_db[0].commit_hash = attributes['target']
                tag_in_db[0].web_url = attributes['commit']['web_url']
                tag_in_db[0].create_date = tag_create.split('T')[0]
                tag_in_db[0].freezed = freeze
                tag_in_db[0].save()
            else:
                newtag = models.Tag(
                    repo=repo_in_db[0],
                    tag_name=attributes['name'],
                    web_url=attributes['commit']['web_url'],
                    commit_hash=attributes['target'],
                    create_date=tag_create.split('T')[0],
                    freezed=freeze,
                )
                newtag.save()
        except Exception as e:
            print("插入数据失败:", str(e))
        else:
            # 如果是插入数据， 一定要提交数据， 不然数据库中找不到要插入的数据;
            print("插入数据成功;")

    def update_branch_list_in_sql(self, project_id, attributes):
        try:
            events = list()
            events_file_path = self.raw_data_path + '/repo/' + str(
                project_id) + '/events_attributes.pkl'
            if os.path.exists(events_file_path):
                events = self.read_pkl(events_file_path)
            freeze = False
            if attributes['protected']:
                if not attributes['developers_can_push'] and \
                        not attributes['developers_can_merge'] and \
                        not attributes['can_push'] and \
                        not attributes['default']:
                    freeze = True
            # if self.raw_projects[project_id]['archived']:
            #     freeze = True
            branch_create = 'more_unknown'
            author_username = 'more_unknown'
            for event in events:
                if event['action_name'] == 'pushed new' and \
                        event['push_data']['ref'] == attributes['name']:
                    branch_create = event['created_at'].split('T')[0]
                    author_username = event['author_username']
            repo_in_db = models.Repo.objects.filter(repo_id=project_id)
            print(str(repo_in_db))
            # models.Branch.objects.all().delete()
            branch_in_db = models.Branch.objects.filter(repo=repo_in_db[0],
                                                        branch_name=attributes[
                                                            'name'])
            print(str(branch_in_db))
            print("branch_name:" + attributes['name'])
            print(str(branch_in_db))
            if branch_in_db:
                branch_in_db[0].create_date = branch_create.split('T')[0]
                branch_in_db[0].freezed = freeze
                branch_in_db[0].save()
            else:
                newBranch = models.Branch(
                    repo=repo_in_db[0],
                    branch_name=attributes['name'],
                    apply_user='',
                    apply_dept='',
                    apply_comments='',
                    apply_project_manager='',
                    base_branch_name='',
                    apply_date='',
                    project='',
                    create_date=branch_create.split('T')[0],
                    project_name='',
                    freezed=freeze,
                )
                newBranch.save()
        except Exception as e:
            print("插入数据失败:", str(e))
        else:
            # 如果是插入数据， 一定要提交数据， 不然数据库中找不到要插入的数据;
            print("插入数据成功;")

    def get_branch_commit_map(self, project_id, branches_in_db):
        # cls_bc = self.get_mysql_connection(project_id, "branch_commit")
        # cls = self.get_mysql_connection(project_id, "commit")
        commit_branch_map = dict()
        for branch in branches_in_db:
            # if branch_name != 'feature-niubi':
            #     continue
            print("branch:" + branch.branch_name)
            command = 'git rev-list --since="2020/01/01" origin/' + \
                      branch.branch_name
            ret, commit_id_list = self.runcmd(command)
            # print("comit_id_list:" + str(commit_id_list))
            if ret and commit_id_list:
                commit_id_list = list(filter(None, commit_id_list.split('\n')))
                for commit_id in reversed(commit_id_list):
                    print(commit_id)
                    if commit_id not in commit_branch_map.keys():
                        commit_branch_map[commit_id] = set()
                    commit_branch_map[commit_id].add(branch)
            else:
                print(commit_id_list, 'error', str(branch.branch_name))
        return commit_branch_map

    def get_commits(self):
        # print(project_id, 'get_commits', projects[project_id]['web_url'])
        # repo_folder = self.raw_data_repo_path + str(project_id) + '/'
        projects_attributes = self.read_pkl(
            self.raw_data_path + 'public_projects_attributes.pkl')
        for project_id, project_data in projects_attributes.items():
            # print(project_id)
            # debug
            start_time = int(time.time())
            repo_folder = self.raw_data_repo_path + str(project_id) + '/'
            if not os.path.exists(repo_folder + 'branches_attributes.pkl'):
                print('no branch data', project_data['web_url'])
                continue
            if project_data['archived'] == 'True':
                continue
            print(project_id, project_data)
            ssh_url_to_repo = project_data['ssh_url_to_repo']
            tmp_repo = repo_folder + 'tmp_repo'
            counts = dict()
            commits = dict()
            single_commits = dict()
            if os.path.exists(tmp_repo):
                shutil.rmtree(tmp_repo)
            print(ssh_url_to_repo)
            git_repo_cmd = 'git clone %s %s' % (ssh_url_to_repo, tmp_repo)
            print(git_repo_cmd)
            ret, output = self.runcmd(git_repo_cmd)
            if not ret:
                print(git_repo_cmd, 'error', ssh_url_to_repo)
                continue
            current_folder = os.getcwd()
            os.chdir(tmp_repo)
            print(os.getcwd())
            self.update_total_commit_list(project_id, ssh_url_to_repo)
            # total_branch_list = self.get_total_branch_list()
            # print('total:' + str(total_branch_list))
            # self.update_branch_commit_list(project_id, total_branch_list)

            os.chdir(current_folder)
            print(os.getcwd())
            shutil.rmtree(tmp_repo)
            '''
            self.save_pkl(repo_folder + 'counts.pkl', counts)
            self.save_pkl(repo_folder + 'commits.pkl', commits)
            self.save_pkl(repo_folder + 'single_commits.pkl', single_commits)
            '''

            end_time = int(time.time())
            run_time = int((end_time - start_time) / 60)
            print('run_time', str(run_time), ssh_url_to_repo)
        # self.save_pkl(self.raw_data_path + 'jira.pkl', self.jira_data)
        # self.jira_ignore = list(set(self.jira_ignore))
        # print(self.jira_ignore)

    def get_total_branch_list(self):
        total_branch_list = list()
        command = 'git branch -r'
        ret, branch_list = self.runcmd(command)
        if ret and branch_list:
            for branch in branch_list.split('\n'):
                print(branch)
                branch_name = branch[9:]
                if branch_name.find('->') < 0 and branch_name:
                    print(branch_name)
                    total_branch_list.append(branch_name)
            return total_branch_list
        return total_branch_list

    def get_users(self):
        users_attributes = list()
        users = self.gl.users.list(all=True, retry_transient_errors=True)
        for user in users:
            users_attributes.append(user.attributes)
        user_file = self.raw_data_path + 'users_attributes.pkl'
        self.save_pkl(user_file, users_attributes)

    def get_user_permission(self, username, br, user_permissions):
        print('get_user_permission', username)
        user_url = 'http://gitlab.test.com/admin/users/%s/projects' % username
        response = br.open(user_url, timeout=60)
        data = response.get_data()
        data_str = str(data, encoding="utf-8")
        tree = etree.HTML(data_str)
        # get group
        r = tree.xpath('//li[@class="group_member"]')
        for i in r:
            a = i.xpath('./strong/a')[0].attrib.get('href')
            span = i.xpath('./div/span')[0].text
            tmp_dict = dict()
            tmp_dict['username'] = username
            tmp_dict['group_path'] = a
            tmp_dict['permission'] = span
            user_permissions.append(tmp_dict)
        r = tree.xpath('//li[@class="project_member"]')
        for i in r:
            a = i.xpath(
                './div[@class="list-item-name"]/a')[0].attrib.get('href')
            span = i.xpath('./div[@class="float-right"]/span')[0].text
            tmp_dict = dict()
            tmp_dict['username'] = username
            tmp_dict['project_path'] = a
            tmp_dict['permission'] = span
            user_permissions.append(tmp_dict)

    def init_br(self):
        br = mechanize.Browser()
        cj = cookiejar.CookieJar()
        br.set_cookiejar(cj)
        br.set_handle_equiv(True)
        br.set_handle_gzip(True)
        br.set_handle_redirect(True)
        br.set_handle_referer(True)
        br.set_handle_robots(False)
        browser_info = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:15.0)'
        browser_info = browser_info + ' Gecko/20100101 Firefox/15.0.1'
        #
        br.set_handle_refresh(
            mechanize._http.HTTPRefreshProcessor(), max_time=1)
        br.set_debug_http(False)
        #
        br.addheaders = [('User-agent', browser_info)]
        #
        response = br.open(
            'https://gitlab.test.com/users/sign_in')
        #
        print(response)
        br.select_form(nr=1)
        #
        br.form['user[login]'] = 'cr_report'
        br.form['user[password]'] = self.cr_report_pw
        #
        br.submit()
        return br

    def get_permissions(self):
        users_attributes = self.read_pkl(
            self.raw_data_path + 'users_attributes.pkl')
        br = self.init_br()
        user_permissions = list()
        for user in users_attributes:
            if user['state'] in ['blocked', 'ldap_blocked']:
                continue
            self.get_user_permission(user['username'], br, user_permissions)
        print('user_permissions total', len(user_permissions))
        permission_file = self.raw_data_path + 'permission_attributes.pkl'
        self.save_pkl(permission_file, user_permissions)

    def parse_permissions(self):
        projects_attributes = self.read_pkl(
            self.raw_data_path + 'public_projects_attributes.pkl')
        groups_attributes = self.read_pkl(
            self.raw_data_path + 'groups_attributes.pkl')
        users_attributes = self.read_pkl(
            self.raw_data_path + 'users_attributes.pkl')
        user_permissions = self.read_pkl(
            self.raw_data_path + 'permission_attributes.pkl')
        output = dict()
        for user_dict in user_permissions:
            username = user_dict['username']
            # if username != 'xiaofeng.ling':
            #    continue
            # print(user_dict)
            if 'project_path' in user_dict.keys():
                permission_type = 'repo'
                g_path = user_dict['project_path'].replace(
                    '/admin/projects/', '')
            else:
                permission_type = 'group'
                g_path = user_dict['group_path'].replace('/admin/groups/', '')
            permission = user_dict['permission']
            # print(username, permission_type, g_path, permission)
            if permission_type == 'repo':
                for p_id, p_data in projects_attributes.items():
                    if p_data['path_with_namespace'] == g_path:
                        if p_id not in output.keys():
                            output[p_id] = dict()
                        if permission not in output[p_id].keys():
                            output[p_id][permission] = list()
                        if username not in output[p_id][permission]:
                            output[p_id][permission].append(username)
            if permission_type == 'group':
                for p_id, p_data in projects_attributes.items():
                    if p_data['path_with_namespace'].find(g_path) == 0:
                        if p_id not in output.keys():
                            output[p_id] = dict()
                        if permission not in output[p_id].keys():
                            output[p_id][permission] = list()
                        if username not in output[p_id][permission]:
                            output[p_id][permission].append(username)
                for g_id, g_data in groups_attributes.items():
                    if g_data['full_path'] == g_path:
                        # print(g_data.keys())
                        # print(g_data['projects'][0])
                        # print('--------------------------')
                        for share_p in g_data['shared_projects']:
                            # print(share_p,'!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                            share_p_id = share_p['id']
                            tmp_permission = 'Owner'
                            for i in share_p['shared_with_groups']:
                                if i['group_id'] == g_data['id']:
                                    if i['group_access_level'] == 40:
                                        tmp_permission = 'Maintainer'
                                    if i['group_access_level'] == 30:
                                        tmp_permission = 'Developer'
                                    if i['group_access_level'] == 20:
                                        tmp_permission = 'Reporter'
                                    if i['group_access_level'] == 10:
                                        tmp_permission = 'Guest'
                            if share_p_id not in output.keys():
                                output[share_p_id] = dict()
                            if tmp_permission not in output[share_p_id].keys():
                                output[share_p_id][tmp_permission] = list()
                            if username not in \
                                    output[share_p_id][tmp_permission]:
                                output[share_p_id][tmp_permission].append(
                                    username)
                        for group_p in g_data['projects']:
                            group_p_id = group_p['id']
                            if group_p_id not in output.keys():
                                output[group_p_id] = dict()
                            if permission not in output[group_p_id].keys():
                                output[group_p_id][permission] = list()
                            if username not in output[group_p_id][permission]:
                                output[group_p_id][permission].append(username)
        # print(output)
        project_user_permission_file = \
            self.raw_data_path + 'project_user_permission.pkl'
        self.save_pkl(project_user_permission_file, output)

    def save_pkl(self, file_name, data):
        # print(time.ctime(), 'to be write', file_name)
        f_obj = open(file_name, 'wb')
        pickle.dump(data, f_obj)
        f_obj.close()

    def read_pkl(self, file_name):
        f_obj = open(file_name, 'rb')
        return pickle.load(f_obj)

    def get_jira_data(self, jira_id):
        proj = jira_id.strip().split("-")[0]
        issue_pkl = self.jira_issue_path + 'issue/' + proj + '.pkl'
        jira_issue = dict()
        if proj != '' and os.path.exists(issue_pkl):
            jira_issue = self.read_pkl(issue_pkl)
        if jira_id in jira_issue.keys():
            jira_type = jira_issue[jira_id]['fields']['issuetype']['name']
            fixVersions = jira_issue[jira_id]['fields']['fixVersions']
            proj_name = jira_issue[jira_id]['fields']['project']['name']
            jira_key = jira_issue[jira_id]['fields']['project']['key']
            component_json_list = jira_issue[jira_id]['fields']['components']
            component_list = [item['name'] for item in component_json_list]
            if fixVersions:
                fixVersions = [fix['name'].strip() for fix in fixVersions][0]
            else:
                fixVersions = ''
            return jira_key, proj_name, jira_type, fixVersions, component_list
        return '', '', '', '', []

    def get_jira_raw_data(self):
        # proj = jira_id.strip().split("-")[0]
        project_pkl = self.jira_issue_path + 'jira_project.pkl'
        projects_attributes = self.read_pkl(project_pkl)
        for project_key in projects_attributes.keys():
            issue_raw = dict()
            issue_pkl = self.jira_issue_path + 'issue/' + project_key + '.pkl'
            jira_issue = self.read_pkl(issue_pkl)
            for jira_id in jira_issue.keys():
                issue_type = jira_issue[jira_id]['fields']['issuetype']['name']
                status = jira_issue[jira_id]['fields']['status']['name']
                fix_versions = jira_issue[jira_id]['fields']['fixVersions']
                proj_name = jira_issue[jira_id]['fields']['project']['name']
                jira_key = jira_issue[jira_id]['fields']['project']['key']
                component_json_list = jira_issue[jira_id]['fields'][
                    'components']
                component_list = [item['name'] for item in component_json_list]
                if fix_versions:
                    fix_versions = \
                        [fix['name'].strip() for fix in fix_versions][0]
                else:
                    fix_versions = ''
                print('jira_id' + '->' + jira_id)
                print('jira_key' + '->' + jira_key)
                print('status' + '->' + status)
                print('proj_name' + '->' + proj_name)
                print('issue_type' + '->' + issue_type)
                print('fix_versions' + '->' + str(fix_versions))
                print('component_list' + '->' + str(component_list))
                try:
                    jira_in_db = models.Jira.objects.filter(jira_id=jira_id)
                    if jira_in_db:
                        jira_in_db[0].jira_id = jira_id
                        jira_in_db[0].jira_key = jira_key
                        jira_in_db[0].status = status
                        jira_in_db[0].proj_name = proj_name
                        jira_in_db[0].issue_type = issue_type
                        jira_in_db[0].fix_versions = json.dumps(
                            fix_versions, ensure_ascii=False)
                        jira_in_db[0].component_list = json.dumps(
                            component_list, ensure_ascii=False)
                        jira_in_db[0].save()
                    else:
                        newJira = models.Jira(
                            jira_id=jira_id,
                            jira_key=jira_key,
                            status=status,
                            proj_name=proj_name,
                            issue_type=issue_type,
                            fix_versions=json.dumps(
                                fix_versions, ensure_ascii=False),
                            component_list=json.dumps(
                                component_list, ensure_ascii=False),
                        )
                        newJira.save()
                except Exception as e:
                    print("插入数据失败:", str(e))
                else:
                    # 如果是插入数据， 一定要提交数据， 不然数据库中找不到要插入的数据;
                    print("插入数据成功;")

    def get_ph_raw_data(self):
        commit_list = models.Commit.objects.filter(submitter_month='2022-06')
        print(len(commit_list))
        for commit in commit_list:
            if commit.cr_ph == '[]':
                continue
            ph_id = re.findall("\\d+", commit.cr_ph)
            print(ph_id[0])
            # if ph_id[0] != '164690':
            #     continue
            ph_in_db = models.Ph.objects.filter(ph_id=ph_id[0])
            if ph_in_db:
                continue
            self.gen_ph_data_ids(ph_id[0])

    def get_time_slot(self, stamp_start, stamp_end):
        date_start = datetime.datetime.fromtimestamp(float(stamp_start))
        date_end = datetime.datetime.fromtimestamp(float(stamp_end))
        gap = (date_end - date_start).days * 24 + (
            date_end - date_start).seconds / 3600
        return int(gap)

    def get_localtime(self, time_t):
        x = time.localtime(time_t)
        localtime = time.strftime('%Y-%m-%d %H:%M:%S', x)
        return localtime

    def update_code_review(self, id, user, comments, create_time, accept_time):
        print('start to update code review')
        duration = self.get_time_slot(create_time, accept_time)
        create_time = self.get_localtime(create_time)
        accept_time = self.get_localtime(accept_time)
        # print(user)
        # print(duration)
        print(comments)
        comments_mum = len(comments)
        try:
            cr_in_db = models.CodeReview.objects.filter(ph_id=id,
                                                        reviewer=user)
            if cr_in_db:
                cr_in_db[0].start_time = create_time
                cr_in_db[0].accept_time = accept_time
                cr_in_db[0].duration = duration
                cr_in_db[0].comments_mum = comments_mum
                # cr_in_db[0].comments = json.dumps(
                #     comments)
                cr_in_db[0].save()
            else:
                newcr = models.CodeReview(
                    ph_id=id,
                    reviewer=user,
                    start_time=create_time,
                    accept_time=accept_time,
                    duration=duration,
                    comments_mum=comments_mum,
                    # comments=json.dumps(
                    #     comments, ensure_ascii=False),
                )
                newcr.save()
        except Exception as e:
            print("插入数据失败:", str(e))
        else:
            # 如果是插入数据， 一定要提交数据， 不然数据库中找不到要插入的数据;
            print("插入数据成功;")

    def gen_ph_data_ids(self, ph_id):
        ph_info = PH.get_ph_info(ph_id)
        for id, ph_data in ph_info.items():
            # print(ph_data)
            reviewer = list()
            comments_mum = 0
            if ph_data['accepter']:
                reviewer = list(ph_data['accepter'].keys())
                for user in reviewer:
                    comments = ''
                    if user in ph_data['comments'].keys():
                        print(user)
                        comments = ph_data['comments'][user]
                    self.update_code_review(
                        id, user, comments,
                        ph_data['create_time'],
                        ph_data['accepter'][user])
            for user, user_comment in ph_data['comments'].items():
                comments_mum += len(user_comment)
            comments = ph_data['comments']
            # print(comments)
            lint_passed = ph_data['lint_passed']
            ph_id = id
            close_time = None
            status = ''
            review_duration = 0
            create_time = self.get_localtime(ph_data['create_time'])
            if 'close_time' in ph_data.keys():
                close_time = self.get_localtime(ph_data['close_time'])
                status = 'Closed'
            if ph_data['comments']:
                review_duration = int(ph_data['review_duration'])

            print(reviewer)
            print(review_duration)
            print('start to update ph')
            try:
                ph_in_db = models.Ph.objects.filter(ph_id=ph_id)
                if ph_in_db:
                    ph_in_db[0].reviewer = json.dumps(
                        reviewer)
                    ph_in_db[0].open_time = create_time
                    ph_in_db[0].close_time = close_time
                    ph_in_db[0].status = status
                    ph_in_db[0].review_duration = review_duration
                    ph_in_db[0].lint_status = lint_passed
                    ph_in_db[0].comments_mum = comments_mum
                    # ph_in_db[0].comments = json.dumps(
                    #     comments)
                    ph_in_db[0].save()
                else:
                    newph = models.Ph(
                        ph_id=ph_id,
                        reviewer=json.dumps(reviewer, ensure_ascii=False),
                        open_time=create_time,
                        close_time=close_time,
                        status=status,
                        review_duration=review_duration,
                        lint_status=lint_passed,
                        comments_mum=comments_mum,
                        # comments=json.dumps(
                        #     comments),
                    )
                    newph.save()
            except Exception as e:
                print("插入数据失败:", str(e))
            else:
                # 如果是插入数据， 一定要提交数据， 不然数据库中找不到要插入的数据;
                print("插入数据成功;")

    def update_repo_approver(self):
        no_apporver_num = 0
        groups_attributes = self.read_pkl(
            self.raw_data_path + 'groups_attributes.pkl')
        for group_id, group_data in groups_attributes.items():
            para_item = dict()
            para_item['type'] = 'group'
            para_item['id'] = group_id
            para_item['parent_id'] = group_data['parent_id']
            self.update_repo_group_in_approver(para_item)

        projects_attributes = self.read_pkl(
            self.raw_data_path + 'public_projects_attributes.pkl')

        for project_id, project_data in projects_attributes.items():
            # if not project_id == 8189:
            #     continue
            para_item = dict()
            para_item['type'] = 'repo'
            para_item['id'] = project_id
            para_item['subgroup_id'] = project_data['namespace']['id']
            self.update_repo_group_in_approver(para_item)

        print("no_apporver_num:" + str(no_apporver_num))

    def update_repo_group_in_approver(self, para_item: dict):
        if para_item['type'] == 'repo':
            repos = models.Repo.objects.filter(repo_id=para_item['id'])
            repo_approver = models.RepoApprover.objects.filter(
                repo_id=repos[0])
            if not repo_approver:
                print(repos[0].repo_id, repos[0].web_url)
                group_approver = models.RepoApprover.objects.filter(
                    group_id__group_id=para_item['subgroup_id'])
                if group_approver:
                    for ga in group_approver:
                        print(
                            "sub groups approver:" + str(ga.approver))
                        models.RepoApprover.objects.update_or_create(
                            defaults={'approver': ga.approver,
                                      'approver_feishu': ga.approver_feishu,
                                      'web_url': repos[0].web_url,
                                      'auto_created': True},
                            repo=repos[0],
                            branch=ga.branch)
                        print('repo:' + str(
                            repos[0].repo_id) + ",branch:" + str(
                            ga.branch) + ' inserted')
                else:
                    print("No found sub groups approver:" + str(
                        repos[0].web_url))
            else:
                if not repo_approver[0].web_url == repos[0].web_url:
                    print('Update Url: from: ' +
                          repo_approver[0].web_url + ' to: ' +
                          repos[0].web_url)
                    repo_approver[0].web_url = repos[0].web_url
                    repo_approver[0].save()

        if para_item['type'] == 'group':
            groups = models.Group.objects.filter(group_id=para_item['id'])
            group_approver = models.RepoApprover.objects.filter(
                group_id=groups[0])
            if not group_approver:
                print(groups[0].group_id, groups[0].web_url)
                print("parent groups:" + str(para_item['parent_id']))
                group_approver = models.RepoApprover.objects.filter(
                    group_id__group_id=para_item['parent_id'])
                if group_approver:
                    for ga in group_approver:
                        print(
                            "parent groups approver:" + str(ga.approver))
                        models.RepoApprover.objects.update_or_create(
                            defaults={'approver': ga.approver,
                                      'approver_feishu': ga.approver_feishu,
                                      'web_url': groups[0].web_url,
                                      'auto_created': True},
                            group=groups[0],
                            branch=ga.branch)
                        print('group:' + str(
                            groups[0].group_id) + ",branch:" + str(
                            ga.branch) + ' inserted')
                else:
                    print("No found parent groups approver:" + str(
                        groups[0].web_url))
            else:
                if not group_approver[0].web_url == groups[0].web_url:
                    print('Update Url: from: ' +
                          group_approver[0].web_url + ' to: ' +
                          groups[0].web_url)
                    group_approver[0].web_url = groups[0].web_url
                    group_approver[0].save()

    @staticmethod
    def json_encode(data):
        if isinstance(data, str):
            return data
        return json.dumps(data, ensure_ascii=False)


def run():
    get_data = GetData()
    get_data.init_folder()
    # get_data.get_jira_raw_data()
    get_data.get_groups()
    get_data.get_projects()
    get_data.get_personal_public_projects()
    get_data.update_repo_approver()
    # get_data.get_project_raw()
    # get_data.get_users()
    # get_data.get_permissions()
    # get_data.parse_permissions()
    # get_data.get_commits()
    # get_data.get_ph_raw_data()

    print('end')
