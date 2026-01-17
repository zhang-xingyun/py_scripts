#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import sys
import json
import yaml
import logging 
import traceback
import itertools
import subprocess
import urllib
import urllib2
from functools import wraps

logger = logging.getLogger()

def logit(func):
    @wraps(func)
    def log(*args,**kwargs):
        try:
            return func(*args,**kwargs)
        except Exception as e:
            logger.error("%s is error,details: %s}" % (func.__name__, traceback.format_exc()))
    return log

def check_config(configpath):
    project = os.getenv('GL_REPOSITORY')
    project_id = project.split('-')[1]
    logger.info("project_id: {}".format(project_id))
    filename = str(project_id) + '.yaml'
    for dirpath, dirnames, filenames in os.walk(configpath):
        for file in filenames:
            fullpath = os.path.join(dirpath, file)
            path_list = fullpath.split('/')
            if filename in path_list:
                logger.info("Found config: {}".format(fullpath))
                return fullpath

#TODO: read config file, get check point
class getConfig:
    def __init__(self, filename):
        self.file = filename
    
    @logit
    def read_config_file(self):
        check_file = os.path.join(os.getcwd(),self.file)
        f = open(check_file)
        data = f.read()
        yaml_reader = yaml.load(data, Loader=yaml.FullLoader)
        return yaml_reader
    
    @logit
    def get_branch_check_point(self):
        config_dict = dict()
        check_point_dict = dict()
        config_content = self.read_config_file()['BRANCH']
        for key in config_content.keys():
            if config_content[key]:
                config_dict[key] = config_content[key]
        if not config_dict:
            return 
        check_point_dict['BRANCH'] = config_dict
        return check_point_dict
    
    @logit
    def get_tag_check_point(self):
        config_dict = dict()
        check_point_dict = dict()
        config_content = self.read_config_file()['TAG']
        for key in config_content.keys():
            if config_content[key]:
                config_dict[key] = config_content[key]
        if not config_dict:
            return 
        check_point_dict['TAG'] = config_dict
        return check_point_dict
    
    @logit
    def get_commit_check_point(self, refname):
        list1 = refname.split('/')
        branch = list1[len(list1)-1]
        config_content = self.read_config_file()['COMMIT']
        config_ref_dict = dict()
        if branch in config_content.keys():
            config_ref_dict[branch] = config_content[branch]
        if 'global' in config_content.keys():
            config_ref_dict['global'] = config_content['global']
        if len(config_ref_dict.keys()) > 1:
            global_dict = dict()
            refname_dict = dict()
            global_dict = config_ref_dict['global']
            logging.debug("global_dict: {}".format(global_dict))
            refname_dict = config_ref_dict[branch]
            logging.debug("refname_dict: {}".format(refname_dict))
            data = dict()
            for k in global_dict.keys():
                if k in refname_dict.keys():
                    data[k] = refname_dict[k]
                else:
                    data[k] = global_dict[k]
        else:
            data = config_ref_dict['global']
        return data


