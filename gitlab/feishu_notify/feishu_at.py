import requests
import logging
import json
import argparse
import textwrap
import datetime
import sys


APP_ID = ""
APP_SECRET = ""


def init_content():
    content = dict()
    content['msg_type'] = 'post'
    content['content'] = dict()
    content['content']['post'] = dict()
    content['content']['post']['zh_cn'] = dict()
    content['content']['post']['zh_cn']['title'] = ''
    content['content']['post']['zh_cn']['content'] = list()
    return content


def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    headers = {
        "Content-Type" : "application/json"
    }
    req_body = {
        "app_id": APP_ID,
        "app_secret": APP_SECRET
    }

    req = requests.post(url=url, data=json.dumps(req_body), headers=headers, timeout=60)
    req_json = req.json()
    print(req_json)
    return req_json['tenant_access_token']

def get_user_id(email):
    token = get_feishu_token()
    email_list = list()
    email_list.append(email)
    url = "https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id"
    headers = {
        "Content-Type" : "application/json",
        "Authorization": "Bearer {}".format(token)
    }
    req_body = {
        "emails": email_list,
    }

    req = requests.post(url=url, data=json.dumps(req_body), headers=headers, timeout=60)
    req_json = req.json()
    print(req_json)
    return req_json['data']['user_list'][0]['user_id']


def shufei_send(url, content):
    headers = {
        "Content-Type": "application/json"
    }
    req = requests.get(url=url, data=json.dumps(
        content), headers=headers, timeout=60)
    req_json = req.json()
    print(req_json)


def trigger_notify(title, webhook, user1_info, user2_info):
    t1 = datetime.datetime.today()
    format_today = t1.strftime('%Y-%m-%d')
    t2 = datetime.date.today() + datetime.timedelta(days=1)
    format_tomorrow = t2.strftime('%Y-%m-%d')
    content = init_content()
    content['content']['post']['zh_cn']['title'] = title
    content['content']['post']['zh_cn']['content'].append(
        [{"tag": "text",
          "text": "今日: " + format_today}])
    content['content']['post']['zh_cn']['content'].append(
        [{"tag": "at",
          "user_id": user1_info[0]}])

    content['content']['post']['zh_cn']['content'].append(
        [{"tag": "text",
          "text": "明日: " + format_tomorrow}])
    content['content']['post']['zh_cn']['content'].append(
        [{"tag": "at",
          "user_id": user2_info[0]}])

    shufei_send(webhook, content)


if __name__ == '__main__':
    format_rule = '[%(levelname)s] '
    format_rule += '%(asctime)s '
    format_rule += '%(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(
        level=logging.DEBUG,
        format=format_rule)

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''\
                     input key type build_url and error msg
                     '''))

    parser.add_argument('-k', '--key',
                        metavar=str(), required=True,
                        help="input bot key",
                        type=str)

    # parser.add_argument('-b', '--buildurl',
    #                     metavar=str(), required=True,
    #                     help="input buildurl",
    #                     type=str)
    parser.add_argument('-t', '--title',
                        metavar=str(), required=True,
                        help="input msg title",
                        type=str)
    # parser.add_argument('-m', '--msg',
    #                     metavar=str(), required=True,
    #                     help="input error msg",
    #                     type=str)
    args = parser.parse_args()
    today = datetime.datetime.today().weekday()
    # today=datetime.date(2022, 5, 8).weekday()
    web_hook = 'https://open.feishu.cn/open-apis/bot/v2/hook/' + args.key

    duty = []

    if today <= 3:
        user1 = duty[today]
        user2 = duty[today+1]
        print (user1,user2)
        user1_id = get_user_id(user1[0])
        user2_id = get_user_id(user2[0])
        user1_phone=user1[1]
        user2_phone=user2[1]
    elif today == 4:
        user1 = duty[today]
        user1_id = get_user_id(user1[0])
        user1_phone=user1[1]
        user2_id = user2_phone = 'all'
    elif today == 5:
        user1_id = user1_phone=user2_id =user2_phone= 'all'
    else:
        user1_id = user1_phone= 'all'
        user2 = duty[0]
        user2_id = get_user_id(user2[0])
        user2_phone=user2[1]
    user1_info=[user1_id,user1_phone]
    user2_info=[user2_id,user2_phone]
    trigger_notify(args.title, web_hook, user1_info, user2_info)

