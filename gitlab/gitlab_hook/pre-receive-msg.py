#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import re
import json
import logging
import itertools
import subprocess
import urllib
import urllib2
import codecs

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

# defined the reviewed hash as global var, due to arc generate new commit/merge point when "arc land"
g_reviewed_hash_list = []
g_reg = r"https://cr.test.com/D(\d+)"


def get_revision(revision_id):
    """
    Phabricator request
    """
    ph_url = "https://cr.test.com/api/differential.query"
    ph_token = ""
    values = {'ids[0]': revision_id, 'api.token': ph_token}
    data = urllib.urlencode(values)
    req = urllib2.Request(ph_url, data)
    response = urllib2.urlopen(req)
    ret = ""
    if response.getcode() != 200:
        logging.error("Error occurred while processing request to PH")
        return ret
    try:
        ret = json.loads(response.read())['result'][0]
    except:
        logging.error("Error occurred when parsing PH response")
    return ret


def verify_revision(revision_lst, commits):
    """
    Verify if every commit in the differential is accepted.
    """
    accepted = True

    # loop check akk revision_id,
    for one_revision_id in revision_lst:
        logging.debug("query revision from ph:{0}".format(one_revision_id))
        revision_detail = get_revision(one_revision_id)
        logging.debug("revision detail: %s" % revision_detail)
        if not revision_detail:
            logging.info("find revision ID: {0}".format(one_revision_id))
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


def check_branch_format(refname):
    logging.info('create new branch: {0}'.format(refname))
    # Check if the branch name is lower case characters (ASCII only), '-', '_', "/" or numbers
    if (not re.search(r'^refs/heads/[-a-z0-9_/]+$', refname)):
        logging.warning('\nWarning: ' + refname +
                        ' is not good! \nbranch should only contain lower-case alpha-numeric characters, "-", "_" or "/" .')


def check_tag_format(refname):
    if (not re.search(r'^refs/tags/[-A-Z0-9_/.]+$', refname)):
        logging.warning('\nWarning: ' + refname +
                        ' is not good! \nTAG should only contain upper-case alpha-numeric characters, "-", "_" or "/" .')
        # todo: if need enforce this rule, set result to block failed case
        # pre_check_pass = -1


def main():
    # set check result defalut as pass
    pre_check_pass = 0
    zero_commit = "0000000000000000000000000000000000000000"
    is_accepted = False

    # get all refs group from stdin.
    all_refs = sys.stdin.readlines()
    # process one refs group
    one_ref = ""
    for one_ref in all_refs:
        # init variable,every loop to record commit and revision.
        oldrev, newrev, refname = one_ref.strip().split(" ")
        logging.info("check ref: {0} commits: {1}..{2}".format(
            refname, oldrev, newrev))

        # check branch bypass
        logging.debug("check branch bypass ...")
        check_branch_bypass(refname)

        # 0.create branch
        if (oldrev == zero_commit and re.search(r'^refs/heads/', refname)):
            logging.debug("check branch create...")
            check_branch_format(refname)
            # check  if there have commit in this new branch
            # to prevent push to branch with un-reviewed commit.
            pre_check_pass = check_new_refs_commit(
                newrev, refname, pre_check_pass)
            # should not exit after check failed, check all return all result.
            continue

        # 1. delete branch
        if (newrev == zero_commit and re.search(r'^refs/heads/', refname)):
            logging.debug("check branch delete...")
            # TODO: check the delete permission?
            # pre_check_pass = -1
            pass
            continue

        # 2. create tag
        if (oldrev == zero_commit and re.search(r'^refs/tags/', refname)):
            logging.debug("check tag create...")
        # Check if the tag name is lower upper characters (ASCII only),
        #  '-', '_', "/" or numbers
            check_tag_format(refname)
            pre_check_pass = check_new_refs_commit(
                newrev, refname, pre_check_pass)
            continue

        # 3. delete tag
        if (newrev == zero_commit and re.search(r'^refs/tags/', refname)):
            logging.debug("check tag delete...")
            # TODO: check the delete permission?
            # pre_check_pass = -1
            pass
            continue

        # 4. others, push commits
        # check each commit in this refs group
        logging.debug("check commits ...")
        pre_check_pass = check_refs_commit(
            oldrev, newrev, refname, pre_check_pass)
    # check for next group: #refname, oldrev, newrev
    if pre_check_pass != 0:
        logging.error(msg)
        logging.debug("PH_HOOK: check fail. {0}".format(pre_check_pass))
    else:
        logging.debug("PH_HOOK: check pass. {0}".format(pre_check_pass))
    return pre_check_pass