#TODO: BRANCH class
class checkBranchTag:
    def __init__(self, oldrev, newrev, refname, check_point):
        self.refname = refname
        self.check_point = check_point
        self.newrev = newrev
        self.oldrev = oldrev
        self.g_reviewed_hash_list = list()

    def check_branch_format(self, regex):
        logger.info('create new branch: {0}'.format(self.refname))
        list1 = self.refname.split('/')
        name = list1[len(list1)-1]
        if (not re.search(regex, self.refname)):
            logging.error('Error: ' + self.refname +
                            ' is not good! \nBranch should only contain lower-case alpha-numeric characters, "-", "_" or "/" .'
                            + '\nExample: {}'.format(name.lower()))
            return -1

    def check_branch_ph_check(self):
        # check  if there have commit in this new branch, to prevent push
        # to branch with un-reviewed commit.
        all_hashes_lst = []
        revision_id_lst = []
        commit_list = []
        check_result = 0
        g_reg = r"https://cr.test.com/D(\d+)"
        # git rev-list $newrev --not --branches=*
        proc = subprocess.Popen(
            ["git", "rev-list", self.newrev, "--not", "--branches=*", "--tags=*"], stdout=subprocess.PIPE)
        commit_list = proc.stdout.readlines()
        logging.debug("new commit lst\n%s" % commit_list)
        # check each commit message
        logging.debug("commit number:{0}".format(len(commit_list)))
        obj = commitCheck(self.oldrev, self.newrev, self.refname, self.check_point)
        if len(commit_list) > 0:
            for commit in commit_list:
                # check each commit in this refs group
                cmd_lst = ["git", "log", "-1",
                        "--format=%H%n%ci%n%s%b%n", commit.strip()]
                logging.debug(cmd_lst)
                proc = subprocess.Popen(cmd_lst, stdout=subprocess.PIPE)
                message = proc.stdout.read()
                logging.debug(message)
                # todo: if some one commit none-stand commit message, then below check will fail?!
                line_list = message.strip().split("\n")
                hash = line_list[0]
                body = line_list[1]
                content = " ".join(line_list[2:])
                try:
                    # user using git push, may cause there have more than on revision ID.
                    logging.debug("content: {0}".format(content))
                    tmp_lst = re.findall(g_reg, content)
                    logging.debug("match: {0} ".format(tmp_lst))
                    if len(tmp_lst) > 0:
                        revision_id_lst.extend(tmp_lst)
                        self.g_reviewed_hash_list.append(hash)
                except:
                    pass
                    logging.debug("Warning: No revision ID for commit %s" % hash)
                all_hashes_lst.append(hash)
            # check there have Phabricator revision id or not ?
            if not len(revision_id_lst) > 0:
                logging.error(
                    "No PH revision ID for this push {0}".format(self.refname))
                logging.error("Error: commit list: {0}".format(all_hashes_lst))
                # not need check revision
                check_result = -1
            else:
                logging.debug("0.1")
                logging.debug("revision_id_lst is= {0}".format(revision_id_lst))
                logging.debug("commit hash list: {0}".format(all_hashes_lst))
                is_accepted = obj.verify_revision(revision_id_lst, all_hashes_lst, self.g_reviewed_hash_list)
                # if have any not accepted commit, change pass to false
                if not is_accepted:
                    check_result = -1
        logging.debug("check_new_refs_commit return {0}".format(check_result))
        return check_result

    def check_tag_format(self, regex):
        logger.info('create new tag: {0}'.format(self.refname))
        list1 = self.refname.split('/')
        name = list1[len(list1)-1]
        if (not re.search(regex, self.refname)):
            logging.error('Error: ' + self.refname +
                            ' is not good! \nTAG should only contain upper-case alpha-numeric characters, "-", "_" or "/" .'
                            + '\nExample: {}'.format(name.upper()))
            return -1

    def check_tag_ph_check(self):
        return 1

    def run_check(self):
        if 'TAG' in self.check_point.keys():
            tag_point = self.check_point['TAG']
            for key in tag_point.keys():
                if tag_point[key]:
                    if key == 'name_check':
                        check_result = self.check_tag_format(tag_point['name_check'])
                        if check_result == -1:
                            return check_result
                    elif key == 'ph_check':
                        check_result = self.check_tag_ph_check()
                        if check_result == -1:
                            return check_result
        elif 'BRANCH' in self.check_point.keys():
            branch_point = self.check_point['BRANCH']
            for key in branch_point.keys():
                if branch_point[key]:
                    if key == 'name_check':
                        check_result = self.check_branch_format(branch_point[key])
                        if check_result == -1:
                            return check_result
                    elif key == 'ph_check':
                        check_result = self.check_branch_ph_check()
                        if check_result == -1:
                            return check_result
        else:
            logging.debug("Nothing need check")


