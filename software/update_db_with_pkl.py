# coding:utf-8

import os
import sys
import re
import json
import time
import datetime
import subprocess
import requests
import pickle
import gitlab

from gitlab_app import models
from gitlab_app import PH


class SaveWithPkl(object):

    def __init__(self):
        self.ph_reg = r"Differential Revision: https://cr.test.com/D(\d+)"
        self.raw_data_path = '/opt/gitlab_report/raw_data2/'
        self.raw_repo_path = '/opt/gitlab_report/raw_data2/repo/'
        self.jira_issue_path = '/opt/gitlab_report/jira_data/'
        self.jira_reg = r"([A-Z][A-Z0-9_]+-[1-9][0-9]*)"
        path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gitlab_cfg = os.path.join(path, 'python-gitlab.cfg')
        self.gl = gitlab.Gitlab.from_config('trigger', [gitlab_cfg])
        self.gl.auth()
        self.ph_api_token = ''
        self.ph_api_url = 'https://cr.test.com/'

    @staticmethod
    def read_pkl(file_name):
        if not os.path.isfile(file_name):
            print(file_name, 'file not found')
            return dict()
        f_obj = open(file_name, 'rb')
        try:
            return pickle.load(f_obj)
        except:
            return dict()

    def read_jira(self):
        jira_attr = self.read_pkl(self.jira_issue_path + 'jira_project.pkl')
        for jira_pro in jira_attr.keys():
            self.get_jira_project_data(jira_pro)

    def get_ph_commits(self, revision_id):
        data = dict()
        commit_list = list()
        data['api.token'] = self.ph_api_token
        data['ids[0]'] = revision_id
        # print(data)
        try:
            differential_query = requests.post(
                self.ph_api_url + '/api/differential.query', data=data).json()
            for commit_data in differential_query['result'][0]['hashes']:
                if commit_data[0] == 'gtcm':
                    if not commit_data[1]:
                        continue
                    commit_list.append(commit_data[1])
            # print(commit_list)
        except Exception as e:
            print("PH commit error:" + str(e))
        return commit_list

    def read_project(self):
        repos = os.listdir(self.raw_repo_path)
        # repos = [8189]
        for repo in repos:
            full_path = self.raw_repo_path + str(repo)
            if os.path.isfile(full_path):
                continue
            branch_pkl_path = full_path + '/branches_attributes.pkl'
            commit_branch_map = full_path + '/commit_branch_map.pkl'
            commit_pkl_path = full_path + '/commit_attributes.pkl'
            event_pkl_path = full_path + '/events_attributes.pkl'
            issues_pkl_path = full_path + '/issues_attributes.pkl'
            members_pkl_path = full_path + '/members_attributes.pkl'
            merge_pkl_path = full_path + '/mrs_attributes.pkl'
            commit_attr = self.read_pkl(commit_pkl_path)
            self.parse_commit(
                repo, commit_attr, self.read_pkl(commit_branch_map))
            self.bind_merge_ph(repo, commit_attr)
            # self.handle_lint(repo, commit_attr, skip_commit_map)
            self.parse_branch(repo, self.read_pkl(branch_pkl_path))
            # self.handle_mr(repo, self.read_pkl(merge_pkl_path))

        return 'SUCCESS'

    def parse_branch(self, project_id, attr: dict):
        events = list()
        events_file_path = self.raw_data_path + '/repo/' + str(
            project_id) + '/events_attributes.pkl'
        if os.path.exists(events_file_path):
            events = self.read_pkl(events_file_path)
        for attributes in attr.values():
            try:

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
                        # author_username = event['author_username']
                repo_in_db = models.Repo.objects.filter(repo_id=project_id)
                branch_in_db = models.Branch.objects.filter(
                    repo=repo_in_db[0], branch_name=attributes['name'])
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

    def parse_repo(self, attr: dict):
        members = self.parse_project_member(attr['id'])
        item = {
            'repo_id': attr['id'],
            'name': attr['name'],
            'apply_dept': attr['name_with_namespace'],
            'web_url': attr['web_url'],
            'create_date': attr['created_at'].split('T')[0],
            'project_last_activity_at': attr['last_activity_at'].split('T')[0],
            'project_name': attr['name'],
            'maintainer': self.json_encode(members.get('Maintainer', list())),
            'developer': self.json_encode(members.get('Developer', list())),
            'reporter': self.json_encode(members.get('Reporter', list())),
            'guest': self.json_encode(members.get('Guest', list())),
            'owner': self.json_encode(members.get('Owner', list())),
            'archived': attr['archived'],
        }
        repo_in_db = models.Repo.objects.update_or_create(item,
                                                          repo_id=attr['id'])

    def parse_member(self, members):
        member_item = dict()
        for member in members:
            attr = member.attributes
            tmp_permission = 'Owner'
            if attr['access_level'] == 40:
                tmp_permission = 'Maintainer'
            if attr['access_level'] == 30:
                tmp_permission = 'Developer'
            if attr['access_level'] == 20:
                tmp_permission = 'Reporter'
            if attr['access_level'] == 10:
                tmp_permission = 'Guest'
            if not member_item.get(tmp_permission):
                member_item[tmp_permission] = list()
            member_item[tmp_permission].append(attr['username'])
        return member_item

    def parse_project_member(self, project_id):
        try:
            members = self.gl.projects.get(
                project_id, retry_transient_errors=True).members_all.list(
                all=True, retry_transient_errors=True)
            members_dict = self.parse_member(members)
        except:
            members_dict = dict()
        return members_dict

    def parse_group_member(self, group_id):
        group_path = self.raw_data_path + 'group/'
        members = self.read_pkl(
            group_path + str(group_id) + '/' + 'members_attributes.pkl')
        members_dict = self.parse_member(members)
        return members_dict

    def bind_merge_ph(self, repo, attr: dict):
        db_commits = models.Commit.objects.filter(repo__repo_id=repo)
        db_commit_hash_dict = dict()
        for item in db_commits:
            db_commit_hash_dict[item.commit_hash] = item
        for commit in attr.values():
            try:
                commit_detail = commit['commit_info']
                commit_message = commit_detail.split('\n')
                if len(commit_message) > 1 and commit_message[1].find(
                        'Merge:') == 0:
                    ph_case_info = re.findall(self.ph_reg, commit_detail)
                    if ph_case_info:
                        commits = self.get_ph_commits(ph_case_info[0])
                        for commit_hash in commits:
                            if commit_hash in db_commit_hash_dict.keys() and \
                                    db_commit_hash_dict[
                                        commit_hash].cr_ph == '[]':
                                print("PH Merge for:" + commit_hash)
                                db_commit_hash_dict[
                                    commit_hash].cr_ph = ph_case_info
                                db_commit_hash_dict[
                                    commit_hash].is_merge_map_ph = True
                                db_commit_hash_dict[commit_hash].save()
            except Exception as e:
                print("Ph Map error:" + str(e))

    def parse_commit(self, repo, attr: dict, commit_branch_map):
        repo_obj = None
        skip_commit_map = dict()
        repo_in_db = models.Repo.objects.filter(repo_id=repo)
        if repo_in_db:
            repo_obj = repo_in_db[0]
        db_commits = models.Commit.objects.filter(repo__repo_id=repo)
        db_commit_hash_list = [item.commit_hash for item in db_commits]
        for commit in attr.values():
            commit_detail = commit['commit_info']
            commit_id = commit['commit_id']
            if not commit_detail:
                continue
            if commit_id in db_commit_hash_list:
                continue

            commit_info = self.parse_commit_detail(commit_id, commit_detail)
            commit_file_info = list()
            if 'commit_file_info' in commit.keys():
                commit_file_info = self.parse_commit_file_detail(
                    commit_id,
                    commit['commit_file_info']
                )
            if not commit_info:
                continue

            merge_info = [commit['merge_info'].get('id')] if commit[
                'merge_info'] else []
            code_review_status = 'no'
            if commit_info['cr_ph']:
                code_review_status = 'ph'
            elif merge_info:
                code_review_status = 'mr'
            author = None
            component_list = list()
            author_in_sql = models.People.objects.filter(
                user_id=commit_info['author'])
            if author_in_sql:
                author = author_in_sql[0]

            jira_key = jira_project_name = jira_type = fix_versions = ''
            if commit_info.get('jira_ids'):
                jira_data = self.get_jira_data(commit_info['jira_ids'][0])
                jira_key = jira_data['jira_key']
                jira_project_name = jira_data['proj_name']
                jira_type = jira_data['jira_type']
                fix_versions = jira_data['fix_versions']
                component_list = jira_data['component_list']

            try:
                item = {
                    "commit_hash": commit_info['commit_hash'],
                    "author": author,
                    "author_date": commit_info['author_date'],
                    "submitter": commit_info['submitter'],
                    "submitter_date": commit_info['submitter_date'],
                    "submitter_week": commit_info['submitter_week'],
                    "submitter_month": commit_info['submitter_month'],
                    "files": commit_info['files'],
                    "additions": commit_info['additions'],
                    "deletions": commit_info['deletions'],
                    "cr_ph": commit_info['cr_ph'],
                    "cr_id_skip": commit_info['cr_id_skip'],
                    "is_3rd_skip": commit_info['3rd_skip'],
                    "no_3rd_skip": commit_info['no_3rd_skip'],
                    "file_list": self.json_encode(commit_file_info),
                    "jira_ids": self.json_encode(commit_info['jira_ids']),
                    "jira_type": jira_type,
                    "fix_version": fix_versions,
                    "jira_key": jira_key,
                    "component_list": self.json_encode(component_list),
                    "jira_project_name": jira_project_name,
                    "repo": repo_obj,
                    'cr_mr': self.json_encode(merge_info),
                    'code_review_status': code_review_status,
                }
                commit_store, ifnew = models.Commit.objects.get_or_create(
                    item, commit_hash=commit_info['commit_hash'], repo=repo_obj
                )

            except Exception as e:
                print('Insert data error: ', commit_info, e)
        if repo_obj:
            commit_in_db = models.Commit.objects.filter(
                repo_id=repo_obj.id).order_by('-id')
            branches_in_db = models.Branch.objects.filter(
                repo_id=repo_obj.id)
            branch_map = dict()
            for b in branches_in_db:
                branch_map[b.branch_name] = b.id
            for c in commit_in_db:
                try:
                    if c.branches:
                        c.branches.clear()
                    else:
                        print("无绑定分支：" + str(c.commit_hash))
                    if c.commit_hash in commit_branch_map.keys():
                        for commit_hash in list(
                                commit_branch_map[c.commit_hash]):
                            # print(commit_hash)
                            branch_id = branch_map.get(commit_hash)
                            if branch_id:
                                c.branches.add(branch_id)

                    c.save()
                    # print('添加分支信息成功: ')
                except Exception as e:
                    print('添加分支信息失败: ', str(e))
        return skip_commit_map

    def parse_commit_file_detail(self, commit_id, commit_file_raw):
        return_value = list()
        lines = list(filter(None, commit_file_raw.split('\n')))
        # print(lines)
        for line in lines:
            file_tmp = dict()
            va = line.split('\t')
            # print(va)
            file_tmp['addtions'] = va[0]
            file_tmp['deletions'] = va[1]
            file_tmp['file'] = va[2]
            return_value.append(file_tmp)
        return return_value


    def parse_commit_detail(self, commit_id, commit_message_raw):
        tmp_dict = dict()
        commit_message = commit_message_raw.split('\n')
        if commit_message[1].find('Merge:') == 0:
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
        # print(commit_message)
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
        tmp_dict['submitter_month'] = submitter_data[0:7]
        tmp_dict['submitter_week'] = datetime.datetime.strptime(
            submitter_data, '%Y-%m-%d').strftime(
            '%Y-%W')
        return tmp_dict

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

    def get_jira_data(self, jira_id):

        project = jira_id.strip().split("-")[0]

        iss_path = self.jira_issue_path
        issue_pkl = iss_path + 'issue/' + project + '.pkl'

        status = jira_key = proj_name = jira_type = fix_versions = ''
        component_list = list()
        if not os.path.isfile(issue_pkl):
            return {
                'jira_key': jira_key,
                'proj_name': proj_name,
                'jira_type': jira_type,
                'fix_versions': fix_versions,
                'component_list': component_list,
                'status': status
            }
        jira_issue = self.read_pkl(issue_pkl)
        if jira_id in jira_issue.keys():
            jira_type = jira_issue[jira_id]['fields']['issuetype']['name']
            fix_versions = jira_issue[jira_id]['fields']['fixVersions']
            proj_name = jira_issue[jira_id]['fields']['project']['name']
            jira_key = jira_issue[jira_id]['fields']['project']['key']
            component_json_list = \
                jira_issue[jira_id]['fields'].get('components', [])
            status = jira_issue[jira_id]['fields']['status']['name']
            component_list = [item['name'] for item in component_json_list]
            if fix_versions:
                fix_versions = [fix['name'].strip() for fix in fix_versions][0]
            else:
                fix_versions = ''
        return {
            'jira_key': jira_key,
            'proj_name': proj_name,
            'jira_type': jira_type,
            'fix_versions': fix_versions,
            'component_list': component_list,
            'status': status
        }

    def get_jira_project_data(self, jira_project):

        iss_path = self.jira_issue_path
        issue_pkl = iss_path + 'issue/' + jira_project + '.pkl'
        if not os.path.isfile(issue_pkl):
            return

        jira_issue = self.read_pkl(issue_pkl)

        for jira_id, jira in jira_issue.items():
            # if not jira_id == 'AR2020001-120':
            #     continue
            # print(jira)
            assignee = None
            creator = None
            reporter = None
            assignee_o = jira_issue[jira_id]['fields']['assignee']
            creator_o = jira_issue[jira_id]['fields']['creator']
            reporter_o = jira_issue[jira_id]['fields']['reporter']
            if assignee_o:
                assignee = assignee_o['name']
            if creator_o:
                creator = creator_o['name']
            if reporter_o:
                reporter = reporter_o['name']
            jira_type = jira_issue[jira_id]['fields']['issuetype']['name']
            create_time = jira_issue[jira_id]['fields']['created']
            resolution_time = jira_issue[jira_id]['fields']['resolutiondate']
            updated_time = jira_issue[jira_id]['fields']['updated']
            fix_versions = jira_issue[jira_id]['fields']['fixVersions']
            proj_name = jira_issue[jira_id]['fields']['project']['name']
            jira_key = jira_issue[jira_id]['fields']['project']['key']
            component_json_list = \
                jira_issue[jira_id]['fields'].get('components', [])
            priority = ''
            if 'priority' in jira_issue[jira_id]['fields'].keys():
                if jira_issue[jira_id]['fields']['priority'] \
                        and 'name' in \
                        jira_issue[jira_id]['fields']['priority'].keys():
                    priority = jira_issue[jira_id]['fields']['priority'][
                        'name']
            severity = ''
            if 'customfield_11221' in jira_issue[jira_id][
                'fields'].keys() and jira_issue[jira_id]['fields'][
                    'customfield_11221']:
                severity = \
                    jira_issue[jira_id]['fields']['customfield_11221'][
                        'value']
            status = jira_issue[jira_id]['fields']['status']['name']
            component_list = [item['name'] for item in component_json_list]
            if fix_versions:
                fix_versions = [fix['name'].strip() for fix in fix_versions][0]
            else:
                fix_versions = ''
            items = {
                'jira_key': jira_key,
                'create_time': create_time,
                'creator': creator,
                'reporter': reporter,
                'resolution_time': resolution_time,
                'assignee': assignee,
                'updated_time': updated_time,
                'proj_name': proj_name,
                'issue_type': jira_type,
                'fix_versions': fix_versions,
                'component_list': component_list,
                'priority': priority,
                'severity': severity,
                'status': status,
                'jira_id': jira_id,
            }
            try:
                self.save_jira(items)
            except Exception as e:
                print('err', e.args)

    @staticmethod
    def save_jira(data):
        models.Jira.objects.update_or_create(data, jira_id=data['jira_id'])

    @staticmethod
    def run_cmd(command):
        try:
            ret = subprocess.run(
                command, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            print('run cmd exception change to gpk ---- ', command)
            return False, ''
        if ret.returncode != 0:
            print("error:", command, ret.returncode, ret.stderr)
            return False, ''.join(map(chr, ret.stdout))
        return True, ''.join(map(chr, ret.stdout))

    def read_group(self):
        try:
            groups = self.gl.groups.list(all=True, retry_transient_errors=True)
        except:
            return "FAIL"
        for group in groups:
            self.parse_group(group.attributes)
        return 'SUCCESS'

    def parse_group(self, attr: dict):
        members = self.parse_group_member(attr['id'])
        repos = list()
        try:
            group_attr = self.gl.groups.get(attr['id']).attributes
        except:
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
            'web_url': attr['web_url'],
            'create_date': attr['created_at'].split('T')[0],
            # 'project_name': attr['name'],
            'maintainer': self.json_encode(members.get('Maintainer', list())),
            'developer': self.json_encode(members.get('Developer', list())),
            'reporter': self.json_encode(members.get('Reporter', list())),
            'guest': self.json_encode(members.get('Guest', list())),
            'owner': self.json_encode(members.get('Owner', list())),
        }
        try:
            group_in_db = models.Group.objects.update_or_create(
                item, group_id=attr['id'])
        except Exception as e:
            print('Insert group error: ', str(e))

    @staticmethod
    def json_encode(data):
        if isinstance(data, str):
            return data
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def handle_mr(repo_id, mr_list: list):
        if not mr_list:
            return
        if not isinstance(mr_list, list):
            return

        for mr in mr_list:
            if mr['data']['state'] != 'merged':
                continue
            try:
                mr_id = mr['data']['id']
                approve_list = set()
                comment_list = set()
                discussion = mr['discussion']
                author = mr['data']['author']
                merged_at = mr['data']['merged_at']
                if not merged_at:
                    merged_at = mr['data']['updated_at']
                merge_create = mr['data']['created_at']
                merge_close = mr['data']['created_at']
                merged_at_time = time.strptime(merged_at,
                                               "%Y-%m-%dT%H:%M:%S.%f+08:00")
                merged_at_timestamp = time.mktime(merged_at_time)
                mr_create_time = time.strptime(merge_create,
                                               "%Y-%m-%dT%H:%M:%S.%f+08:00")
                mr_create_timestamp = time.mktime(mr_create_time)
                mr_close_time = time.strptime(merge_close,
                                              "%Y-%m-%dT%H:%M:%S.%f+08:00")
                mr_close_timestamp = time.mktime(mr_close_time)
                for comment in discussion:
                    create_time = time.strptime(merged_at,
                                                "%Y-%m-%dT%H:%M:%S.%f+08:00")
                    create_time_timestamp = time.mktime(create_time)

                    if create_time_timestamp > merged_at_timestamp:
                        continue
                    if comment['body'].startswith('approved'):
                        approve_list.add(comment['author']['username'])
                    comment_list.add(comment['author']['username'])
                item = {
                    'mr_id': mr_id,
                    'auther': author,
                    'reviewers': json.dumps(list(comment_list)),
                    'approver': json.dumps(list(approve_list)),
                    'comments_mum': len(comment_list),
                    'merge_duration': int(merged_at_timestamp) - int(
                        mr_create_timestamp),
                    'status': mr['data']['state'],
                    'repo_id': repo_id,
                    'open_time': time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(mr_create_timestamp)),
                    'close_time': time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(mr_close_timestamp)),
                }
                models.Mr.objects.update_or_create(item, mr_id=mr_id,
                                                   repo_id=repo_id)
            except Exception as err:
                print(err)

    def handle_lint(self, repo, commit_list: dict, skip_commit_map: dict):
        for commit in commit_list.values():
            commit_id = commit['commit_id']
            if skip_commit_map.get(commit_id):
                continue
            commit_detail = commit['commit_info']
            if commit_detail == '':
                continue
            commit_message = commit_detail.split('\n')
            if commit_message[1].find('Merge:') == 0:
                continue
            # commit_id = commit['commit_id']
            cr_ph = re.findall(self.ph_reg, commit_detail)
            if len(cr_ph) == 0:
                continue

            cr_ph_str = ','.join(cr_ph)
            ph_id = re.findall("\\d+", cr_ph_str)
            ph_in_db = models.Ph.objects.filter(ph_id=ph_id[0])
            if ph_in_db:
                continue
            self.gen_ph_data_ids(ph_id[0])

    def gen_ph_data_ids(self, ph_id):
        ph_info = PH.get_ph_info(ph_id)
        for id, ph_data in ph_info.items():
            reviewer = list()
            comments_mum = 0
            if ph_data.get('accepter'):
                reviewer = list(ph_data['accepter'].keys())
                for user in reviewer:
                    comments = ''
                    if user in ph_data['comments'].keys():
                        # print(user)
                        comments = ph_data['comments'][user]
                    self.update_code_review(
                        id, user, comments,
                        ph_data['create_time'],
                        ph_data['accepter'][user])
            if not ph_data.get('ph_data', None):
                continue
            for user, user_comment in ph_data['comments'].items():
                comments_mum += len(user_comment)
            # comments = ph_data['comments']
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
                    )
                    newph.save()
            except Exception as e:
                print("插入数据失败:", str(e))
            else:
                # 如果是插入数据， 一定要提交数据， 不然数据库中找不到要插入的数据;
                print("插入数据成功;")

    def update_code_review(self, _id, user, comments, create_time,
                           accept_time):
        duration = self.get_time_slot(create_time, accept_time)
        create_time = self.get_localtime(create_time)
        accept_time = self.get_localtime(accept_time)
        comments_mum = len(comments)
        try:
            cr_in_db = models.CodeReview.objects.filter(ph_id=_id,
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
                    ph_id=_id,
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

    @staticmethod
    def get_time_slot(stamp_start, stamp_end):
        date_start = datetime.datetime.fromtimestamp(float(stamp_start))
        date_end = datetime.datetime.fromtimestamp(float(stamp_end))
        gap = (date_end - date_start).days * 24 + (
                date_end - date_start).seconds / 3600
        return int(gap)

    @staticmethod
    def get_localtime(time_t):
        x = time.localtime(time_t)
        localtime = time.strftime('%Y-%m-%d %H:%M:%S', x)
        return localtime


def run():
    s = SaveWithPkl()
    s.read_project()
    # s.read_group()
