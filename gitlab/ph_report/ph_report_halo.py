#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging 
import requests
import time
import argparse
import pandas as pd



ph_url = 'https://cr.test.com'
ph_token = ''
differential_diff_search = ph_url + '/api/differential.query'
user_query = ph_url + '/api/user.query'
project_query = ph_url + '/api/project.query'
transaction_search = ph_url + '/api/transaction.search'
query_diffs = ph_url + '/api/differential.querydiffs'

#constraints {"projects":["halo"]}
repo_query = ph_url + '/api/diffusion.repository.search'

#constraints {"repositoryPHIDs":["PHID-REPO-okc7esoiwr2qypjozpc5"]}
revision_search = ph_url + '/api/differential.revision.search'


def public_assertion(result):
    if result['error_code'] is None:
        return True
    else:
        logging.error(f'error messages : {result["error_info"]}')
        return False

def get_repo_list(tag):
    data = dict()
    data['api.token'] = ph_token
    data['constraints[projects][0]'] = tag
    result = requests.get(url=repo_query, params=data).json()
    if not public_assertion(result):
        return False
    repo_list = list()
    for repo in result['result']['data']:
        repo_list.append(repo['phid'])
    return repo_list

def get_repo_author_id(revision_id):
    data = dict()
    data['api.token'] = ph_token
    data['constraints[phids][0]'] = revision_id
    result = requests.get(url=revision_search, params=data).json()
    if not public_assertion(result):
        return False
    for data in result['result']['data']:
        repo_id = data['fields']['repositoryPHID']
        authorPHID = data['fields']['authorPHID']
        ph_url_id = data['id']
    return repo_id, authorPHID, ph_url_id

def get_repo_name(repo_id):
    data = dict()
    data['api.token'] = ph_token
    data['constraints[phids][0]'] = repo_id
    result = requests.get(url=repo_query, params=data).json()
    if not public_assertion(result):
        return False
    for data in result['result']['data']:
        repo_name = data['fields']['name']
    return repo_name

def get_revision_author(authorPHID):
    author_name = get_username(authorPHID)
    return author_name

def get_revision_list(repo_list, days):
    data = dict()
    revision_id_list = list()
    data['api.token'] = ph_token
    for repo in repo_list:
        data['constraints[repositoryPHIDs][0]'] = repo
        result = requests.get(url=revision_search, params=data).json()
        if not public_assertion(result):
            return False
        for revision in result['result']['data']:
            if revision['fields']['status']['value'] in ['published', 'accepted']:
                time_diff = time.time() - revision['fields']['dateModified']
                time_set = days * 24 * 3600
                if time_set == 0 or time_diff < time_set:
                    revision_id_list.append(revision['phid'])
                #revision['fields']['dateModified']
    return revision_id_list

def get_username(author_id):
    data = dict()
    data['api.token'] = ph_token
    data['phids[0]'] = author_id
    result = requests.get(url=user_query, params=data).json()
    if not public_assertion(result):
        return False
    if len(result['result']) == 0:
        return False
    username = result['result'][0]['userName'] + '@test.com'
    return username

def get_localtime(time_t):
    x = time.localtime(time_t)
    localtime = time.strftime('%Y-%m-%d %H:%M:%S', x)
    return localtime

def get_diff_id(revision_id):
    data = dict()
    data['api.token'] = ph_token
    data['ids[0]'] = revision_id
    result = requests.get(url=differential_diff_search, params=data).json()
    if not public_assertion(result):
        return False
    diff_id = result['result'][0]['diffs'][0]
    title = result['result'][0]['title']
    return title, diff_id

def get_file_rows(revision_id):
    data = dict()
    data['api.token'] = ph_token
    data['revisionIDs[0]'] = revision_id
    result = requests.get(url=query_diffs, params=data).json()
    if not public_assertion(result):
        return False
    title, diff_id = get_diff_id(revision_id)
    chanegs = result['result'][diff_id]['changes']
    rows_count = 0
    for change in chanegs:
        rows_count += int(change['addLines']) + int(change['delLines'])
    file_count = len(chanegs)
    return title, rows_count, file_count

