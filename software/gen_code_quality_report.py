#!/usr/bin/env python3
import logging
import io
import sys
import os
import json
import datetime
import re
from gitlab_app import models
from gitlab_app import people
from gitlab_app.code_quality.coverity_report import get_total_coverity_data
"""gen code report"""


#  软件质量报告  #
#  By test  #
#  包含Coverity和单元测试#
os.environ['PYTHON_ALLOCATED_MEMORY'] = '4G'


def get_everyday(begin_date, end_date):
    date_list = []
    while begin_date <= end_date:
        date_str = begin_date.strftime("%Y-%m-%d")
        date_list.append(date_str)
        begin_date += datetime.timedelta(days=1)
    return date_list


def get_code_quality_data(date_from, date_to):
    coverity_data_list = list()
    projects = models.Project.objects.all()
    day_slot = get_everyday(date_from, date_to)
    item = 0
    for proj in projects:
        modules = models.ProjectModule.objects.filter(project_id=proj)
        for mod in modules:
            # if not mod.name == 'dev-test':
            #     continue
            item += 1
            report_dict = dict()
            report_dict['Item_id'] = item
            report_dict['project'] = proj.name
            report_dict['project_module'] = mod
            report_dict['stream_name'] = mod.stream_name
            repos = mod.repo.all()
            ph_list = list()
            cr_duration_list = list()
            cr_duration_less_one = 0
            cr_comment_num_list = list()
            cr_comment_less_one = 0
            lint_pass_status_list = list()
            lint_pass_num = 0
            cr_duration_less_one_rate = str(0.0) + '%'
            cr_comment_less_one_rate = str(0.0) + '%'
            cr_duration_large_one_rate = str(0.0) + '%'
            cr_comment_large_one_rate = str(0.0) + '%'
            lint_pass_rate = str(0.0) + '%'
            code_review_rate = str(0.0) + '%'
            code_review_num = 0
            total_commit_num = 0
            changed_code_line = 0
            bug_num = 0
            for repo in repos:
                # print(repo)
                # print("day_slot:" + str(day_slot))
                commits = models.Commit.objects.filter(
                    repo=repo,
                    submitter_date__in=day_slot)
                # print(commits)
                for commit in commits:
                    total_commit_num = total_commit_num + 1
                    jira_ids = json.loads(commit.jira_ids)
                    for jira_id in jira_ids:
                        jira = models.Jira.objects.filter(jira_id=jira_id)
                        if jira:
                            if jira[0].issue_type == 'Bug' \
                                    or jira[0].issue_type == 'OBug':
                                bug_num += 1
                    if commit.code_review_status == 'ph':
                        code_review_num = code_review_num + 1
                        ph_id = re.findall("\\d+", commit.cr_ph)
                        ph = models.Ph.objects.filter(ph_id=ph_id[0])
                        # print(ph)
                        if ph:
                            ph_list.append(ph_id)
                            cr_duration_list.append(ph[0].review_duration)
                            if ph[0].review_duration <= 1:
                                cr_duration_less_one += 1
                            cr_comment_num_list.append(ph[0].comments_mum)
                            if ph[0].comments_mum <= 1:
                                cr_comment_less_one += 1
                            lint_pass_status_list.append(ph[0].lint_status)
                            if ph[0].lint_status:
                                lint_pass_num += 1
                    if commit.code_review_status == 'mr':
                        code_review_num = code_review_num + 1
                        mr_id = re.findall("\\d+", commit.cr_mr)
                        mr = models.Mr.objects.filter(mr_id=mr_id[0])
                        if mr:
                            # ph_list.append(ph_id)
                            cr_duration_list.append(mr[0].merge_duration)
                            if mr[0].merge_duration <= 1:
                                cr_duration_less_one += 1
                            cr_comment_num_list.append(mr[0].comments_mum)
                            if mr[0].comments_mum <= 1:
                                cr_comment_less_one += 1
                            lint_pass_status_list.append(mr[0].lint_status)
                            if mr[0].lint_status:
                                lint_pass_num += 1
            # print(ph_list)
            # print(cr_duration_list)
            # print(cr_comment_num_list)
            # print(lint_pass_status_list)
            if len(cr_duration_list) > 0:
                cr_duration_less_one_rate = "%.2f%%" % (
                        (cr_duration_less_one / len(cr_duration_list)) * 100)
                cr_duration_large_one_rate = "%.2f%%" % (
                        (1 - cr_duration_less_one / len(
                            cr_duration_list)) * 100)
            if len(cr_comment_num_list) > 0:
                cr_comment_less_one_rate = "%.2f%%" % (
                        (cr_comment_less_one / len(cr_comment_num_list)) * 100)
                cr_comment_large_one_rate = "%.2f%%" % (
                        (1 - cr_comment_less_one / len(
                            cr_comment_num_list)) * 100)
            if len(lint_pass_status_list) > 0:
                lint_pass_rate = "%.2f%%" % (
                        (lint_pass_num / len(lint_pass_status_list)) * 100)
            if not total_commit_num == 0:
                code_review_rate = "%.2f%%" % (
                        (code_review_num / total_commit_num) * 100)
            # print(repos)
            if report_dict['stream_name']:
                print("try to get coverity result for:" + report_dict[
                    'stream_name'])
                coverity_data = models.CoverityReport.objects.filter(
                    stream_name=mod.stream_name,
                    coverity_scan_time__lt=date_to).order_by(
                    '-coverity_scan_time')
                if coverity_data:
                    # commits = models.Commit.objects.filter(cr_ph=)
                    report_dict['impact_total'] = coverity_data[0].impact_total
                    report_dict['impact_medium'] = coverity_data[
                        0].impact_medium
                    report_dict['impact_low'] = coverity_data[0].impact_low
                    report_dict['impact_high'] = coverity_data[0].impact_high
                    report_dict['ccm_num'] = coverity_data[0].ccm_num
                    report_dict['ccm_num_15'] = coverity_data[0].ccm_num_15
                    report_dict['ccm_num_25'] = coverity_data[0].ccm_num_25
                    report_dict['ccm_num_more'] = coverity_data[0].ccm_num_more
                    report_dict['ccm_num_json'] = coverity_data[0].ccm_num_json
                    report_dict['code_comment_comment'] = coverity_data[
                        0].code_comment_comment
                    report_dict['code_comment_line'] = coverity_data[
                        0].code_comment_line
                    report_dict['code_comment_rate'] = coverity_data[
                        0].code_comment_rate
                    report_dict['coverity_scan_time'] = coverity_data[
                        0].coverity_scan_time
                    report_dict['changed_code_line'] = coverity_data[
                        0].code_comment_line
            report_dict[
                'cr_duration_less_rate'] = cr_duration_less_one_rate
            report_dict[
                'cr_duration_large_rate'] = cr_duration_large_one_rate
            report_dict[
                'cr_comment_less_rate'] = cr_comment_less_one_rate
            report_dict[
                'cr_comment_large_rate'] = cr_comment_large_one_rate
            report_dict[
                'lint_pass_rate'] = lint_pass_rate
            report_dict[
                'bug_num'] = bug_num
            report_dict['code_review_rate'] = code_review_rate
            coverity_data_list.append(report_dict)
    return coverity_data_list


def update_code_quality_report():
    date_now = datetime.datetime.today()
    days_ago = (date_now - datetime.timedelta(days=30))
    code_quality_data = get_code_quality_data(days_ago, date_now)
    gen_date = date_now.strftime("%Y-%m-%d")
    for item in code_quality_data:
        try:
            item.pop('Item_id')
            # item.pop('project')
            module = item['project_module']
            item.pop('project_module')
            print("insert:" + str(item['stream_name']))
            group_in_db = models.QualityReport.objects.update_or_create(
                item,
                project_module=module,
                report_generate_time=gen_date)
        except Exception as e:
            print('Insert code_quality_report error: ', str(e))
    # return code_quality_data


def run():
    #people.main()
    get_total_coverity_data()
    update_code_quality_report()
