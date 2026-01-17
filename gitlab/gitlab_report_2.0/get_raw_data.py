limport gitlab
import pickle
import os
import time
import argparse
import textwrap
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


class GetData():
    def __init__(self, cr_report_pw, get_commit, get_code_type):
        self.gl = None
        self.cr_report_pw = cr_report_pw
        self.get_commit = get_commit
        self.get_code_type = get_code_type
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
        self.get_single_project_thread = 4
        self.git_cmd_thread = 120
        self.ph_reg = r"Differential Revision: https://cr.test.com/D(\d+)"
        self.jira_reg = r"([A-Z][A-Z0-9_]+-[1-9][0-9]*)"
        # self.jira_data = dict()
        # self.jira_ignore = list()
        # self.jira_conn = JIRA('https://jira.test.com:8443',
        #                         auth=('', ''))

    def init_folder(self):
        self.gl = gitlab.Gitlab.from_config('trigger', 'python-gitlab.cfg')
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
            group = self.gl.groups.get(
                group_single.attributes['id'], retry_transient_errors=True)
            self.groups_attributes[group.attributes['id']] = group.attributes
        gourp_file = self.raw_data_path + 'groups_attributes.pkl'
        self.save_pkl(gourp_file, self.groups_attributes)
        print('total group number is %d' % len(self.groups_attributes))

    def get_projects(self):
        print(time.ctime(), 'get_projects')
        projects = self.gl.projects.list(all=True, retry_transient_errors=True)
        for project in projects:
            self.projects_attributes[project.attributes['id']
                                     ] = project.attributes
        project_file = self.raw_data_path + 'projects_attributes.pkl'
        self.save_pkl(project_file, self.projects_attributes)
        print('total project number is %d' % len(self.projects_attributes))

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

    def get_branch(self, project_url, project_id, repo_folder):
        print(time.ctime(), 'get_branches', project_id)
        try:
            project = self.gl.projects.get(
                project_id, retry_transient_errors=True)
        except Exception as e:
            print('error branch project exception', project_url, e)
            return
        try:
            branches = project.branches.list(
                all=True, retry_transient_errors=True)
        except Exception as e:
            print('error branch branch exception', project_url, e)
            return
        branches_attributes = dict()
        for branch in branches:
            branches_attributes[branch.name] = branch.attributes
        self.save_pkl(repo_folder + 'branches_attributes.pkl',
                      branches_attributes)

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
            self.get_branch(projects[project_id]
                            ['web_url'], project_id, repo_folder)
            self.get_events(projects[project_id]
                            ['web_url'], project_id, repo_folder)
            self.get_mrs(projects[project_id]['web_url'],
                         project_id, repo_folder)
            self.get_issues(projects[project_id]
                            ['web_url'], project_id, repo_folder)
            # self.get_members(projects[project_id]['web_url'],
            #                  project_id, repo_folder)

    def get_project_raw(self):
        projects = self.read_pkl(
            self.raw_data_path + 'public_projects_attributes.pkl')
        project_keys = list(projects.keys())
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

    def run_thread(self, commit_id_list, commit_list,
                   single_commits, ssh_url_to_repo):
        while True:
            try:
                commit_id = commit_id_list.pop()
                if commit_id in single_commits.keys():
                    # print('commit exist')
                    commit_list.append(single_commits[commit_id])
                    # print(len(commit_list))
                    continue
            except:
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
            if self.get_code_type:
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
            '[')+1:commit_message_raw.find(']')].split(' ')
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

    def commit_parse_thread(self, commit_id_list, single_commits,
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
                commit_id_list, data[i], single_commits, ssh_url_to_repo))
            threads.append(tr)
        for i in threads:
            i.start()
        for i in threads:
            i.join()
        for i, j in data.items():
            # print(i,len(j))
            output.extend(j)
        return output

    def get_commit_list(self, single_commits, ssh_url_to_repo):
        print(time.ctime(), 'get_commit_list')
        commit_list = list()
        ret, commit_id_list = self.runcmd(
            'git --no-pager log --pretty=format:"%H"')
        if ret:
            commit_id_list = commit_id_list.split('\n')
            commit_list = self.commit_parse_thread(
                commit_id_list, single_commits, ssh_url_to_repo)
        else:
            print(commit_id_list, 'error', ssh_url_to_repo)
        return commit_list

    def get_commits(self):
        # print(project_id, 'get_commits', projects[project_id]['web_url'])
        # repo_folder = self.raw_data_repo_path + str(project_id) + '/'
        projects_attributes = self.read_pkl(
            self.raw_data_path + 'public_projects_attributes.pkl')
        for project_id, project_data in projects_attributes.items():
            # print(project_id)
            # debug
            # if project_id != 7972:
            #   continue
            # debug end
            start_time = int(time.time())
            repo_folder = self.raw_data_repo_path + str(project_id) + '/'
            if not os.path.exists(repo_folder + 'branches_attributes.pkl'):
                print('no branch data', project_data['web_url'])
                continue
            print(project_id, project_data)
            branches_attributes = self.read_pkl(
                repo_folder + 'branches_attributes.pkl')
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
            for branch_name, branch in branches_attributes.items():
                # debug
                # if branch_name != 'Release_TR51':
                #    continue
                # end
                print('branch name', branch_name)
                if branch_name == 'HEAD':
                    continue
                git_checkout_cmd = 'git checkout -b %s origin/%s' % (
                    branch_name, branch_name)
                ret, output = self.runcmd(git_checkout_cmd)
                if not ret:
                    print(git_checkout_cmd, 'error', ssh_url_to_repo)
                    print(output)
                    self.runcmd('git checkout ' + branch_name)
                ret, count_info = self.runcmd('loc')
                if ret:
                    counts[branch_name] = self.parse_loc_count(count_info)
                else:
                    print('loc', 'error', ssh_url_to_repo)
                commits[branch_name] = self.get_commit_list(
                    single_commits, ssh_url_to_repo)
            os.chdir(current_folder)
            print(os.getcwd())
            shutil.rmtree(tmp_repo)
            self.save_pkl(repo_folder + 'counts.pkl', counts)
            self.save_pkl(repo_folder + 'commits.pkl', commits)
            self.save_pkl(repo_folder + 'single_commits.pkl', single_commits)
            end_time = int(time.time())
            run_time = int((end_time - start_time)/60)
            print('run_time', str(run_time), ssh_url_to_repo)
        # self.save_pkl(self.raw_data_path + 'jira.pkl', self.jira_data)
        # self.jira_ignore = list(set(self.jira_ignore))
        # print(self.jira_ignore)

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
        response = br.open('http://gitlab.test.com/users/sign_in#login-pane')
        #
        br.select_form(nr=0)
        #
        br.form['username'] = 'cr_report'
        if 'CR_REPORT_PW' in os.environ:
            br.form['password'] = os.environ.get('CR_REPORT_PW')
            print("CR_REPORT_PW env:" + str(os.environ.get('CR_REPORT_PW')))
        elif self.cr_report_pw:
            br.form['password'] = self.cr_report_pw
            print("CR_REPORT_PW in par :" + str(self.cr_report_pw))
        else:
            br.form['password'] = ""
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


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''\
                         input the pw of cr_report and whether get commit
                         '''))
    parser.add_argument('-cr_pw', '--cr_report_pw',
                        metavar=str(), required=False,
                        help="input the pw of cr_report",
                        type=str)
    parser.add_argument('--get_commit',
                        action='store_true', default=False,
                        help="Whether you need to get commits information")
    parser.add_argument('--get_code_type',
                        action='store_true', default=False,
                        help="Whether you need to get code type")
    args = parser.parse_args()

    get_data = GetData(args.cr_report_pw, args.get_commit, args.get_code_type)
    get_data.init_folder()
    get_data.get_groups()
    get_data.get_projects()
    get_data.get_personal_public_projects()
    get_data.get_project_raw()
    get_data.get_users()
    get_data.get_permissions()
    get_data.parse_permissions()
    if get_data.get_commit:
        get_data.get_commits()
    print('end')


if __name__ == "__main__":
    main()
