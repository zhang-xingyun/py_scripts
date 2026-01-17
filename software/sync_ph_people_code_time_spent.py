import datetime
import requests
import time

from gitlab_app.models import PHTimeSpent, PHUsers, PHCodeReviewRepo


class PHTimeSpentObj(object):

    def __init__(self):
        self.ph_url = 'https://cr.test.com'
        self.ph_token = ''
        # revision转换
        self.revision_search = \
            f'{self.ph_url}/api/differential.revision.search'
        # 用户查询
        self.user_search = f'{self.ph_url}/api/user.search'
        # 分支查询
        self.branch_search = f'{self.ph_url}/api/differential.diff.search'
        self.repository_search = \
            f'{self.ph_url}/api/diffusion.repository.search'
        self.user_map = {}
        self.save_user = [
        ]
        self.save_repo = {
        }

    # 计算指定日期的前N天的时间戳
    @staticmethod
    def get_last_month_day_time(n=31):
        # 今天日期
        today = datetime.date.today()
        # 昨天时间
        last_month_day = today - datetime.timedelta(days=n)
        start = int(
            time.mktime(time.strptime(str(last_month_day), '%Y-%m-%d')))
        if start < 1677945600:
            start = 1677945600
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

    def search_branch(self, revision_phid):
        data = {
            "api.token": self.ph_token,
            "constraints[revisionPHIDs][0]": revision_phid
        }
        response = requests.post(self.branch_search, data)

        for branch in response.json()['result']['data']:

            branch_name = None
            for ref in branch['fields']['refs']:
                # if ref['type'] == 'branch':
                #     branch1 = ref['name']
                if ref['type'] == 'onto':
                    branch_name = ref['name']
            if not branch_name:
                continue
            return branch_name

    # 通过仓库phid获取revision列表
    def search_revision(self, after_id=None):
        created_start = self.get_last_month_day_time()
        data = {
            "api.token": self.ph_token,
            "constraints[createdStart]": created_start,
            "limit": 100
        }
        if after_id:
            data['after'] = after_id
        result = requests.get(url=self.revision_search, params=data)
        result = result.json()['result']

        for res in result['data']:
            try:
                after_id = res['id']
                status = res['fields']['status']['closed']
                value = res['fields']['status']['value']
                if not status or value != 'published':
                    continue

                self.save_time_spent(res)
            except Exception:
                pass
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

    def save_time_spent(self, revision):
        authorPHID = revision['fields']['authorPHID']
        self.search_user([authorPHID])
        username = self.user_map.get(revision['fields']['authorPHID'])
        if not username:
            return
        if username not in self.save_user:
            return
        try:
            repo_name = self.search_repo(revision['fields']['repositoryPHID'])

            if not self.save_repo.get(repo_name):
                return

            branch_name = self.search_branch(revision['phid'])
            save_branch = self.save_repo.get(repo_name)
            if branch_name not in save_branch:
                return
            print(print(revision['fields']['status']))
            timeSpent = revision['fields']['timeSpent']

        except Exception:
            return
        title = revision['fields']['title']
        title = title.strip()
        item = {
            'title': title,
            'web_url': revision['fields']['uri'],
            'name': username,
            'phid': revision['phid'],
            'created_at': self.timestamp_to_datetime(
                revision['fields']['dateCreated']),
            'status': revision['fields']['status']['value'],
            'repo_name': repo_name,
            'time_spent': timeSpent,
            'branch': branch_name,
        }
        PHTimeSpent.objects.update_or_create(item, phid=revision['phid'])


def main():
    p = PHTimeSpentObj()
    p.search_revision()


def run():
    main()
