import requests
import json
import argparse
import textwrap

APP_ID = ""
APP_SECRET = ""
APP_VERIFICATION_TOKEN = ""

def gettoken_feishu():
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
    return req_json['tenant_access_token']

def shufei_send(access_token, email, content):
    url = "https://open.feishu.cn/open-apis/message/v4/send/"
    headers = {
        "Authorization" : ' '.join(['Bearer', access_token]),
        "Content-Type" : "application/json"
    }
    data = dict()
    data["email"] = email
    data["msg_type"] = "post"
    data["content"] = content
    req = requests.post(url=url, data=json.dumps(data), headers=headers, timeout=60)
    req_json = req.json()

def we_chat_notify(build_user, user_list, build_url, build_status, title, msg):
    access_token = gettoken_feishu()
    content = dict()
    content["post"] = dict()
    content["post"]["zh_cn"] = dict()
    content["post"]["zh_cn"]["title"] = title
    content["post"]["zh_cn"]["content"] = list()
    content["post"]["zh_cn"]["content"].append([{"tag": "text", "text": "Build status: " + build_status}])
    content["post"]["zh_cn"]["content"].append([{"tag": "text", "text": "Build stage: " + msg}])
    content["post"]["zh_cn"]["content"].append([{"tag": "text", "text": "Build url: " + build_url}])
    content["post"]["zh_cn"]["content"].append([{"tag": "text", "text": "Build by: " + build_user}])
    for email in user_list:
        shufei_send(access_token, email, content)


    return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''\
                     input key type build_url and error msg
                     '''))

    parser.add_argument('-u', '--build_user',
                        metavar=str(), required=True,
                        help="input build user",
                        type=str)

    parser.add_argument('-l', '--build_url',
                        metavar=str(), required=True,
                        help="input build url",
                        type=str)
    parser.add_argument('-s', '--build_status',
                        metavar=str(), required=True,
                        help="input build_status",
                        type=str)
    parser.add_argument('-t', '--title',
                        metavar=str(), required=True,
                        help="input msg title",
                        type=str)
    parser.add_argument('-m', '--msg',
                        metavar=str(), required=True,
                        help="input error msg",
                        type=str)
    args = parser.parse_args()
    user_list = list()
    user_list.append(args.build_user)
    #build_status = 'stage error'
    we_chat_notify(args.build_user, user_list,args.build_url, args.build_status, args.title, args.msg)