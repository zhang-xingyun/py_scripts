import re
from hashlib import sha1
from datetime import datetime
import requests

from gitlab_app.models import PHCodeReviewRepo, PHCodeReviewInline


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
        self.score_tag = r'<CS (.*?)>'
        self.confirm_tag = r'<(confirm|accept)>'

    # 从数据获取仓库
    def get_db_repo(self):
        ph_repo_list = PHCodeReviewRepo.objects.all()
        repo_list = []
        for repo in ph_repo_list:
            git_path = re.search(r'gitlab.test.com[:/](.*?)\.git', repo.git)
            if git_path:
                ph_name = git_path.group(1)
                repo_list.append({
                    'ph_name': ph_name,
                    'db_repo': repo,
                    'last_create': repo.last_create,
                    'repo_phid': repo.repo_phid,
                })
        return repo_list

    # 通过git路径查询仓库
    def search_repo(self, repo_info):
        data = {"api.token": self.ph_token,
                'constraints[query]': repo_info['ph_name']}
        result = requests.get(url=self.repository_search, params=data)
        for res in result.json()['result']['data']:
            if res['fields']['name'].strip() == repo_info['ph_name'].strip():
                return res['phid']
        PHCodeReviewRepo.objects.filter(id=repo_info['db_repo'].id).update(
            repo_is_register=False
        )
        return False

    # 通过仓库phid获取revision列表
    def search_revision(self, repo_phid, db_repo, after_id=None,
                        last_create_timestamp=0, revisions=[]):
        # if last_create_timestamp < 1670342400:
        #     last_create_timestamp = 1670342400
        data = {
            "api.token": self.ph_token,
            "constraints[repositoryPHIDs][0]": repo_phid,
            "constraints[createdStart]": 1670342400,
            "limit": 100
        }
        if after_id:
            data['after'] = after_id
        result = requests.get(url=self.revision_search, params=data)
        result = result.json()['result']
        if len(revisions) == 0:
            revisions = []

        for res in result['data']:
            if res['fields']['dateCreated'] > last_create_timestamp:
                last_create_timestamp = res['fields']['dateCreated']
            after_id = res['id']
            revisions.append({
                'db_id': db_repo.id,
                'id': res['id'],
                'phid': res['phid'],
                'auth_phid': res['fields']['authorPHID']
            })
        if len(result['data']) < int(result['cursor']['limit']):
            self.update_ph_review_table(db_repo.id, repo_phid,
                                        last_create_timestamp)
            self.save_score(revisions, db_repo)
            return

        self.search_revision(repo_phid, db_repo, after_id,
                             last_create_timestamp,
                             revisions)

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

    def get_comments(self, ph_info):
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
            replyToCommentPHID = comment['fields']['replyToCommentPHID']
            if replyToCommentPHID and content_map.get(replyToCommentPHID):
                submit = re.search(self.confirm_tag, content, re.S)
                if submit:
                    content_map[replyToCommentPHID]['confirm'] = True
                    reply_comment = re.sub(self.confirm_tag, '',
                                           content, re.S).strip()
                    content_map[replyToCommentPHID]['reply_comment'] = \
                        reply_comment
                    continue
            score = re.search(self.score_tag, content, re.S)
            content = re.sub(self.score_tag, '', content).strip()
            if score:
                score = score.group(1).strip()
            else:
                continue
            inline_phid = comment['comments'][0]['phid']
            comment_user_ph_id = comment['comments'][0]['authorPHID']
            user_list.append(comment_user_ph_id)
            anchor = self.digestForAnchor(comment['fields']['path'])
            url = f'{self.ph_url}/D{revision_id}#change-{anchor}'
            content_map[inline_phid] = {
                'comment_user_ph_id': comment_user_ph_id,
                'comment': content,
                'score': score,
                'line': comment['fields']['line'],
                'length': comment['fields']['length'],
                'file_name': comment['fields']['path'],
                'ph_repo': ph_info['db_id'],
                'auth_phid': auth_phid,
                'url': url,
                'created_at': self.timestamp_to_datetime(
                    comment['comments'][0]['dateCreated']),
                'confirm': False
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
            data[f'constraints[phids][{index}]'] = user_id
            index += 1
            user_set.add(user_id)

        response = requests.post(self.user_search, data=data)
        for res in response.json()['result']['data']:
            user_phid = res['phid']
            name = res['fields']['username']
            self.user_map[user_phid] = name

    @staticmethod
    def timestamp_to_datetime(timestamp):
        dt_time = datetime.fromtimestamp(timestamp)
        time_str = dt_time.strftime('%Y-%m-%d %H:%M:%S')
        return time_str

    def save_score(self, revisionid_and_revisionphid, db_repo):
        print(111, revisionid_and_revisionphid)
        for revision in revisionid_and_revisionphid:
            r_content_map, r_user_list = self.get_comments(revision)
            self.search_user(r_user_list)
            for content in r_content_map.values():
                user_ph_id = content['comment_user_ph_id']
                user = self.user_map.get(user_ph_id, '')
                content['reviewer'] = user
                author = self.user_map.get(content['auth_phid'], '')
                content['author'] = author
                content.pop('comment_user_ph_id')
                content.pop('auth_phid')
                content['ph_repo'] = db_repo
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
    db_repo_list = p.get_db_repo()
    for db_repo in db_repo_list:
        repo_phid = db_repo['repo_phid']
        if not repo_phid:
            repo_phid = p.search_repo(db_repo)
        if not repo_phid:
            continue
        p.search_revision(repo_phid, db_repo['db_repo'], None,
                          db_repo['last_create'])


def run():
    main()
