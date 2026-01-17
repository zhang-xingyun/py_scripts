# -*- coding: utf-8 -*-

import os
import sys
import shutil
import logging
import datetime
import time
import requests
import json
import argparse
from jenkins import Jenkins, JenkinsException, NotFoundException
from xml.etree import ElementTree

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

class Main(object):
    _version = '1.0.0'
    _name = os.path.basename(sys.argv[0])

    def __init__(self):
        self.server = None
        self._args = self._parse_args()
        self._username = self._args.username
        self._password = self._args.password
        self._url = self._args.url
        self._duration = self._args.duration
        self._warning = self._args.warning
        self._critical = self._args.critical
        self.APP_ID = ""
        self.APP_SECRET = ""
        self.APP_VERIFICATION_TOKEN = ""
        self._exit_codes = {
            0: 'OK',
            1: 'WARNING',
            2: 'CRITICAL',
            3: 'UNKNOWN'
        }

    def _show_fun(self, ob):
        for m in dir(ob):
            print(str(m))

    def _parse_args(self):
        parser = argparse.ArgumentParser(description='A monitor to Jenkins slaves')
        parser.add_argument('--version', action='version', version='%s %s' %
                            (self._name, self._version))
        parser.add_argument('-u', '--username', help='username', dest='username', required=False)
        parser.add_argument('-p', '--password', help='password', dest='password', required=False)
        parser.add_argument('-U', '--url', help='Jenkins instance URL', dest='url', required=True)
        parser.add_argument('-d', '--duration', help='Jenkins build duration', dest='duration', required=True,
                            type=int)
        parser.add_argument('-w', '--warning', help='warning threshold (default: %(default)s)', dest='warning',
                            default=1, type=int)
        parser.add_argument('-c', '--critical', help='critical threshold (default: %(default)s)', dest='critical',
                            default=1, type=int)
        return parser.parse_args()

    def _die(self, exit_code, message):
        print('%s - %s' % (self._exit_codes[exit_code], message))
        exit(exit_code)

    def run(self):
        offline_nodes = []
        timeout_jobs = []
        nodes = None
        excluded = 0
        username = ''
        password = ''
        if 'HOBOT_CI_PW' in os.environ:
            username = "robot"
            password = os.environ.get('HOBOT_CI_PW')
        else:
            username = self._username
            password = self._password

        try:
            self.server = Jenkins(
                url=self._url,
                username=username,
                password=password
            )
            nodes = self.server.get_nodes()
            jobs = self.server.get_running_builds()

        except JenkinsException as e:
            self._die(3, e.message)
        for job in jobs:
            job_dic = dict()
            #if job.get('name') != 'qa02-multicam_CICD_test':
            #    continue
            job_json = self.get_request(job['url'] + '/api/json?pretty=true')
            #print(job_json)
            ts = str(job_json['timestamp'])[0:10]
            last_url = ''
            gap = self.get_time_slot(ts)
            if gap > self._duration:
                job_dic['name'] = job.get('name')
                job_dic['time'] = gap
                job_dic['link'] = job['url']
                timeout_jobs.append(job_dic)
        m = len(timeout_jobs)

        for node in nodes:
            #if node.get('name') != 'ADAS-APPSW':
            #    continue
            if node.get('offline'):
                try:
                    offline_reason = self.server.get_node_info(node.get('name')).get('offlineCauseReason')
                except NotFoundException:
                    offline_reason = ''
                # print(node.get('name') + " offline reason: " + offline_reason)

                try:
                    node_descritpion = ElementTree.fromstring(self.server.get_node_config(node.get('name')))
                    node_descritpion = str(node_descritpion.find('description').text)
                except (NotFoundException, AttributeError):
                    node_descritpion = ''

                except JenkinsException as e:
                    self._die(3, e.message)

                if 'exclud' in offline_reason.lower() or 'exclud' in node_descritpion.lower():
                    excluded += 1
                else:
                    offline_nodes.append(node.get('name'))

        n = len(offline_nodes)

        if n == 0:
            exit_message = 'All nodes are online\n'
            if m == 0:
                exit_message = exit_message + 'All jobs are normal'
            else:
                s = '' if m == 1 else 's'
                exit_message = exit_message + '%s exceeds duration job%s: %s' % (m, s, ', '.join([job['name'] for job in timeout_jobs]))
        else:
            s = '' if n == 1 else 's'
            exit_message = '%s offline node%s: %s\n' % (n, s, ', '.join(offline_nodes))
            if m == 0:
                exit_message = exit_message + 'All jobs are normal'
            else:
                s = '' if m == 1 else 's'
                exit_message = exit_message + '%s exceeds duration job%s: %s' % (m, s, ', '.join([job['link'] for job in timeout_jobs]))

        if excluded:
            exit_message = '%s (%s excluded)' % (exit_message, excluded)

        if n >= self._critical:
            exit_code = 2
        elif n >= self._warning:
            exit_code = 1
        else:
            exit_code = 0
        send_user_list = []
        self.we_chat_notify(send_user_list, offline_nodes, timeout_jobs, "Jenkins checking status:")
        self._die(exit_code, exit_message)

    # 根据10位时间戳，来比较跟当前时间差是多少小时，注：如果时间戳是13位，要提前转换为10位
    def get_time_slot(self, stamp):
        dateArray = datetime.datetime.fromtimestamp(float(stamp))
        now = datetime.datetime.now()
        gap = (now - dateArray).days * 24 + (now - dateArray).seconds / 3600
        return int(gap)

    def get_request(self, url):
        response = self.server.jenkins_open(
            requests.Request('GET', url))
        json_result = json.loads(response)
        return json_result

    #############################################
    # clean_workspace
    # 这个函数暂时还没有测试，只是预留功能，方便后期持续开发。
    #############################################
    def clean_workspace(self):
        jenkins_workspace_path = "/opt/JENKINS_HOME/workspace/"
        for dirpath, dirnames, filenames in os.walk(jenkins_workspace_path):
            if dirpath == jenkins_workspace_path:
                for dirname in dirnames:
                    jenkins_job_name = dirname
                # 如果job被删除，则清理相应的workspace
        if not self.server.has_job(jenkins_job_name):
            logger.info("removing workspace dir of job:%s" % dirname)
            shutil.rmtree(os.path.join(dirpath, dirname))

    def gettoken_feishu(self):
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        headers = {
            "Content-Type": "application/json"
        }
        req_body = {
            "app_id": self.APP_ID,
            "app_secret": self.APP_SECRET
        }
        req = requests.post(url=url, data=json.dumps(req_body), headers=headers, timeout=60)
        req_json = req.json()
        return req_json['tenant_access_token']

    def we_chat_notify(self, user_list, offline_node_list, time_out_job_list, title):
        access_token = self.gettoken_feishu()

        offline_node_text = ''
        timeout_job_text = ''
        for offlinenode in offline_node_list:
            offline_node_text = offline_node_text + '\n *' + offlinenode + '*'
        for timeoutjob in time_out_job_list:
            timeout_job_text = timeout_job_text + '\n [Build duration: ' + str(timeoutjob['time']) + ' hours,link:' + timeoutjob['link'] + '](' + timeoutjob['link'] + ')'
        content = "\n**Offline node list✅**" + offline_node_text + "\n**Exceeds duration job list✅**\n" + timeout_job_text + "\n<at id=all></at>"
        for email in user_list:
            self.send_markdown(access_token, email, content)

    def send_markdown(self, access_token, email, text):
        print('Start to send feishu message')
        """发送富文本消息"""
        url = url = "https://open.feishu.cn/open-apis/message/v4/send/"
        headers = {"Content-Type": "text/plain","Authorization": ' '.join(['Bearer', access_token])}
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
                        "content": "【Jenkins check status】"
                    },
                    "template": "red"
                },
                "elements": [{"tag": "div",
                              "text": {"content": text,
                                       "tag": "lark_md"}}]}
        }
        r = requests.post(url, headers=headers, json=data)
        print(r.text)

if __name__ == '__main__':
    try:
        main = Main()
        main.run()
        #main.we_chat_notify(['test@test.com'],[],[],'test')
    except KeyboardInterrupt:
        print('\nCancelling...')
