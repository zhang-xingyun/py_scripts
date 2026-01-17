#!/usr/bin/env python3
import requests
import logging
import pandas as pd
import io
import sys
import os
import argparse
import json
import datetime
import re

"""coverity report"""
#  软件质量报告  #
#  By robot  #
#  包含Coverity和单元测试#


class Coverity(object):
    def __init__(self, host, port, username, password):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.logger = logging.getLogger('coverity')
        self.url = 'https://{}:{}'.format(self.host, self.port)

    def load_yaml(self, filename):
        with open(filename) as file:
            return yaml.load(file, Loader=yaml.FullLoader)

    def get_issue_by_view(self, project_id):
        """get view data"""
        url = '{}/api/viewContents/issues/v1/Outstanding%20Issues'.format(
            self.url)
        payload = dict(projectId=project_id, rowCount='-1')
        headers = dict(Accept='text/csv')
        response = requests.get(url, auth=(self.username, self.password),
                                params=payload, headers=headers)
        if not response.ok:
            self.logger.error('get issue failed, err_msg: {}, status_code: {}\
        '.format(response.text, response.status_code))
            return None
        else:
            # print(response.text)
            df = pd.read_csv(io.StringIO(response.text))
            # df = df[['CID','影响','组件','文件']]
            # print(df)
            return df

    def get_summary_data(self, project_id):
        url = '{}/api/viewContents/components/v1/All%20In%20Project'.format(
            self.url)
        payload = dict(projectId=project_id, rowCount=-1)
        headers = dict(Accept='text/csv')
        response = requests.get(url, auth=(self.username, self.password),
                                params=payload, headers=headers)
        if not response.ok:
            err_msg = 'get summary failed, msg: {}, status_code: {}'.format(
                          response.text, response.status_code)
            self.logger.error(err_msg)
            return None
        else:
            df = pd.read_csv(io.StringIO(response.text))
            if '组件' in df.columns:
                df = df[df['组件'] != '其他']

            return df

    def get_high_impact_issue_from_project(self, project_id):
        url = '{}/api/v2/issues/search?includeColumnLabels=true&locale=en_us' \
              '&offset=0&queryType=byProject&rowCount=200&sortOrder=asc' \
              '"'.format(
                  self.url)
        payload = dict(projectId=project_id, rowCount=1)
        headers = dict(Accept='text/csv')
        response = requests.post(url, auth=(self.username, self.password),
                                 params=payload, headers=headers)
        if not response.ok:
            err_msg = 'get impact failed, msg: {}, status_code: {}'.format(
                          response.text, response.status_code)
            self.logger.error(err_msg)
            return None
        else:
            df = pd.read_csv(io.StringIO(response.text))
            return df

    def get_snapshot_info(self, project_id):
        url = '{}/api/viewContents/snapshots/v1/All%20In%20Project'.format(
            self.url)
        payload = dict(projectId=project_id, rowCount=20)
        headers = dict(Accept='text/csv')
        response = requests.get(url, auth=(self.username, self.password),
                                params=payload, headers=headers)
        if not response.ok:
            err_msg = 'get snapshot failed, msg: {}, status_code: {}'.format(
                          response.text, response.status_code)
            self.logger.error(err_msg)
            return None
        else:
            df = pd.read_csv(io.StringIO(response.text))
            return df

    def get_projects(self):
        proj_stream = dict()
        url = '{}/api/v2/projects?includeChildren=true&includeStreams=true' \
              ''.format(
                  self.url)
        # payload = dict(projectId=project_id)
        payload = dict()
        headers = dict(Accept='application/json')
        response = requests.get(url, auth=(self.username, self.password),
                                params=payload, headers=headers)
        if not response.ok:
            err_msg = 'get project failed, msg: {}, status_code: {}'.format(
                          response.text, response.status_code)
            self.logger.error(err_msg)
            return None
        else:
            # df = pd.read_csv(io.StringIO(response.text))
            # print(str(response.text))
            json_list = response.json()['projects']
            print(json_list)
            for item in json_list:
                print(item['name'])
                proj_stream[item['name']] = list()
                for stream in item['streams']:
                    proj_stream[item['name']].append(stream['name'])
            # print(str(proj_stream))
            return proj_stream

    def get_streams(self, project_id):
        url = '{}/api/v2/streams'.format(self.url)
        payload = dict(projectId=project_id)
        headers = dict(Accept='application/json')
        response = requests.get(url, auth=(self.username, self.password),
                                params=payload, headers=headers)
        if not response.ok:
            err_msg = 'get streams failed, msg: {}, status_code: {}'.format(
                          response.text, response.status_code)
            self.logger.error(err_msg)
            return None
        else:
            json_list = response.json()['streams']
            # print(json_list)
            for item in json_list:
                print(item['name'])
            return json_list

    def get_functions_info(self, project_id):
        url = '{}/api/viewContents/functions/v1/High CCM (>9)?'.format(
            self.url)
        payload = dict(projectId=project_id, rowCount=50000)
        headers = dict(Accept='application/json')
        response = requests.get(url, auth=(self.username, self.password),
                                params=payload, headers=headers)
        if not response.ok:
            err_msg = 'get functions failed, msg: {}, status_code: {}'.format(
                          response.text, response.status_code)
            self.logger.error(err_msg)
            return None
        else:
            return response.json()['viewContentsV1']['rows']