def check_branch_bypass(refname):
    white_bypass_file = os.path.join(os.getcwd(),'custom_hooks','white_bypass.txt')
    black_bypass_file = os.path.join(os.getcwd(),'custom_hooks','black_bypass.txt')
    logging.debug(white_bypass_file)
    logging.debug(black_bypass_file)
    logging.debug(refname)
    white_bypass_file_status = os.access(white_bypass_file, os.R_OK)
    black_bypass_file_status = os.access(black_bypass_file, os.R_OK)
    if white_bypass_file_status and black_bypass_file_status:
        logging.debug('both white_bypass.txt and black_bypass.txt')
        return
    if (not white_bypass_file_status) and (not black_bypass_file_status):
        logging.debug('both no white_bypass.txt and no black_bypass.txt')
        return
    if black_bypass_file_status:
        black_bypass_data = map(lambda x:'/'.join(['refs/heads',x.strip()]),filter(None,open(black_bypass_file,'r').read().split('\n')))
        logging.debug(black_bypass_data)
        if refname not in black_bypass_data:
            sys.exit(0)

    if white_bypass_file_status:
        white_bypass_data = map(lambda x:'/'.join(['refs/heads',x.strip()]),filter(None,open(white_bypass_file,'r').read().split('\n')))
        logging.debug(white_bypass_data)
        if refname in white_bypass_data:
            sys.exit(0)

def get_branch_and_group(file):
    f = codecs.open(file, mode='r', encoding='utf-8')
    line = f.readline()
    dict1 = {}
    while line:
        a = line.split()
        dict1[a[0]] = a[1]
        line = f.readline()
    f.close()
    return dict1

def check_refs_commit(oldrev, newrev, refname, pre_check_pass):
    all_hashes_lst = []
    revision_id_lst = []
    commit_list = []
    check_result = pre_check_pass

    separator = "----****----"
    # todo, catch call exception
    proc = subprocess.Popen(["git",
                             "log",
                             "--format=%H%n%ci%n%s%b%n" + separator,
                             oldrev + ".." + newrev],
                            stdout=subprocess.PIPE)
    message = proc.stdout.read()
    commit_list = message.strip().split(separator)[:-1]
    # commit msg check

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
            tmp_lst = re.findall(g_reg, content)
            logging.debug("match: {0} ".format(tmp_lst))
            if len(tmp_lst) > 0:
                revision_id_lst.extend(tmp_lst)
                # this is arc generated commit.
                # (arc land history.immutable: true, generate merge commit)
                g_reviewed_hash_list.append(hash)
        except:
            pass
            logging.debug("Warning: No revision ID for commit %s" % hash)
        all_hashes_lst.append(hash)

    check_commit_msg_file = os.path.join(os.getcwd(),'custom_hooks','check_commit_msg.txt')
    if os.access(check_commit_msg_file, os.R_OK):
        dict1 = get_branch_and_group(check_commit_msg_file)
        branch_list = dict1.keys()
        list1 = refname.split('/')
        branch = list1[len(list1)-1]
        if branch in branch_list:
            if not check_commit_msg(commit_list):
                return -1
            if not check_ph_group_accept(revision_id_lst,dict1):
                return -1
    logging.debug("7")
    # check there have Phabricator revision id or not ?
    if not len(revision_id_lst) > 0:
        logging.error(" No PH revision ID for this push")
        logging.error(" commit list: {0}".format(all_hashes_lst))
        # not need check revision
        check_result = -1
    else:
        logging.debug("8")
        logging.debug("revision_id_lst is= {0}".format(revision_id_lst))
        logging.debug("commit hash list: {0}".format(all_hashes_lst))
        is_accepted = verify_revision(revision_id_lst, all_hashes_lst)
        # if have any not accepted commit, change pass to false
        if not is_accepted:
            check_result = -1

    logging.debug("check_refs_commit return {0}".format(check_result))
    return check_result

def check_commit_msg(commit_list):
    check_commit_msg_skip = "skip"
    for i,commit in enumerate(commit_list):
        logging.debug("c1")
        # todo: if some one commit none-stand commit message, then below check will fail.
        line_list = commit.strip().split("\n")
        content = line_list[2].split('Signed-off-by:')[0].replace('Summary:','')
        logging.debug(content)
        if i == 0:
            if len(check_commit_msg_skip) > 0:
                if content.find(check_commit_msg_skip) > 0:
                    return True
            if not re.match(r'.+([a-zA-Z][a-zA-Z0-9_]+-[1-9][0-9]*).+', content):
                logging.error('NO Jira Issue Key in PH Case Title: ' + content)
                return False
        if not re.match(r'(feat|fix|docs|style|refactor|perf|test|chore)(\[)(\w+)(\]):( ).+(?<![\.|\;|\:|\,])$', content):
            logging.error('Commit Message Rule Check Fail: ' + content)
            logging.error('http://wiki.test.com/x/yKvrC Sample (feat|fix|docs|style|refactor|perf|test|chore)[xxxx]: xxxxxxxxxx')
            return False
    return True

