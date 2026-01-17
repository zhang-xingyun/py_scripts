#!/usr/bin/env python3
import logging
import json
import datetime

import requests
from gitlab_app import models
from django.contrib.auth.models import User
from django.db.models import Q


class GetData(object):
    def __init__(self):
        self.APP_ID = ""
        self.APP_SECRET = ""
        self.APP_VERIFICATION_TOKEN = ""
        self.businessunit_list = \
            {}

    def get_content(self, version):
        quality_report_link = \
            f'http://cmo-message.test.com/code_quality_report/?' \
            f'version={version}'
        quality_report_diff_link = \
            f'http://cmo-message.test.com/code_quality_diff_report/?' \
            f'version={version}'
        advice_link = ''
        content = "\n**代码质量报告✅**\n**全量数据链接:**" + quality_report_link + \
                  "\n**差分数据链接:**" + quality_report_diff_link + \
                  "\n**请用您域账号id(如san.zhang)和密码(默认密码:Hobot123)登录**" + \
                  "\n**欢迎您对质量报告提出建议：**" + advice_link + \
                  "\n**如有疑问，可以在软件工程话题里提出.**"
        header_content = '【软件质量报告】'
        return content, header_content

    def create_staff_user(self, email):
        try:
            username = email.split('@')[0]
            user = User.objects.filter(username=username, email=email)
            if user:
                return user[0]
            else:
                new_user = User.objects.create_user(username=username,
                                                    email=email,
                                                    password="",
                                                    is_staff=True)
                return new_user
        except Exception as e:
            logging.warning("Create user failed" + str(e))
            return ''

    def send_quality_report(self, user_list=None):
        version = 1
        if not user_list:
            businessunit_json = self.businessunit_list

            user_list = []
            for b, d in businessunit_json.items():
                if isinstance(d, list):
                    if len(d) == 0:
                        users = models.People.objects.filter(
                            businessUnit=b
                        )
                    else:
                        users = models.People.objects.filter(
                            businessUnit=b, division__in=d
                        )
                    user_list.extend(users)
                else:
                    for d2, p2 in d.items():
                        users = models.People.objects.filter(
                            businessUnit=b, division=d2, department__in=p2
                        )
                        user_list.extend(users)

            user_list = [[item.feishu_id, item.email] for item in user_list]
            res = models.ReportSendLog.objects.get_or_create(
                name='quality_report',
                url='http://cmo-message.test.com/code_quality_report/',
                job_start_time=datetime.datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S')
            )
            version = res[0].id
        send_user_list = user_list
        content, header_content = self.get_content(version)
        for email in send_user_list:
            self.create_staff_user(email[1])
        send_user_list = [item[0] for item in send_user_list]
        self.feishu_id_notify(send_user_list, content, header_content)

    def send_no_read_quality_report(self):
        businessunit_list = self.businessunit_list

        user_list = models.People.objects.filter(
            businessUnit__in=businessunit_list)
        send_user_list = [item.user_id for item in user_list]
        recent_send_report = models.ReportSendLog.objects.filter(
            name='quality_report').latest('job_start_time')
        if not recent_send_report:
            return
        read_user = models.AccessRecord.objects.filter(
            Q(webpage='/code_quality_diff_report/') |
            Q(webpage='/code_quality_report/')
        ).filter(
            access_time__gte=recent_send_report.job_start_time,
        )
        read_user = read_user.values('username').distinct()
        read_user_list = [item['username'] for item in read_user]
        no_read_list = set(send_user_list).difference(
            set(read_user_list))

        content, header_content = self.get_content(recent_send_report.version)
        self.feishu_email_notify(no_read_list, content, header_content)

    def gettoken_feishu(self):
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token" \
              "/internal/"
        headers = {
            "Content-Type": "application/json"
        }
        req_body = {
            "app_id": self.APP_ID,
            "app_secret": self.APP_SECRET
        }
        req = requests.post(url=url, data=json.dumps(req_body),
                            headers=headers, timeout=60)
        req_json = req.json()
        return req_json['tenant_access_token']

    @staticmethod
    def cut(obj, sec=100):
        return [obj[i:i + sec] for i in range(0, len(obj), sec)]

    def feishu_id_notify(self, user_list, content, header_content):
        access_token = self.gettoken_feishu()
        user_list = self.cut(user_list)

        for users in user_list:
            self.send_batch_markdown(access_token, users, content,
                                     header_content)

    def feishu_email_notify(self, user_list, content, header_content):
        access_token = self.gettoken_feishu()
        for user in user_list:
            email = f'{user}@test.com'
            self.send_markdown(access_token, email, content, header_content)

    def send_batch_markdown(self, access_token, user, text, header_content):
        """发送富文本消息"""
        url = "https://open.feishu.cn/open-apis/message/v4/batch_send/"
        headers = {"Content-Type": "text/plain",
                   "Authorization": ' '.join(['Bearer', access_token])}
        data = {
            "msg_type": "interactive",
            "user_ids": user,
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": header_content
                    },
                    "template": "red"
                },
                "elements": [{"tag": "div",
                              "text": {"content": text,
                                       "tag": "lark_md"}}]}
        }
        r = requests.post(url, headers=headers, json=data)
        print(r.text)

    def send_markdown(self, access_token, email, text, header_content):
        print('Start to send feishu message')
        """发送富文本消息"""
        url = "https://open.feishu.cn/open-apis/message/v4/send/"
        headers = {"Content-Type": "text/plain",
                   "Authorization": ' '.join(['Bearer', access_token])}

        data = {
            "msg_type": "interactive",
            "email": email,
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": header_content
                    },
                    "template": "red"
                },
                "elements": [{"tag": "div",
                              "text": {"content": text,
                                       "tag": "lark_md"}}]}
        }
        r = requests.post(url, headers=headers, json=data)
        print(r.text)


def run(*args):
    data = GetData()
    if args:
        data.send_no_read_quality_report()
        pass
    else:
        data.send_quality_report()