#TODO: COMMIT class
class commitCheck:

    def __init__(self, oldrev, newrev, refname, check_point):
        self.oldrev = oldrev
        self.newrev = newrev
        self.refname = refname
        self.check_point = check_point
        self.g_reviewed_hash_list = list()
        self.g_reg = r"https://cr.test.com/D(\d+)"
        self.ph_token = ''
        self.differential_diff_search = 'https://cr.test.com/api/differential.query'
        self.user_query = 'https://cr.test.com/api/user.query'
        self.project_query = 'https://cr.test.com/api/project.query'
        self.transaction_search = 'https://cr.test.com/api/transaction.search'
        self.diff_path_query = 'https://cr.test.com/api/differential.getcommitpaths'
        self.query_diffs = 'https://cr.test.com/api/differential.querydiffs'

    def get_revision(self, revision_id):
        """
        Phabricator request
        """
        values = {'ids[0]': revision_id, 'api.token': self.ph_token}
        data = urllib.urlencode(values)
        req = urllib2.Request(self.differential_diff_search, data)
        response = urllib2.urlopen(req)
        ret = ""
        if response.getcode() != 200:
            logging.error("Error occurred while processing request to PH")
            return ret
        try:
            ret = json.loads(response.read())['result'][0]
        except Exception as e:
            logging.error(e)
            logging.error("Error occurred when parsing PH response")
        return ret


    def verify_revision(self, revision_lst, commits, g_reviewed_hash_list):
        """
        Verify if every commit in the differential is accepted.
        """
        accepted = True

        # loop check akk revision_id,
        for one_revision_id in revision_lst:
            logging.debug("query revision from ph:{0}".format(one_revision_id))
            revision_detail = self.get_revision(one_revision_id)
            logging.debug("revision detail: %s" % revision_detail)
            if not revision_detail:
                logger.info("find revision ID: {0}".format(one_revision_id))
                continue
            logging.debug("--verify 1---")
            status = revision_detail['statusName']
            # the workflow, allow Accepted,Closed before push, due to some user close very quickly.
            # if not correct status: Accepted or Closed
            if not (status == 'Accepted' or status == 'Closed'):
                logging.error("NONE ACCEPTED Revison %s , status is: %s" %
                            (one_revision_id, status))
                accepted = False
                continue
            logging.debug("--verify 2---")
            # if status ok, get this revisionID's commit hash
            hashes = list(itertools.chain(revision_detail['hashes']))
            for ctype, value in hashes:
                if (ctype == 'gtcm'):
                    g_reviewed_hash_list.append(value)

        logging.debug("--verify 3---")
        logging.debug("g_reviewed_hash_list:{0}".format(g_reviewed_hash_list))
        # after get all reviewed_hash_lst, check the commit all in here or not
        # if CR status ok, check commit:
        if accepted:
            logging.debug("verify commits: {0}".format(commits))
            for one_commit in commits:
                if not one_commit in g_reviewed_hash_list:
                    accepted = False
                    logging.error("Commit {0} Not reviewed !".format(one_commit))
                else:
                    pass
                    logging.debug(
                        "commit review check pass:{0}".format(one_commit))
        return accepted

    def get_commit_list(self):
        separator = "----****----"
        # todo, catch call exception
        proc = subprocess.Popen(["git",
                                "log",
                                "--format=%H%n%ci%n%s%b%n" + separator,
                                self.oldrev + ".." + self.newrev],
                                stdout=subprocess.PIPE)
        message = proc.stdout.read()
        commit_list = message.strip().split(separator)[:-1]
        logging.debug("commit_list: {0}".format(commit_list))
        return commit_list

    def get_revision_and_hash(self):
        all_hashes_lst = list()
        revision_id_lst = list()
        commit_list = self.get_commit_list()
        for commit in commit_list:
            logging.debug("6")
            # todo: if some one commit none-stand commit message, then below check will fail.
            line_list = commit.strip().split("\n")
            hash = line_list[0]
            body = line_list[1]
            logging.debug("hash: {0}".format(hash))
            logging.debug("body: {0}".format(body))
            content = " ".join(line_list[2:])
            try:
                # user using git push, may cause there have more than on revision ID.
                logging.debug("content: {0}".format(content))
                tmp_lst = re.findall(self.g_reg, content)
                logging.debug("match: {0} ".format(tmp_lst))
                if len(tmp_lst) > 0:
                    revision_id_lst.extend(tmp_lst)
                    self.g_reviewed_hash_list.append(hash)
            except:
                logging.debug("Warning: No revision ID for commit %s" % hash)
            all_hashes_lst.append(hash)
        logging.info('revison id: %s' % revision_id_lst)
        return revision_id_lst, all_hashes_lst

    def check_force_ac(self):
        revision_id_lst, all_hashes_lst = self.get_revision_and_hash()
        logging.debug("revision_id_lst: %s, all_hashes_lst: %s " % (revision_id_lst, all_hashes_lst))
        check_result = self.verify_revision(revision_id_lst, all_hashes_lst, self.g_reviewed_hash_list)
        if not check_result:
            logger.error("Force review accept check is failed! NONE ACCEPTED")
            return -1

    def commit_msg(self, commit_list, regex, rule):
        check_commit_msg_skip = "skip"
        for i,commit in enumerate(commit_list):
            line_list = commit.strip().split("\n")
            content = line_list[2].split('Signed-off-by:')[0].replace('Summary:','')
            logging.debug(content)
            # if i == 0:
            if len(check_commit_msg_skip) > 0:
                    if content.find(check_commit_msg_skip) > 0:
                        return True
            if not re.match(regex, content):
                logging.error('Commit Message Rule Check Fail: ' + content)
                logging.error('http://wiki.test.com/x/yKvrC Sample (feat|fix|docs|style|refactor|perf|test|chore)[xxxx]: xxxxxxxxxx')
                return False
            if not rule:
                break
        return True

    def check_commit_msg(self, regex, rule):
        commit_list = self.get_commit_list()
        logging.debug("check commit msg list: %s " % (commit_list))
        check_result = self.commit_msg(commit_list, regex, rule)
        if not check_result:
            logger.error("commit msg  check is failed!!!")
            return -1

    def jira_msg(self, commit_list, rule):
        check_commit_msg_skip = "skip"
        for i,commit in enumerate(commit_list):
            line_list = commit.strip().split("\n")
            content = line_list[2].split('Signed-off-by:')[0].replace('Summary:','')
            logging.debug(content)
            # if i == 0:
            if len(check_commit_msg_skip) > 0:
                if content.find(check_commit_msg_skip) > 0:
                    return True
            if not re.match(r'.+([a-zA-Z][a-zA-Z0-9_]+-[1-9][0-9]*).+', content):
                logging.error('NO Jira Issue Key in PH Case Title: ' + content)
                return False
            if not rule:
                break
        return True

    def check_jira_msg(self, rule):
        commit_list = self.get_commit_list()
        logging.debug("check commit msg list: %s " % (commit_list))
        check_result = self.jira_msg(commit_list, rule)
        if not check_result:
            logger.error("Jira ID msg  check is failed!!!")
            return -1

    def get_ph_data(self, url, data):
        data = urllib.urlencode(data)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        ret = json.loads(response.read())
        return ret

    def get_username(self, userid):
        data = dict()
        data['api.token'] = self.ph_token
        data['phids[0]'] = userid
        result = self.get_ph_data(self.user_query, data)['result'][0]
        username = result['userName'] + '@test.com'
        return username

    def get_prj_reviewers(self, prj_name):
        members = list()
        data = dict()
        data['api.token'] = self.ph_token
        data['names[0]'] = prj_name
        result = self.get_ph_data(self.project_query, data)['result']
        if result['data']:
            phid_prj = result['data'].keys()
            data['phids[0]'] = phid_prj[0]
            result = self.get_ph_data(self.project_query, data)['result']['data'][phid_prj[0]]['members']
            for j in result:
                members.append(self.get_username(j))
            members = list(set(members))
            return members
    
    def get_reviewers(self, name_list):
        data = dict()
        members = list()
        data['api.token'] = self.ph_token
        for name in name_list:
            name = name.strip()
            data['usernames[0]'] = name
            result = self.get_ph_data(self.user_query, data)['result']
            if result:
                members.append(name + '@test.com')
            else:
                group = self.get_prj_reviewers(name)
                if group:
                    members.extend(group)
        members = list(set(members))
        return members

    def process_transaction(self, phid):
        data = dict()
        data['api.token'] = self.ph_token
        data['objectIdentifier'] = phid
        data['limit'] = 99999
        result = self.get_ph_data(self.transaction_search, data)['result']['data']
        accepters = list()
        for i in result:
            if i['type'] == 'accept':
                accepters.append(self.get_username(i['authorPHID']))
            accepters = list(set(accepters))
        return accepters

    def ph_group_accept_result(self, revision_id, name_list, rule):
        data = self.get_revision(revision_id)
        phid = data["phid"]
        logging.debug("phid is : %s" % phid)
        author = self.get_username(data['authorPHID'])
        logging.debug("author is : %s" % author)
        review_members = self.get_reviewers(name_list)
        if not review_members:
            logging.error("name list is valid: %s" % name_list)
            return False
        if author in review_members:
            review_members.remove(author)
        logging.debug("Need to be reviewed by these people: %s" % ','.join(review_members))
        accepters = self.process_transaction(phid)
        logger.info("User have accepted: %s " % ','.join(accepters))
        need_accept = list(set(review_members) - set(accepters))
        if not rule:
            if len(need_accept) < len(review_members):
                logging.debug('Mandatory reviewer group has been approved')
                return True
            else:
                logging.error('At least one to review accept: %s' % ','.join(review_members))
                return False
        if len(need_accept) > 0:
            logging.error("Need user to accept: %s" % ','.join(need_accept))
            return False
        return True

    def check_force_people_accept(self, name_list, rule):
        flag = 0
        revision_id_lst, all_hashes_lst = self.get_revision_and_hash()
        for revision_id in revision_id_lst:
            check_result = self.ph_group_accept_result(revision_id, name_list, rule)
            if check_result == False:
                flag = -1
                logging.error("Force people accept check failed!")
        return flag

    def get_accepters(self,revision_id):
        data = self.get_revision(revision_id)
        phid = data["phid"]
        accepters = self.process_transaction(phid)
        # ac_num = len(accepters)
        return accepters

    def get_ph_author(self, revision_id):
        data = self.get_revision(revision_id)
        phid = data["phid"]
        logging.debug("phid is : %s" % phid)
        author = self.get_username(data['authorPHID'])
        return author

    def check_ac_num(self, ac_num):
        flag = 0
        revision_id_lst, all_hashes_lst = self.get_revision_and_hash()
        for revision_id in revision_id_lst:
            accepters = self.get_accepters(revision_id)
            if ac_num > len(accepters):
                flag = -1
                logger.error("ac num check failed, total need %s users accept, already %s users accept" % (ac_num, len(accepters)))
        return flag

    def get_diff_path(self, revision_id):
        data = dict()
        data['api.token'] = self.ph_token
        data['revision_id'] = revision_id
        result = self.get_ph_data(self.diff_path_query, data)['result']
        return result

    def get_diff_id(self, revision_id):
        data = dict()
        data['api.token'] = self.ph_token
        data['ids[0]'] = revision_id
        result = self.get_ph_data(self.differential_diff_search, data)['result'][0]
        diff_id = result['diffs'][0]
        return diff_id

    def get_file_rows(self, revision_id, file_path):
        data = dict()
        data['api.token'] = self.ph_token
        data['revisionIDs[0]'] = revision_id
        result = self.get_ph_data(self.query_diffs, data)
        diff_id = self.get_diff_id(revision_id)
        chanegs = result['result'][diff_id]['changes']
        rows = 0
        for change in chanegs:
            if change['currentPath'] == file_path:
                rows += int(change['addLines']) + int(change['delLines'])
        return rows

    def check_path(self, data):
        flag = 0
        revision_id_lst, all_hashes_lst = self.get_revision_and_hash()
        for revision_id in revision_id_lst:
            accepters = self.get_accepters(revision_id)
            author = self.get_ph_author(revision_id)
            file_path_list = self.get_diff_path(revision_id)
            logging.info('file_path_list : %s' % file_path_list)
            logging.info('accepters : %s' % accepters)
            diff_count = dict()
            alreay_check_list = list()
            for i in data:
                diff_count[i['check_path']] = dict()
                diff_count[i['check_path']]['count'] = 0
                diff_count[i['check_path']]['rows'] = 0
                for file_path in file_path_list:
                    if 'check_path' in i.keys() and i['check_path'] and re.match(i['check_path'], file_path):
                        if file_path not in alreay_check_list:
                            alreay_check_list.append(file_path)
                            logging.info('matching file path: %s, rule: %s' % (file_path, i['check_path']))
                            file_rows = self.get_file_rows(revision_id, file_path)
                            diff_count[i['check_path']]['count'] += 1
                            diff_count[i['check_path']]['rows'] += file_rows
                            #file_path_list.remove(file_path)
                # Remove unmatched data.
                if diff_count[i['check_path']]['count'] == 0:
                    del diff_count[i['check_path']]
            logging.info('count: %s' % diff_count)
            for key in diff_count.keys():
                for i in data:
                    if i['check_path'] == key:
                        for review_level in ['maintainers', 'approvers', 'supervisors']:
                            reviewers_limit = review_level + '_limit'
                            review_level_change_files_count = review_level + '_change_files_count'
                            review_level_change_rows = review_level + '_change_rows'
                            if review_level in i.keys() and i[review_level] and reviewers_limit in i.keys() and i[reviewers_limit] and i[reviewers_limit] > 0:
                                reviewers = i[review_level].split(',')
                                reviewers_list = self.get_reviewers(reviewers)
                                check = 0
                                if review_level_change_files_count in i.keys() and i[review_level_change_files_count] and diff_count[key]['count'] >= i[review_level_change_files_count]:
                                    check = 1
                                if review_level_change_rows in i.keys() and i[review_level_change_rows] and diff_count[key]['rows'] >= i[review_level_change_rows]:
                                    check = 1
                                # No configuration files count and rows, default run check.
                                if review_level_change_files_count not in i.keys() and review_level_change_rows not in i.keys():
                                    check = 1
                                if check == 1:
                                    already_accept = list(set(reviewers_list) & set(accepters))
                                    logging.info("%s already review: %s" % (review_level, already_accept))
                                    if author in reviewers_list:
                                        i[reviewers_limit] = i[reviewers_limit] - 1
                                    if len(already_accept) < i[reviewers_limit]:
                                        need_review = list(set(reviewers_list) - set(already_accept))
                                        need_num = i[reviewers_limit] - len(already_accept)
                                        logging.error('%s need reviewer: %s, at least %d of them are needed' % (review_level, need_review, need_num))
                                        flag = -1
        return flag

    def run_check(self):
        flag = 0
        data = self.check_point
        for key in data.keys():
            if data[key]:
                if key == 'jira_check':
                    check_result = self.check_jira_msg(data['jira_check_recurrence'])
                    if check_result == -1:
                        flag = -1
                elif key == 'commit_msg':
                    check_result = self.check_commit_msg(data[key], data['commit_msg_recurrence'])
                    if check_result == -1:
                        flag = -1
                elif key == 'ph_force_cr':
                    check_result = self.check_force_ac()
                    if check_result == -1:
                        flag = -1
                elif key == 'ph_force_people':
                    name_list = data[key].split(',')
                    check_result = self.check_force_people_accept(name_list, data['ph_force_people_all'])
                    if check_result == -1:
                        flag = -1
                elif key == 'ph_ac_number':
                    check_result = self.check_ac_num(data[key])
                    if check_result == -1:
                        flag = -1
                elif key == 'ph_check_by_path':
                    check_result = self.check_path(data[key])
                    if check_result == -1:
                        flag = -1
                else:
                    logging.debug('Nothing need check')
        return flag


