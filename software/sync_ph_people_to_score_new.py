import re
from hashlib import sha1
import datetime
import requests
import time
import logging
from gitlab_app.models import PHCodeReviewRepo, PHCodeReviewInline, PHUsers

logger = logging.getLogger()

logging.basicConfig(
    format='%(levelname)s:%(asctime)s : %(lineno)d :%(message)s',
    datefmt='%Y/%m/%d %H:%M:%S',
    filename='ph_score.log',
    level=logging.WARNING)


class PHComments(object):

    def __init__(self):
        self.ph_url = 'https://cr.test.com'
        self.ph_token = ''
        # revision转换
        self.revision_search = \
            f'{self.ph_url}/api/differential.revision.search'
        # 获取评论链接
        self.transaction_search = self.ph_url + '/api/transaction.search'
        # 用户查询
        self.user_search = f'{self.ph_url}/api/user.search'
        self.repository_search = \
            f'{self.ph_url}/api/diffusion.repository.search'
        self.user_map = {}
        self.score_tag = r'meme, src="class_(.)"'
        self.above = r'meme,.*?above=(.*?)[,\}]'
        self.below = r'meme,.*?below=(.*?)[,\}]'
        self.confirm_tag = r'<(confirm|accept)>'
        self.save_repo = ['ptd/ss']

    # 计算指定日期的前N天的时间戳
    @staticmethod
    def get_last_month_day_time(n=31):

        # 今天日期
        today = datetime.date.today()
        # 昨天时间
        last_month_day = today - datetime.timedelta(days=n)
        start = int(
            time.mktime(time.strptime(str(last_month_day), '%Y-%m-%d')))
        # if start < 1677945600:
        #     start = 1677945600
        return start

    # 通过仓库phid查询仓库
    def search_repo(self, ph_repo_id):
        db_repo = PHCodeReviewRepo.objects.filter(repo_phid=ph_repo_id)
        if db_repo:
            return db_repo[0].name
        data = {"api.token": self.ph_token,
                'constraints[phids][0]': ph_repo_id}
        result = requests.get(url=self.repository_search, params=data)
        for res in result.json()['result']['data']:
            save_data = {
                'name': res['fields']['name'],
                'repo_phid': res['phid'],
            }
            PHCodeReviewRepo.objects.update_or_create(save_data,
                                                      repo_phid=res['phid'])
            return save_data['name']
        return None

    # 通过仓库phid获取revision列表
    def search_revision(self, after_id=None):
        created_start = self.get_last_month_day_time()
        data = {
            "api.token": self.ph_token,
            "constraints[createdStart]": created_start,
            # "constraints[ids][0]": 255242,
            "limit": 100
        }
        if after_id:
            data['after'] = after_id
        result = requests.get(url=self.revision_search, params=data)
        result = result.json()['result']

        for res in result['data']:
            after_id = res['id']
            value = res['fields']['status']['value']
            title = res['fields']['title']
            title = title.strip()
            revision = {
                'ph_repo_id': res['fields']['repositoryPHID'],
                'id': res['id'],
                'phid': res['phid'],
                'auth_phid': res['fields']['authorPHID'],
                'dateCreated': res['fields']['dateCreated'],
                'status': value,
                'title': title,
            }

            # self.save_score(revision)
            try:
                self.save_score(revision)
            except Exception as e:
                logging.error(e)
        if len(result['data']) < int(result['cursor']['limit']):
            return

        self.search_revision(after_id)

    #
    def update_ph_review_table(self, db_id, repo_phid, last_create_timestamp):
        PHCodeReviewRepo.objects.filter(id=db_id).update(
            repo_phid=repo_phid,
            last_create=last_create_timestamp
        )

    def revision_to_phid(self, revisions):
        data = {
            "api.token": self.ph_token
        }
        for index, revision_id in enumerate(revisions):
            data[f'constraints[ids][{index}]'] = revision_id
        result = requests.get(url=self.revision_search, params=data).json()
        phids = []
        for ph in result['result']['data']:
            phids.append({
                'id': ph['id'],
                'phid': ph['phid'],
                'auth_phid': ph['fields']['authorPHID']
            })
        return phids

    def get_comments(self, ph_info, repo_name):
        revision_id = ph_info.get('id')
        ph_id = ph_info.get('phid')
        auth_phid = ph_info.get('auth_phid')
        data = {"api.token": self.ph_token, 'objectIdentifier': ph_id}
        comment_result = requests.post(url=self.transaction_search, data=data)
        comment_list = comment_result.json()['result']['data']
        revert_comment_list = comment_list[::-1]
        content_map = {}
        user_list = [auth_phid]
        for comment in revert_comment_list:
            if comment['type'] != 'inline':
                continue
            content = comment['comments'][0]['content']['raw']
            content = content.strip()
            replyToCommentPHID = comment['fields']['replyToCommentPHID']
            if replyToCommentPHID and content_map.get(replyToCommentPHID):
                if not content_map[replyToCommentPHID].get('reply_comment'):
                    content_map[replyToCommentPHID]['reply_comment'] = []
                content_map[replyToCommentPHID]['reply_comment'].append(
                    content)
                continue
            score = re.search(self.score_tag, content, re.S)
            confirm = False
            if score:
                score = score.group(1).strip().upper()
                confirm = comment['fields']['isDone']
                auto_score = 0
            else:
                score = 'A'
                auto_score = 1
            above = re.search(self.above, content, re.S)
            if above:
                above = above.group(1).strip()
            below = re.search(self.below, content, re.S)
            if below:
                below = below.group(1).strip()
            inline_phid = comment['comments'][0]['phid']
            comment_user_ph_id = comment['comments'][0]['authorPHID']
            user_list.append(comment_user_ph_id)
            anchor = self.digestForAnchor(comment['fields']['path'])
            url = f'{self.ph_url}/D{revision_id}#change-{anchor}'
            content_map[inline_phid] = {
                'revision': ph_info['id'],
                'comment_user_ph_id': comment_user_ph_id,
                'comment': content,
                'score': score,
                'line': comment['fields']['line'],
                'length': comment['fields']['length'],
                'file_name': comment['fields']['path'],
                'auth_phid': auth_phid,
                'url': url,
                'created_at': self.timestamp_to_datetime(
                    comment['comments'][0]['dateCreated']),
                'confirm': confirm,
                'repo_name': repo_name,
                'below': below,
                'above': above,
                'auto_score': auto_score
            }
        return content_map, user_list

    def search_user(self, user_list):
        data = {
            "api.token": self.ph_token
        }
        index = 0
        user_set = set()
        for user_id in user_list:
            if user_id in user_set:
                continue
            if self.user_map.get(user_id):
                continue
            db_user = PHUsers.objects.filter(phid=user_id)
            if db_user:
                self.user_map[user_id] = db_user[0].name
                continue
            data[f'constraints[phids][{index}]'] = user_id
            index += 1
            user_set.add(user_id)
        if not user_set:
            return
        response = requests.post(self.user_search, data=data)
        for res in response.json()['result']['data']:
            user_phid = res['phid']
            name = res['fields']['username']
            item = {
                'name': name,
                'phid': user_phid
            }
            PHUsers.objects.update_or_create(item, phid=user_phid)
            self.user_map[user_phid] = name

    @staticmethod
    def timestamp_to_datetime(timestamp):
        dt_time = datetime.datetime.fromtimestamp(timestamp)
        time_str = dt_time.strftime('%Y-%m-%d %H:%M:%S')
        return time_str

    def save_score(self, revision):
        repo_name = self.search_repo(revision['ph_repo_id'])

        if not repo_name:
            return

        for dep in self.save_repo:
            if repo_name.startswith(dep):
                r_content_map, r_user_list = self.get_comments(revision,
                                                               repo_name)
                self.search_user(r_user_list)
                for content in r_content_map.values():
                    user_ph_id = content.get('comment_user_ph_id', None)
                    if user_ph_id:
                        user = self.user_map.get(user_ph_id, '')
                        content['reviewer'] = user
                    author = self.user_map.get(content['auth_phid'], '')
                    content['author'] = author
                    content['title'] = revision['title']
                    content.pop('comment_user_ph_id', None)
                    content.pop('auth_phid')
                    content['repo_name'] = repo_name
                    content['status'] = revision['status']
                    if not content.get('line'):
                        PHCodeReviewInline.objects.update_or_create(
                            content,
                            revision=content['revision'],

                        )
                    else:
                        db_save = PHCodeReviewInline.objects.filter(
                            revision=content['revision'], line=None)
                        if db_save:
                            PHCodeReviewInline.objects.update_or_create(
                                content,
                                revision=content['revision'],
                            )
                        else:
                            PHCodeReviewInline.objects.update_or_create(
                                content,
                                url=content['url'],
                                line=content['line'],
                                length=content['length'],
                                file_name=content['file_name']
                            )

    # 计算锚点
    def digestForAnchor(self, str1):
        hash1 = sha1(str1.encode()).digest()
        map1 = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        result = ''
        accum = 0
        map_size = len(map1)
        for i in range(12):
            byte = hash1[i]
            low_bits = byte & 0x3F
            accum = (accum + byte) % map_size
            if low_bits < map_size:
                result += map1[low_bits]
            else:
                result += map1[accum]
        return result


def main():
    p = PHComments()
    p.search_revision()


def run():
    main()
