import requests
import logging
import json
import argparse
import os
import textwrap
import sys
import subprocess


def init_content():
    content = dict()
    content['msg_type'] = 'post'
    content['content'] = dict()
    content['content']['post'] = dict()
    content['content']['post']['zh_cn'] = dict()
    content['content']['post']['zh_cn']['title'] = ''
    content['content']['post']['zh_cn']['content'] = list()
    return content


def shufei_send(url, content):
    headers = {
        "Content-Type": "application/json"
    }
    req = requests.get(url=url, data=json.dumps(
        content), headers=headers, timeout=60)
    req_json = req.json()
    print(req_json)


# def trigger_test(webhook):
#     print('test', webhook)
#     report = eval(open('Result.json', 'r').read())
#     result = 'Success'
#     if report['Fail'] != 0:
#         result = 'Fail'
#     content = init_content()
#     content['content']['post']['zh_cn']['title'] = os.environ['TEST_TYPE'] + \
#         ' - 环境版本测试结果 ' + result
#     content['content']['post']['zh_cn']['content'].append(
#         [{"tag": "text", "text": "Tag : " + os.environ['TAG_NAME']}])
#     content['content']['post']['zh_cn']['content'].append(
#         [{"tag": "text", "text": "Status : " + result}])
#     content['content']['post']['zh_cn']['content'].append(
#         [{"tag": "text", "text": "测试用例数 : " + str(report['Num'])}])
#     content['content']['post']['zh_cn']['content'].append(
#         [{"tag": "text", "text": "未通过数 : " + str(report['Fail'])}])
#     content['content']['post']['zh_cn']['content'].append([
#         {"tag": "text", "text": "Jenkins URL : "},
#         {"tag": "a", "text": os.environ['BUILD_URL'],
#             "href": os.environ['BUILD_URL']}
#     ]
#     )
#     if result == 'Fail':
#         cmd = 'git cat-file tag %s' % os.environ['TAG_NAME']
#         cmd_result = subprocess.run(
#             cmd, shell=True,
#             stderr=subprocess.PIPE,
#             stdout=subprocess.PIPE).stdout
#         content['content']['post']['zh_cn']['content'].append(
#             [{"tag": "text", "text": "Tag Info : " + cmd_result.decode()}])

#     shufei_send(webhook, content)

#     if result == 'Fail':
#         sys.exit(1)


def trigger_notify(title, buildurl, msg, webhook):
    content = init_content()
    content['content']['post']['zh_cn']['title'] = title
    content['content']['post']['zh_cn']['content'].append(
        [{"tag": "text",
          "text": "Jenkins URL: " + buildurl}])
    content['content']['post']['zh_cn']['content'].append(
        [{"tag": "text",
          "text": "message : " + msg}])
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

    parser.add_argument('-b', '--buildurl',
                        metavar=str(), required=True,
                        help="input buildurl",
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
    web_hook = 'https://open.feishu.cn/open-apis/bot/v2/hook/' + args.key

    trigger_notify(args.title, args.buildurl, args.msg, web_hook)