def main():
    configpath = "/home/git/data/custom_hooks/config/push"
    check_config_file = check_config(configpath)
    if not check_config_file:
        logging.debug("No configuration needs to be check")
        return 0
    #check_config_file = os.path.join(os.getcwd(),'custom_hooks','config.yaml')
    if os.access(check_config_file, os.R_OK):
        config_obj = getConfig(check_config_file)
        branch_check_point = config_obj.get_branch_check_point()
        tag_check_point = config_obj.get_tag_check_point()
        zero_commit = "0000000000000000000000000000000000000000"
        all_refs = sys.stdin.readlines()
        for one_ref in all_refs:
            oldrev, newrev, refname = one_ref.strip().split(" ")
            logger.info("check ref: {} commits: {}..{}".format(
                refname, oldrev, newrev))
            commit_check_point = config_obj.get_commit_check_point(refname)
            if (oldrev == zero_commit and re.search(r'^refs/heads/', refname)):
                if branch_check_point:
                    logger.info("branch check point:{}".format(branch_check_point))
                    obj = checkBranchTag(oldrev, newrev, refname, branch_check_point)
                    check_result = obj.run_check()
                    return check_result
            elif (oldrev == zero_commit and re.search(r'^refs/tags/', refname)):
                if tag_check_point:
                    logger.info("tag check point: {}".format(tag_check_point))
                    obj = checkBranchTag(oldrev, newrev, refname, tag_check_point)
                    check_result = obj.run_check()
                    return check_result
            else:
                if commit_check_point:
                    logger.info("commit_check_point: %s" % commit_check_point)
                    check_obj = commitCheck(oldrev, newrev, refname, commit_check_point)
                    check_result = check_obj.run_check()
                    return check_result
    else:
        logging.debug("No configuration needs to be check")
