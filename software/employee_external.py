# coding:utf-8

import gitlab

from gitlab_app import models


class EmployeeExternal(object):

    def __init__(self):
        self.gl = gitlab.Gitlab.from_config('trigger', [
            '/data/wwwroot/gitlab_data/pyecharts_django/python-gitlab.cfg'])
            # 'python-gitlab.cfg'])
        self.gl.auth()
        self.official_employee = dict()

    def get_official_employee(self):
        employee = models.People.objects.filter(employee_type='正式员工').values(
            'user_id', 'email')
        for e in employee:
            self.official_employee[e.get('user_id', '')] = 1

    def get_gitlab_users(self):
        users = self.gl.users.list(all=True)
        for user in users:
            user_name = user.username
            try:
                # 正式员工
                if self.official_employee.get(user_name):
                    if user.external:
                        user.external = False
                        user.save()
                # 外包和实习
                else:
                    if not user.external:
                        user.external = True
                        user.save()
            except Exception as error:
                print(f"{user_name} error {error}")


def run():
    e = EmployeeExternal()
    e.get_official_employee()
    e.get_gitlab_users()