# check ph group accept result  revision_id_lst=['79574']
def check_ph_group_accept(revision_id_lst,dict1):
    flag = True
    for revision_id in revision_id_lst:
        check_result = check_ph_group_accept_result(revision_id,dict1)
        if check_result == False:
            flag = False
    return flag

# call ph-API,get revsion_id group review result
def check_ph_group_accept_result(revision_id,dict1):
    API_TOKEN = ''
    differential_diff_search = 'https://cr.test.com/api/differential.query'
    user_query = 'https://cr.test.com/api/user.query'
    project_query = 'https://cr.test.com/api/project.query'

    def get_ph_data(url,data):
        data = urllib.urlencode(data)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        ret = json.loads(response.read())
        return ret

    def get_username(userid):
        data = dict()
        data['api.token'] = API_TOKEN
        data['phids[0]'] = userid
        result = get_ph_data(user_query, data)['result'][0]
        username = result['userName'] + '@test.com'
        return username

    def get_reviewers(prj_id):
        output = list()
        data = dict()
        data['api.token'] = API_TOKEN
        data['ids[0]'] = prj_id
        try:
            phid_prj = get_ph_data(project_query, data)['result']['data'].keys()
        except Exception as e:
            logging.error("Get phid_prj failed,check project id.")
            return
        data['phids[0]'] = phid_prj[0]
        result = get_ph_data(project_query, data)['result']['data'][phid_prj[0]]['members']
        for j in result:
            output.append(get_username(j))
        output = list(set(output))
        return output


    def process_transaction(phid):
        data = dict()
        data['api.token'] = API_TOKEN
        data['objectIdentifier'] = phid
        data['limit'] = 99999
        result = get_ph_data('https://cr.test.com/api/transaction.search', data)['result']['data']
        accepters = list()
        for i in result:
            if i['type'] == 'accept':
                accepters.append(get_username(i['authorPHID']))
            accepters = list(set(accepters))
        return accepters

    data = get_revision(revision_id)
    branch = data['branch']
    logging.info("check repo branch is: %s" % branch)
    prj_id = dict1[branch]
    logging.info("check group id is: %s" % prj_id)
    phid = data["phid"]
    logging.info("phid is : %s" % phid)
    author = get_username(data['authorPHID'])
    logging.debug("author is : %s" % author)
    prj_members = get_reviewers(prj_id)
    if not prj_members:
        logging.error("Project id is error,id: %s" % prj_id)
        return False
    if author in prj_members:
        prj_members.remove(author)
    logging.info("Need to be reviewed by these Group id: %s ,People: %s" % (prj_id,','.join(prj_members)))
    accepters = process_transaction(phid)
    logging.info("These are the people who have accepted: %s " % ','.join(accepters))
    need_accept = list(set(prj_members) - set(accepters))
    if len(need_accept) > 0:
        logging.error("Need this person to accept: %s" % ','.join(need_accept))
        return False
    return True

def check_new_refs_commit(newrev, refname, pre_check_pass):
    # check  if there have commit in this new branch, to prevent push
    # to branch with un-reviewed commit.
    all_hashes_lst = []
    revision_id_lst = []
    commit_list = []
    check_result = pre_check_pass

    # git rev-list $newrev --not --branches=*
    proc = subprocess.Popen(
        ["git", "rev-list", newrev, "--not", "--branches=*", "--tags=*"], stdout=subprocess.PIPE)
    commit_list = proc.stdout.readlines()
    logging.debug("new commit lst\n%s" % commit_list)
    # check each commit message
    logging.debug("commit number:{0}".format(len(commit_list)))
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
                    g_reviewed_hash_list.append(hash)
            except:
                pass
                logging.debug("Warning: No revision ID for commit %s" % hash)
            all_hashes_lst.append(hash)
        # check there have Phabricator revision id or not ?
        if not len(revision_id_lst) > 0:
            logging.error(
                "No PH revision ID for this push {0}".format(refname))
            logging.error("Error: commit list: {0}".format(all_hashes_lst))
            # not need check revision
            check_result = -1
        else:
            logging.debug("0.1")
            logging.debug("revision_id_lst is= {0}".format(revision_id_lst))
            logging.debug("commit hash list: {0}".format(all_hashes_lst))
            is_accepted = verify_revision(revision_id_lst, all_hashes_lst)
            # if have any not accepted commit, change pass to false
            if not is_accepted:
                check_result = -1
    logging.debug("check_new_refs_commit return {0}".format(check_result))
    return check_result


if __name__ == '__main__':
    #logging.basicConfig(format='%(levelname)s:%(asctime)s : %(lineno)d :%(message)s',
    #                    datefmt='%Y/%m/%d %H:%M:%S', level=logging.DEBUG)
    logging.basicConfig(format='%(levelname)s:%(asctime)s: %(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S', level=logging.WARNING)
    sys.exit(main())