if __name__ == '__main__':
    msg = r"""
+---------------------------------------------------------------+
|      * * * PUSH REJECTED BY EVIL DRAGON BUREAUCRATS * * *     |
+---------------------------------------------------------------+
             \
              \                    ^    /^
               \                  / \  // \
                \   |\___/|      /   \//  .\
                 \  /V  V  \__  /    //  | \ \           *----*
                   /     /  \/_/    //   |  \  \          \   |
                   @___@`    \/_   //    |   \   \         \/\ \
                  0/0/|       \/_ //     |    \    \         \  \
              0/0/0/0/|        \///      |     \     \       |  |
           0/0/0/0/0/_|_ /   (  //       |      \     _\     |  /
        0/0/0/0/0/0/`/,_ _ _/  ) ; -.    |    _ _\.-~       /   /
                    ,-}        _      *-.|.-~-.           .~    ~
  *     \__/         `/\      /                 ~-. _ .-~      /
   \____(Oo)            *.   }            {                   /
   (    (..)           .----~-.\        \-`                 .~
   //___\\\\  \ DENIED!  ///.----..<        \             _ -~
  //     \\\\                ///-._ _ _ _ _ _ _{^ - - - - ~

  Please make sure this change is Accepted in Phabricator before push."
  Reference: http://wiki.test.com/pages/viewpage.action?pageId=65647806"
"""
    logging.basicConfig(format='%(levelname)s:%(asctime)s : %(lineno)d :%(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S', level=logging.ERROR)
    result = main()
    if result == -1:
        logging.error(msg)
        sys.exit(-1)
    sys.exit(0)