def get_ac_comment(revision_id_list):
    data = dict()
    result_list = list()
    result_list2 = list()
    data['api.token'] = ph_token
    for revision in revision_id_list:
        data['objectIdentifier'] = revision
        data['limit'] = 99999
        result =  requests.get(url=transaction_search, params=data).json()
        if not public_assertion(result):
            return False
        ac_list = list()
        for transaction in result['result']['data']:
            if transaction['type'] == 'accept':
                reviewer = get_username(transaction['authorPHID'])
                ac_list.append(reviewer)
        for transaction in result['result']['data']:
            if transaction['type'] == 'comment' and transaction['authorPHID'].find('PHID-USER') == 0 and transaction['authorPHID'] != 'PHID-USER-7nbph5b5zwolmndgmt3x':
                repo_id, authorPHID, ph_url_id = get_repo_author_id(revision)
                revision_author = get_username(authorPHID)
                if revision_author == get_username(transaction['authorPHID']):
                    continue
                comment = transaction['comments'][0]
                modifytime = get_localtime(transaction['dateModified'])
                title, rows_count, file_count = get_file_rows(ph_url_id)
                repo_name = get_repo_name(repo_id)
                ph_link = ph_url + '/D' + str(ph_url_id)
                revision_author = get_username(authorPHID)
                result_data = dict()
                result_data['ph_url'] = ph_link
                result_data['title'] = title
                result_data['repo_name'] = repo_name
                result_data['committer'] = revision_author
                result_data['reviewer'] = get_username(transaction['authorPHID'])
                result_data['comment'] = comment['content']['raw']
                result_data['code_lines'] = rows_count
                result_data['file_count'] = file_count
                result_data['modifytime'] = modifytime
                result_list.append(result_data)
                if result_data['reviewer'] in ac_list:
                    ac_list.remove(result_data['reviewer'])
            if transaction['type'] == 'inline' and transaction['authorPHID'].find('PHID-USER') == 0 and transaction['authorPHID'] != 'PHID-USER-7nbph5b5zwolmndgmt3x':
                repo_id, authorPHID, ph_url_id = get_repo_author_id(revision)
                revision_author = get_username(authorPHID)
                # if revision_author == get_username(transaction['authorPHID']):
                #     continue
                comment = transaction['comments'][0]
                inline_comment = transaction['fields']
                inline_file_path = inline_comment['path']
                inline_line = inline_comment['line']
                modifytime = get_localtime(transaction['dateModified'])
                title, rows_count, file_count = get_file_rows(ph_url_id)
                repo_name = get_repo_name(repo_id)
                ph_link = ph_url + '/D' + str(ph_url_id)
                revision_author = get_username(authorPHID)
                result_data1 = dict()
                result_data1['ph_url'] = ph_link
                result_data1['title'] = title
                result_data1['repo_name'] = repo_name
                result_data1['committer'] = revision_author
                result_data1['reviewer'] = get_username(transaction['authorPHID'])
                result_data1['inline_comment'] = comment['content']['raw']
                result_data1['inline_comment_file_path'] = inline_file_path
                result_data1['inline_comment_line'] = inline_line
                # result_data['code_lines'] = rows_count
                # result_data['file_count'] = file_count
                result_data1['modifytime'] = modifytime
                result_list2.append(result_data1)
                # if result_data['reviewer'] in ac_list:
                #     ac_list.remove(result_data['reviewer'])
        for reviewer in ac_list:
            repo_id, authorPHID, ph_url_id = get_repo_author_id(revision)
            title, rows_count, file_count = get_file_rows(ph_url_id)
            repo_name = get_repo_name(repo_id)
            ph_link = ph_url + '/D' + str(ph_url_id)
            revision_author = get_username(authorPHID)
            modifytime = get_localtime(transaction['dateModified'])
            result_data = dict()
            result_data['ph_url'] = ph_link
            result_data['title'] = title
            result_data['repo_name'] = repo_name
            result_data['committer'] = revision_author
            transaction = result['result']['data'][0]
            result_data['reviewer'] = reviewer
            result_data['comment'] = None
            result_data['code_lines'] = rows_count
            result_data['file_count'] = file_count
            result_data['modifytime'] = modifytime
            result_list.append(result_data)
    return result_list, result_list2

def to_excel(comment, inline_commnet):
    comment_df = pd.DataFrame(comment)
    inline_commnet_df = pd.DataFrame(inline_commnet)
    try:
        #df.to_csv("halo_comments.csv", encoding='utf_8_sig')
        #df.to_excel('halo_inline_comments.xlsx', encoding='utf-8', sheet_name="comments")
        with pd.ExcelWriter('halo_comments.xlsx') as writer:
            comment_df.to_excel(writer, encoding='utf-8', sheet_name="comments")
            inline_commnet_df.to_excel(writer, encoding='utf-8', sheet_name="inline_comments")
    except Exception as e:
        logging.error("excel failed, err: {}".format(e))

def main():
    parser = argparse.ArgumentParser(description='Process some args.')
    parser.add_argument('-d', '--days',
                        metavar=int(), required=False, default=0,
                        help="input days",
                        type=int)
    parser.add_argument('-t', '--tags',
                        metavar=str(), required=True,
                        help="repo tag",
                        type=str)

    args = parser.parse_args()
    days = args.days
    tag = args.tags
    repo_list = get_repo_list(tag)
    if len(repo_list) == 0:
        logging.error("can not find repo, please check tags name")
        return False
    revision_id_list = get_revision_list(repo_list, days)
    comment, inline_commnet = get_ac_comment(revision_id_list)
    to_excel(comment, inline_commnet)

if __name__ == '__main__':
    main()