import datetime
import jenkins
import time
import logging
import requests
import json
import base64
from lxml import etree
import threading
from gitlab_app import models

logging.basicConfig(format='%(levelname)s:%(asctime)s: %(message)s',
                    datefmt='%Y/%m/%d %H:%M:%S', level=logging.DEBUG)


class JenkinsObj:
    def __init__(self, url, source) -> None:
        self.get_single_job_thread = 1
        self.passwd = base64.b64decode('').decode(
            'utf-8')
        self.server = jenkins.Jenkins(url,
                                      username='robot',
                                      password='')
        self.job_source = source
        self.error_list = list()
        self.external_list = [
            'devops/gitlab_health_check',
            'devops_se_scm/CI_LINT_CHECK_ALL',
            'devops/gitlab_health_check',
            'devops/repo_sync',
            'devops/oncall_notify',
            'devops/Jenkins_Monitor'
            ]

    def get_db_job_info(self, full_name, job_source):
        return_dict = dict()
        job = models.JenkinsBuildRecord.objects.filter(
            job_name=full_name, job_source=job_source).order_by('-job_number')
        if job:
            # print("最新的job是：" + str(job[0]))
            return_dict['job_name'] = job[0].job_name
            return_dict['job_number'] = job[0].job_number
        else:
            return_dict['job_name'] = full_name
            return_dict['job_number'] = 0
        return return_dict

    def insert_job_info(self, job_data_list):
        for job_data in job_data_list:
            try:
                item = {
                    'job_name': job_data['job_name'],
                    'job_number': job_data['job_number'],
                    'job_result': job_data['job_result'],
                    'job_start_time': job_data['job_start_time'],
                    'job_buildableTimeMillis': job_data[
                        'job_buildableTimeMillis'],
                    'job_buildingDurationMillis': job_data[
                        'job_buildingDurationMillis'],
                    'job_executingTimeMillis': job_data[
                        'job_executingTimeMillis'],
                    'job_waitingDurationMillis': job_data[
                        'job_waitingDurationMillis'],
                    'job_waitingTimeMillis': job_data['job_waitingTimeMillis'],
                    'job_duration': job_data['job_duration'],
                    'job_estimatedDuration': job_data['job_estimatedDuration'],
                }
                models.JenkinsBuildRecord.objects.get_or_create(
                    item,
                    job_build_url=job_data['job_build_url'],
                    job_source=job_data['job_source'],
                )
            except Exception as e:
                logging.error('Insert job error: ', str(e))

    def get_job_info(self):
        job_list = self.server.get_all_jobs(
            folder_depth=20,
            folder_depth_per_request=5)

        threads = list()
        for i in range(self.get_single_job_thread):
            tr = threading.Thread(
                target=self.get_single_job, args=(job_list,))
            threads.append(tr)
        for i in threads:
            i.start()
        for i in threads:
            i.join()

    def get_single_job(self, job_list: list):
        while True:
            try:
                job = job_list.pop()
            except Exception as e:
                error_msg = 'Pop job error:' + str(e)
                logging.error(error_msg)
                if len(job_list) == 0:
                    break
                continue
            try:
                if 'WorkflowMultiBranchProject' not in job['_class'] \
                        and 'Folder' not in job['_class'] \
                        and job['fullname'] not in self.external_list:
                    # execute_list = ['HAT/HAT']
                    # if not job['fullname'] in execute_list:
                    #     continue
                    logging.info(job)
                    exists_msg = self.get_db_job_info(job['fullname'],
                                                      self.job_source)
                    job_info = self.server.get_job_info(job['fullname'])
                    exists_msg['url'] = job_info['url']
                    logging.info('exists job:' + str(exists_msg))
                    if job_info['nextBuildNumber'] - 1 > \
                            exists_msg['job_number']:
                        logging.debug(
                            job['fullname'] + ' sqlNumber:' + str(
                                exists_msg[
                                    'job_number']) + ' nextNumber: ' + str(
                                job_info['nextBuildNumber']))
                        next_build_number = job_info['nextBuildNumber']
                        buildable = job_info['buildable']
                        if next_build_number == 1 or buildable is False:
                            continue
                        job_data = self.get_build_info(exists_msg,
                                                       next_build_number)
                        print(job_data)
                        self.insert_job_info(job_data)
            except Exception as e:
                error_msg = 'Found error when get job:' + str(e)
                logging.error(error_msg)

    def get_localtime(self, time_t):
        timestamp = time_t / 1000
        localtime = time.strftime(
            '%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
        return localtime

    def get_request_json(self, url):
        response = self.server.jenkins_open(
            requests.Request('GET', url))
        json_result = json.loads(response)
        return json_result

    def get_request_text(self, url):
        response = self.server.jenkins_open(
            requests.Request('GET', url))
        return response

    def get_waiting_time_from_console(self, url, time_str):
        duration = int()
        try:
            job_console = self.get_request_text(url)
            tree = etree.HTML(job_console)
            trigger = \
                tree.xpath('//*[@id="main-panel"]/pre/span[1]/b/text()')[0]
            trigger_time = '2022-01-01 ' + trigger[0:10]
            print(trigger_time)
            tigger_time_a = datetime.datetime.strptime(trigger_time,
                                                       '%Y-%m-%d %H:%M:%S')

            sp = job_console.split('Running on ')
            # print(sp[0])
            st = sp[0].split("timestamp")
            end_l = st[len(st) - 1]
            # print(end_l)
            start_time = '2022-01-01 ' + end_l[5:13]
            print(start_time)
            start_time_a = datetime.datetime.strptime(start_time,
                                                      "%Y-%m-%d %H:%M:%S")
            duration = (start_time_a - tigger_time_a).seconds * 1000
            print(duration)
        except Exception as e:
            error_msg = 'Found error when get_waiting_time_from_console:' + \
                        str(e)
            logging.error(error_msg)
            infor = time_str + ', ' + url
            self.error_list.append(infor)
        return duration

    def get_build_info(self, job_data, next_build_number):
        result_list = list()
        job_name = job_data['job_name']
        range_num = job_data['job_number']
        for i in range(range_num + 1, next_build_number):
            job_result = dict()
            job_result['job_source'] = self.job_source
            try:
                job_json = self.get_request_json(
                    job_data['url'] + str(i) + '/api/json?pretty=true')

                if job_json['result'] in ['ABORTED', 'FAILURE', 'SUCCESS']:
                    for j in job_json['actions']:
                        if '_class' in j.keys() and j['_class'] == \
                                'jenkins.metrics.impl.TimeInQueueAction':
                            job_result['job_buildableTimeMillis'] = \
                                j['buildableTimeMillis']
                            job_result['job_buildingDurationMillis'] = \
                                j['buildingDurationMillis']
                            job_result['job_executingTimeMillis'] = \
                                j['executingTimeMillis']
                            job_result['job_waitingDurationMillis'] = \
                                j['waitingDurationMillis']
                            job_result['job_waitingTimeMillis'] = \
                                j['waitingTimeMillis']
                            break

                    job_result['job_duration'] = job_json['duration']
                    job_result['job_estimatedDuration'] = \
                        job_json['estimatedDuration']
                    job_result['job_name'] = job_name
                    job_result['job_number'] = i
                    job_result['job_build_url'] = job_json['url']
                    job_result['job_result'] = job_json['result']
                    localtime = self.get_localtime(job_json['timestamp'])
                    job_result['job_start_time'] = localtime
                    # if not self.job_source == 'ci':
                    #     console_waiting_time = \
                    #         self.get_waiting_time_from_console(
                    #             job_data['url'] + str(i) + '/consoleFull',
                    #             localtime)
                    #     if not console_waiting_time == 0:
                    #         job_result[
                    #             'job_buildableTimeMillis'] = \
                    #                 console_waiting_time
                    result_list.append(job_result)
            except Exception as e:
                error_msg = 'Found error when get_build_info:' + str(e)
                logging.error(error_msg)
        # print(result_list)
        return result_list


def run():
    job_task_list = list()
    job_task_list.append(
        {
            'url': 'https://ci-mars.test.com:8443/',
            'source': 'ci-mars'
        })
    job_task_list.append(
        {
            'url': 'https://ci-earth.test.com:8443/',
            'source': 'ci-earth'
        })
    job_task_list.append(
        {
            'url': 'https://ci.test.com/',
            'source': 'ci'
        })
    for job_task in job_task_list:
        jenkins_job_obj = JenkinsObj(job_task['url'], job_task['source'])
        jenkins_job_obj.get_job_info()
        print('-------------error infor list---------------')
        for error in jenkins_job_obj.error_list:
            print(error)
