import json
import os
import time
import pickle
import re
import datetime
from gitlab_app import models
from gitlab_app import PH


class CRMR(object):

    def __init__(self):
        self.raw_repo_path = '/opt/gitlab_report/raw_data2/repo/'
        self.ph_reg = r"Differential Revision: https://cr.test.com/D(\d+)"

    @staticmethod
    def read_pkl(file_name):
        if not os.path.isfile(file_name):
            print(file_name, 'file not found')
            return dict()
        f_obj = open(file_name, 'rb')
        try:
            return pickle.load(f_obj)
        except Exception as e:
            print('read pkl error:' + str(e))
            return dict()

    def handle(self):
        repos = os.listdir(self.raw_repo_path)
        for repo in repos:
            full_path = self.raw_repo_path + repo
            if os.path.isfile(full_path):
                continue
            merge_pkl_path = full_path + '/mrs_attributes.pkl'
            commit_pkl_path = full_path + '/commit_attributes.pkl'
            # print(self.read_pkl(merge_pkl_path))
            self.handle_mr(repo, merge_pkl_path)
            self.handle_lint(repo, self.read_pkl(commit_pkl_path))

    def handle_mr(self, repo_id, merge_pkl_path):
        mr_list = self.read_pkl(merge_pkl_path)
        if not mr_list:
            return
        if not isinstance(mr_list, list):
            return

        for mr in mr_list:
            if mr['data']['state'] != 'merged':
                continue
            try:
                mr_id = mr['data']['id']
                approver = dict()
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
                user_comment_dic = dict()
                for comment in discussion:
                    create_time = time.strptime(merged_at,
                                                "%Y-%m-%dT%H:%M:%S.%f+08:00")
                    create_time_timestamp = time.mktime(create_time)

                    if create_time_timestamp > merged_at_timestamp:
                        continue
                    if comment['body'].startswith('approved'):
                        comment_create_time = time.strptime(
                            comment['created_at'],
                            "%Y-%m-%dT%H:%M:%S.%f+08:00")
                        comment_create_timestamp = time.mktime(
                            comment_create_time)
                        approver[comment['author'][
                            'username']] = comment_create_timestamp
                    if comment['type'] == "DiffNote":
                        if comment['author']['username'] \
                                not in user_comment_dic.keys():
                            user_comment_dic[
                                comment['author']['username']] = list()
                        comment_dic = dict()
                        comment_dic['comment'] = comment['body']
                        comment_create_time = time.strptime(
                            comment['created_at'],
                            "%Y-%m-%dT%H:%M:%S.%f+08:00"
                        )
                        comment_create_timestamp = time.mktime(
                            comment_create_time
                        )
                        comment_dic['time'] = comment_create_timestamp
                        user_comment_dic[comment['author']['username']].append(
                            comment_dic
                        )
                if approver:
                    for user in approver.keys():
                        comments = list()
                        if user in user_comment_dic.keys():
                            comments = user_comment_dic[user]
                        self.update_code_review(
                            mr_id, user, repo_id, comments,
                            mr_create_timestamp,
                            approver[user],
                            0,
                            0,
                            'MR'
                        )

                item = {
                    'mr_id': mr_id,
                    'auther': author,
                    'reviewers': json.dumps(list(user_comment_dic.keys())),
                    'approver': json.dumps(list(approver.keys())),
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

    def handle_lint(self, repo, commit_list: dict):
        phs_repo = models.Ph.objects.filter(repo_id=repo)
        ph_list = [item.ph_id for item in phs_repo]
        for commit in commit_list.values():
            commit_detail = commit['commit_info']
            cr_ph = re.findall(self.ph_reg, commit_detail)
            if len(cr_ph) == 0:
                continue
            cr_ph_str = ','.join(cr_ph)
            ph_id = re.findall("\\d+", cr_ph_str)

            if ph_id and ph_id[0] not in ph_list:
                self.gen_ph_data_ids(ph_id[0], repo)

    def gen_ph_data_ids(self, ph_id, repo):
        ph_info = PH.get_ph_info(ph_id)
        for id, ph_data in ph_info.items():
            reviewer = list()
            comments_mum = 0
            ph_id = id
            close_time = None
            status = ''
            review_duration = 0
            if ph_data.get('accepter'):
                reviewer = list(ph_data['accepter'].keys())
                for user in reviewer:
                    comments = ''
                    if user in ph_data['comments'].keys():
                        # print(user)
                        comments = ph_data['comments'][user]
                    self.update_code_review(
                        id, user, repo, comments,
                        ph_data['create_time'],
                        ph_data['accepter'][user],
                        ph_data['file_count'],
                        ph_data['line_count'],
                        'PH'
                    )
            if ph_data.get('ph_data', None):
                continue
            if 'create_time' not in ph_data.keys():
                continue
            if 'comments' in ph_data.keys():
                for user, user_comment in ph_data['comments'].items():
                    comments_mum += len(user_comment)
                review_duration = int(ph_data['review_duration'])
            lint_passed = ph_data['lint_passed']

            create_time = self.get_localtime(ph_data['create_time'])
            if 'close_time' in ph_data.keys():
                close_time = self.get_localtime(ph_data['close_time'])
                status = 'Closed'

            try:
                data = dict()
                data['reviewer'] = json.dumps(reviewer, ensure_ascii=False)
                data['open_time'] = create_time
                data['close_time'] = close_time
                data['file_count'] = ph_data['file_count']
                data['line_count'] = ph_data['line_count']
                data['status'] = status
                data['review_duration'] = review_duration
                data['lint_status'] = lint_passed
                data['comments_mum'] = comments_mum
                data['jobs'] = json.dumps(ph_data['jobs'], ensure_ascii=False)
                models.Ph.objects.update_or_create(
                    data,
                    ph_id=ph_id,
                    repo_id=repo
                )
            except Exception as e:
                print("插入PH数据失败:", str(e))
            else:
                # 如果是插入数据， 一定要提交数据， 不然数据库中找不到要插入的数据;
                print("插入PH数据成功;")

    def update_code_review(self, _id, user, repo, comments, create_time,
                           accept_time, file_count, line_count, source):
        # print('start to update code review')
        duration = self.get_time_slot(create_time, accept_time)
        create_time = self.get_localtime(create_time)
        accept_time = self.get_localtime(accept_time)
        # print(comments)
        comments_mum = len(comments)
        try:
            cr_in_db = models.CodeReview.objects.filter(source_id=_id,
                                                        source=source,
                                                        reviewer=user)
            if cr_in_db:
                cr_in_db[0].start_time = create_time
                cr_in_db[0].accept_time = accept_time
                cr_in_db[0].repo_id = repo
                cr_in_db[0].file_count = file_count
                cr_in_db[0].line_count = line_count
                cr_in_db[0].duration = duration
                cr_in_db[0].comments_mum = comments_mum
                cr_in_db[0].comments = json.dumps(comments, ensure_ascii=False)
                cr_in_db[0].save()
            else:
                newcr = models.CodeReview(
                    source_id=_id,
                    source=source,
                    reviewer=user,
                    repo_id=repo,
                    file_count=file_count,
                    line_count=line_count,
                    start_time=create_time,
                    accept_time=accept_time,
                    duration=duration,
                    comments_mum=comments_mum,
                    comments=json.dumps(comments, ensure_ascii=False),
                )
                newcr.save()
        except Exception as e:
            print("插入CR数据失败:", str(e))
        else:
            # 如果是插入数据， 一定要提交数据， 不然数据库中找不到要插入的数据;
            print("插入CR数据成功:" + str(_id))

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
    CRMR().handle()
