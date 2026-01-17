import requests
import gitlab

from gitlab_app.models import LeaveEmployee
from gitlab.exceptions import GitlabBlockError


# from django.db.models.QuerySet import DoesNotExist

class BlockLeaveEmployee(object):

    def __init__(self):
        self.appKey = ''
        self.appSecret = ''
        self.gl = gitlab.Gitlab.from_config('trigger', [
            '/data/wwwroot/gitlab_data/pyecharts_django/python-gitlab.cfg'])
        self.gl.auth()

    def get_token(self):
        url = 'http://11.11.11.11:8089/userCenter/v1/app/appToken'
        data = {
            'appKey': self.appKey,
            'appSecret': self.appSecret
        }
        response = requests.post(url, json=data)
        res_json = response.json()
        if res_json['code'] != 0:
            raise ValueError('token 获取失败')
        return res_json['data']['token']

    def get_all_leave_employee(self):
        url = 'http://11.11.11.11:8089/userCenter/v1' \
              '/employee/getAllLeaveEmployee'
        token = self.get_token()
        headers = {
            'client-app-token': token
        }
        response = requests.get(url, headers=headers)
        for user in response.json()['data']:
            try:
                res = self.db_exist(user['username'])
            except Exception:
                res = False
            if not res:
                print(user['username'])
                people = self.gl.users.list(username=user['username'])
                for peo in people:
                    try:
                        peo.block()
                    except GitlabBlockError:
                        pass
                        
    @staticmethod
    def db_exist(username):
        try:
            res = LeaveEmployee.objects.get(username=username)
            return True
        except LeaveEmployee.DoesNotExist:
            res = LeaveEmployee.objects.create(username=username)
            return False

    def block_user(self, username):
        use = self.gl.user.get(username)


def run():
    BlockLeaveEmployee().get_all_leave_employee()
