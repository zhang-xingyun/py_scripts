import logging
import argparse
import textwrap
import datetime
import time
import requests
import json


class Notify:

    def __init__(self):
        self.APP_ID = ""
        self.APP_SECRET = ""
        self.web_hook = 'https://open.feishu.cn/open-apis/bot/v2/hook/'
        self.duty_list = dict()

    def get_feishu_token(self):
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        headers = {"Content-Type": "application/json"}
        req_body = {"app_id": self.APP_ID, "app_secret": self.APP_SECRET}

        req = requests.post(url=url,
                            data=json.dumps(req_body),
                            headers=headers,
                            timeout=60)
        req_json = req.json()
        print(req_json)
        return req_json['tenant_access_token']

    def get_user_id(self, email):
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
        req = requests.post(url=url,
                            data=json.dumps(req_body),
                            headers=headers,
                            timeout=60)
        req_json = req.json()
        return req_json['data']['user_list'][0]['user_id']

    def init_content(self):
        content = dict()
        content['msg_type'] = 'post'
        content['content'] = dict()
        content['content']['post'] = dict()
        content['content']['post']['zh_cn'] = dict()
        content['content']['post']['zh_cn']['title'] = ''
        content['content']['post']['zh_cn']['content'] = list()
        return content

    def shufei_send(self, url, content):
        headers = {"Content-Type": "application/json"}
        req = requests.get(url=url,
                           data=json.dumps(content),
                           headers=headers,
                           timeout=60)
        req_json = req.json()
        print(req_json)

    def trigger(self, user_id, user_tel):
        title = ''
        intro = ''
        url_page = ''
        url_desk = ''
        url_group = ''
        content = self.init_content()
        content['content']['post']['zh_cn']['title'] = title
        content['content']['post']['zh_cn']['content'].append([{
            "tag":
            "text",
            "text":
            intro + '\n'
        }])
        content['content']['post']['zh_cn']['content'].append([{
            "tag": "a",
            "text": '',
            "href": url_page
        }])
        content['content']['post']['zh_cn']['content'].append([{
            "tag": "a",
            "text": '',
            "href": url_desk
        }])
        content['content']['post']['zh_cn']['content'].append([{
            "tag":
            "a",
            "text":
            '',
            "href":
            url_group
        }])
        content['content']['post']['zh_cn']['content'].append([{
            "tag": "text",
            "text": ''
        }])
        content['content']['post']['zh_cn']['content'].append([{
            "tag":
            "at",
            "user_id":
            user_id
        }])
        content['content']['post']['zh_cn']['content'].append([{
            "tag":
            "text",
            "text":
            '联系电话 ' + user_tel
        }])
        self.shufei_send(self.web_hook, content)

    def send(self, group_key):
        self.web_hook = ''.join([self.web_hook, group_key])
        logging.debug(self.web_hook)
        timestamp = time.time()  # + 3600*24*1
        dt_object = datetime.datetime.fromtimestamp(timestamp)
        #weekday = dt_object.weekday()
        year, week, weekday = dt_object.isocalendar()
        logging.debug(year)
        logging.debug(week)
        logging.debug(weekday)
        if weekday < 6:
            duty_one = self.duty_list[weekday]
        else:
            duty_one = self.duty_list[week % len(self.duty_list) + 1]
        logging.debug(duty_one)
        user_id = self.get_user_id(duty_one['email'])
        logging.debug('user_id is')
        logging.debug(user_id)
        self.trigger(user_id, duty_one['tel'])


if __name__ == '__main__':
    format_rule = '[%(levelname)s] '
    format_rule += '%(asctime)s '
    format_rule += '%(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=format_rule)

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''\
                     input key type build_url and error msg
                     '''))

    parser.add_argument('-k',
                        '--key',
                        metavar=str(),
                        required=True,
                        help="input bot key",
                        type=str)
    args = parser.parse_args()
    logging.debug(args.key)
    notify = Notify()
    notify.send(args.key)
