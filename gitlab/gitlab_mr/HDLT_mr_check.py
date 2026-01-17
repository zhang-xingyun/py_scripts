# -*- coding: utf-8 -*-
import os
import sys
import gitlab
import os
import logging
import re
import mechanize
from http import cookiejar


class MrCheck:
    def __init__(self, repo_id, mr_id):
        self.repo_id = repo_id
        self.mr_id = mr_id
        self.gl = gitlab.Gitlab.from_config('trigger', ['python-gitlab.cfg'])
        # self.patch_limit = 1024 * 1024
        # self.changed_count = 100
        self.patch_limit = 1
        self.changed_count = 1

    def get_mr_msg(self):
        project = self.gl.projects.get(self.repo_id)
        mr_msg = project.mergerequests.get(self.mr_id)
        title = mr_msg.title
        description = mr_msg.description
        changes_count = mr_msg.changes_count
        web_url = mr_msg.web_url
        squash_status = mr_msg.squash
        force_remove_source_branch_status = mr_msg.force_remove_source_branch
        notes = mr_msg.notes
        author_id = mr_msg.author['id']
        return title, description, changes_count, web_url, squash_status, force_remove_source_branch_status, notes, author_id

    def init_br(self):
        br = mechanize.Browser()
        cj = cookiejar.CookieJar()
        br.set_cookiejar(cj)
        br.set_handle_equiv(True)
        br.set_handle_gzip(True)
        br.set_handle_redirect(True)
        br.set_handle_referer(True)
        br.set_handle_robots(False)
        br.set_handle_refresh(
            mechanize._http.HTTPRefreshProcessor(), max_time=1)
        br.set_debug_http(False)
        br.addheaders = [
            ('User-agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:15.0) Gecko/20100101 Firefox/15.0.1')]
        response = br.open('http://gitlab.test.com')
        br.select_form(nr=0)
        br.form['username'] = 'robot'
        br.form['password'] = ''
        br.submit()
        return br

    def patch_and_count_check_status(self, description):
        if re.search(r'\[x\] 粒度适中', description):
            logging.debug(" patch and count need check")
            return True
        logging.debug("patch and count do not need check")
        return False

    def check_mr_patch(self, web_url, description):
        if not self.patch_and_count_check_status(description):
            return True
        br = self.init_br()
        user_url = web_url + '.patch'
        response = br.open(user_url, timeout=60)
        data = response.get_data()
        data_str = str(data, encoding="utf-8")
        size = sys.getsizeof(data_str)
        if size > self.patch_limit:
            logging.error('Mr patch size: {}, Exceeds the set value {}'.format(
                size, self.patch_limit))
            return False
        return True

    def check_changes_count(self, changes_count, description):
        if not self.patch_and_count_check_status(description):
            return True
        if int(changes_count) > self.changed_count:
            logging.error("Changed files count: {}, Exceeds the set value {}".format(
                changes_count, self.changed_count))
            return False
        return True

    def jira_check(self, title):
        if re.match(r'.+([a-zA-Z][a-zA-Z0-9_]+-[1-9][0-9]*).+', title):
            return True

    def commit_header_check(self, title):
        if re.match(r'^(feat|fix|docs|style|refactor|perf|test|chore)(.*): \[.*\] [A-Z].+', title):
            return True

    def check_title(self, title):
        # if not self.jira_check(title):
        #     logging.error('NO Jira Issue Key in Title: ' + title)
        if not self.commit_header_check(title):
            logging.error('Check  title failed: ' + title)
            return False
        return True

    def check_description(self, description):
        result = True
        if not re.search(r'Details', description):
            logging.error("Check description failed,No Details Field")
            result = False
        if not re.search(r'设计/重构文档', description):
            logging.error("Check description failed,No 设计/重构文档 Field")
            result = False
        if not re.search(r'jira/issue', description):
            logging.error("check description failed,No jira/issue Field")
            result = False
        if not re.search(r'关注人', description):
            logging.error("Check description failed,No 关注人 Field")
            result = False
        # if not re.search(r'优先级', description):
        #     logging.error("Check description failed,No 优先级 Field")
        #     result = False
        matches_target = re.finditer(r'\[ \]|\[x\]|\[X\]', description)
        matches_target_int = len(list(matches_target))
        if matches_target_int == 0:
            logging.error("Checklist is none")
            result = False
        matches = re.finditer(r'\[x\]|\[X\]', description)
        matches_int = len(list(matches))
        if matches_int < 4:
            logging.error(
                "Checklist matches: {0}, at least 4.".format(matches_int))
            result = False
        return result

    def check_squash_status(self, squash_status):
        if not squash_status:
            logging.error(
                "Squash commits status: {}, need True".format(squash_status))
            return False
        return True

    def check_force_remove_source_branch_status(self, force_remove_source_branch_status):
        if not force_remove_source_branch_status:
            logging.error("Force remove source branch status: {}, need True".format(
                force_remove_source_branch_status))
            return False
        return True

    def check_LGTM(self, notes, author_id):
        lgtm_list = list()
        for i in notes.list():
            if re.search(r'LGTM', i.body):
                lgtm_list.append(i.author['id'])
        lgtm = list(set(lgtm_list))
        if author_id in lgtm:
            lgtm.remove(author_id)
        if len(lgtm) < 3:
            logging.error("LGTM count is {}, less 3".format(len(lgtm)))
            return False
        return True

    def check_discussion(self, notes, author_id):
        result = True
        for i in notes.list():
            if i.type and i.resolvable == True and i.resolved == True:
                if author_id == i.resolved_by['id']:
                    logging.error("{} is resolved by {} self".format(
                        i.body, i.resolved_by['name']))
                    result = False
        return result

    def run_check(self):
        result = True
        title, description, changes_count, web_url, squash_status, force_remove_source_branch_status, notes, author_id = self.get_mr_msg()
        if not self.check_title(title):
            result = False
        if not self.check_description(description):
            result = False
        # if not self.check_changes_count(changes_count, description):
        #     result = False
        # if not self.check_mr_patch(web_url, description):
        #     result = False
        # if not self.check_squash_status(squash_status):
        #     result = False
        # if not self.check_force_remove_source_branch_status(force_remove_source_branch_status):
        #     result = False
        # if not self.check_LGTM(notes, author_id):
        #     result = False
        if not self.check_discussion(notes, author_id):
            result = False
        return result


def main():
    repo_id = os.getenv('gitlabMergeRequestTargetProjectId')
    mr_id = os.getenv('gitlabMergeRequestIid')
    obj = MrCheck(repo_id, mr_id)
    result = obj.run_check()
    if not result:
        return 1
    return 0


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(asctime)s: %(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S', level=logging.WARNING)
    sys.exit(main())