def read_json():
    f = open('coverity.json', encoding='utf-8')
    d_data = json.load(f)

    return d_data


def test():
    coverity = Coverity(host="coverity-earth.test.com", port=8443,
                        username="robot", password="Aa123456")
    ccm_list = coverity.get_functions_info(project_id='Bole')


def get_coverity_data():
    coverity = Coverity(host="coverity-earth.test.com", port=8443,
                        username="robot", password="Aa123456")
    proj_stream = coverity.get_projects()
    report = list()
    for proj, streams in proj_stream.items():
        issue_df = coverity.get_issue_by_view(project_id=proj)
        comments_df = coverity.get_snapshot_info(project_id=proj)
        ccm_list = coverity.get_functions_info(project_id=proj)
        ccm_count = int()
        for ccm in ccm_list:
            if int(ccm['cyclomaticComplexity']) > 9:
                ccm_count += 1
        if issue_df is None or comments_df is None:
            coverity.logger.error('get view data error')
            sys.exit(1)
        else:
            # df = issue_df[['CID', 'Impact', 'Last Snapshot Stream']]
            for stream in streams:
                report_tmp = dict()
                report_tmp['项目'] = proj
                report_tmp['Stream'] = stream
                issue_high = issue_df.loc[
                    (issue_df['Last Snapshot Stream'] == stream) & (
                        issue_df['Impact'] == 'High')]
                issue_medium = issue_df.loc[
                    (issue_df['Last Snapshot Stream'] == stream) & (
                        issue_df['Impact'] == 'Medium')]
                issue_low = issue_df.loc[
                    (issue_df['Last Snapshot Stream'] == stream) & (
                        issue_df['Impact'] == 'Low')]
                # 添加impact进report
                report_tmp['Total'] = len(issue_low) + len(issue_medium) + len(
                    issue_high)
                report_tmp['High'] = len(issue_high)
                report_tmp['Medium'] = len(issue_medium)
                report_tmp['Low'] = len(issue_low)

                comment_steam = comments_df.loc[
                    (comments_df['Stream'] == stream)
                ]
                if not comment_steam.empty:
                    comment_latest = comment_steam.iloc[0]
                    report_tmp['扫描日期'] = comment_latest['Date']
                    report_tmp['注释行数'] = comment_latest['Comment Lines']
                    report_tmp['代码行数'] = comment_latest['Code Lines (LOC)']
                    comment_rate = "%.2f%%" % ((comment_latest[
                        'Comment Lines'] /
                        comment_latest[
                        'Code Lines (LOC)']) * 100)
                    report_tmp['代码注释率'] = comment_rate
                else:
                    report_tmp['代码注释率'] = str(0.0) + '%'
                report_tmp['圈复杂度(>9)'] = ccm_count
                report.append(report_tmp)
    return report


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    now_time = datetime.datetime.now()
    report_excel_path = pd.ExcelWriter(
        '质量报告' + now_time.strftime('%Y-%m-%d') + '.xlsx')

    # 获取质量数据
    cov_data = get_coverity_data()

    # create excel
    pf = pd.DataFrame(cov_data)
    pf.to_excel(report_excel_path, encoding='utf-8', index=False)
    report_excel_path.save()
