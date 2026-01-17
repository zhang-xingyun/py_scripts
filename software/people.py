# coding:utf-8

import requests
import json
import re
import pickle
from gitlab_app import models


class People():
    def __init__(self):
        self.url = "http://11.11.11.75:8000/api/v1/dataBase/curQueryPage" \
                   "/dataBaseAllUserInfo?current=1&page_size=10000"
        self.login_page = "http://11.11.11.75:8000/api/v1/users/login"
        self.headers = {
            'User-agent': 'Mozilla/5.0 (Windows NT 6.3;WOW64; rv:36.0) '
                          'Gecko/201    00101 Firefox/36.0'}
        self.app_token_url = \
            "http://11.11.112.92:8089/userCenter/v1/app/appToken"
        self.user_rul = "http://11.11.112.92:8089/userCenter/v1/employee" \
                        "/getEmployeeInfOnJob"
        self.department_url = \
            "http://11.11.112.92:8089/userCenter/v1/department" \
            "/getAllDepartmentInfo"

    def login(self):
        data = {"username": '', "password": ''}
        res = requests.post(self.login_page, data=data, headers=self.headers)
        return res

    def get_app_token(self):
        headers = {'content-type': "application/json"}
        body = {
            "appKey": "",
            "appSecret": ""
        }
        res = requests.post(self.app_token_url, json=body, headers=headers)
        user_dic = json.loads(res.text)
        if user_dic['code'] == 0:
            print(user_dic['data']['token'])
            return user_dic['data']['token']
        return ''

    def get_user_data_v2(self):
        token = self.get_app_token()
        headers = {
            "client-app-token": token
            }
        res1 = requests.get(self.user_rul, headers=headers)
        # print(res1.text)
        user_dic = json.loads(res1.text)
        # print(user_dic)
        self.update_database_v2(user_dic)

    def get_department_data_v2(self):
        token = self.get_app_token()
        headers = {
            "client-app-token": token
            }
        res1 = requests.get(self.department_url, headers=headers)
        print(res1.text)

    def get_user_data(self, cookies):
        res = self.login()
        res1 = requests.get(self.url, cookies=res.cookies, headers=self.headers)
        user_dic = json.loads(res1.content)
        print(str(user_dic))
        # self.save_pkl('people.pkl', user_dic)
        self.update_database(user_dic)

    def save_pkl(self, file_name, data):
        # print(time.ctime(), 'to be write', file_name)
        f_obj = open(file_name, 'wb')
        pickle.dump(data, f_obj)
        f_obj.close()

    def get_feishu_token(self):
        APP_ID = ""
        APP_SECRET = ""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token" \
              "/internal/"
        headers = {
            "Content-Type": "application/json"
        }
        req_body = {
            "app_id": APP_ID,
            "app_secret": APP_SECRET
        }

        req = requests.post(url=url, data=json.dumps(req_body),
                            headers=headers, timeout=60)
        req_json = req.json()
        print(req_json)
        return req_json['tenant_access_token']

    def get_feishu_id(self, email):
        token = self.get_feishu_token()
        email_list = list()
        email_list.append(email)
        url = "https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(token)
        }
        req_body = {
            "emails": email_list,
        }
        try:
            req = requests.post(url=url, data=json.dumps(req_body),
                                headers=headers, timeout=60)
            req_json = req.json()
            print(req_json)
            return req_json['data']['user_list'][0]['user_id']
        except Exception as e:
            print("Get feishu Id failed with error:" + str(e))
            return ''

    def update_database(self, data):
        # models.People.objects.all().delete()
        try:
            for pe in data['data']['records']:
                # if pe['hobotId'] != 'test':
                #     continue
                if re.search('.+\\..+', pe['hobotId']):
                    user_in_sql = models.People.objects.filter(
                        user_id=pe['hobotId'])
                    if user_in_sql:
                        # if not user_in_sql[0].feishu_id:
                        #     user_in_sql[0].feishu_id = self.get_feishu_id(
                        #         pe['email'])
                        user_in_sql[0].businessUnit = pe['businessUnit']
                        user_in_sql[0].division = pe['division']
                        user_in_sql[0].department = pe['department']
                        user_in_sql[0].org4 = pe['org4']
                        user_in_sql[0].manager_id = pe['managerId']
                        user_in_sql[0].email = pe['email']
                        user_in_sql[0].save()
                    else:
                        new_storage = models.People.objects.create(
                            user_id=pe['hobotId'],
                            businessUnit=pe['businessUnit'],
                            division=pe['division'],
                            department=pe['department'],
                            org4=pe['org4'],
                            manager_id=pe['managerId'],
                            email=pe['email'],
                            feishu_id=self.get_feishu_id(
                                pe['email'])
                        )
                        new_storage.save()
        except Exception as e:
            print("插入数据失败:" + str(e))
        else:
            print("插入数据成功:")

    def update_database_v2(self, data):
        # models.People.objects.all().delete()
        print(len(data['data']))
        for pe in data['data']:
            try:
                # if pe['username'] != 'test':
                #     continue
                if re.search('.+\\..+', pe['username']):
                    user_in_sql = models.People.objects.filter(
                        user_id=pe['username'])
                    # print(user_in_sql)
                    if user_in_sql:
                        # if not user_in_sql[0].feishu_id:
                        #     user_in_sql[0].feishu_id = self.get_feishu_id(
                        #         pe['email'])
                        user_in_sql[0].businessUnit = pe['primaryDepName']
                        user_in_sql[0].division = pe['secondDepName']
                        user_in_sql[0].department = pe['thirdDepName']
                        user_in_sql[0].org4 = pe['fourthDepName']
                        user_in_sql[0].manager_id = pe['managerUsername']
                        user_in_sql[0].email = pe['email']
                        user_in_sql[0].feishu_id = pe['larkUserId']
                        user_in_sql[0].employee_type = pe[
                            'employeeTypeDescription']
                        user_in_sql[0].save()
                    else:
                        new_storage = models.People.objects.create(
                            user_id=pe['username'],
                            businessUnit=pe['primaryDepName'],
                            division=pe['secondDepName'],
                            department=pe['thirdDepName'],
                            org4=pe['fourthDepName'],
                            manager_id=pe['managerUsername'],
                            email=pe['email'],
                            feishu_id=pe['larkUserId'],
                            employee_type=pe['employeeTypeDescription']
                        )
                        new_storage.save()
            except Exception as e:
                print("插入数据失败:" + str(e))
            else:
                print("插入数据成功:")

def main():
    peo = People()
    # peo.get_feishu_id('test@test.com')
    # res = peo.login()
    # peo.get_user_data(res.cookies)
    # peo.get_department_data_v2()
    peo.get_user_data_v2()

def run():
    main()
