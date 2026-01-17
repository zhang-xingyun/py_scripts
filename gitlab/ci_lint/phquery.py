#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from phabricator import Phabricator
from configobj import ConfigObj
import config 
import logging
import logging.handlers
import argparse

'''
the script qurey PH for a give revuiew id: 
input :
reviewid input the review id number 

output:
-r  output repo, 
-b  output branch
-d  output diffid 
-s  output code size
-f  format gitlab url to startwith ssh://git@

the output format diff when need one output or multiple output

#the out put have item name: repourl, branch, size, or diffid
$ python phquery.py -r -b  587
repourl  http://gitlab.test.com/iot/devices/x2solution/xperson.git
branch  master

#the out put have NO item name: repourl, branch, size, or diffid,
#when qurey one item, this will easy for use.
$ python phquery.py -r  587
http://gitlab.test.com/iot/devices/x2solution/xperson.git
'''

parser = argparse.ArgumentParser()
parser.add_argument("reviewid", type=int, help="input the review id number")
parser.add_argument("-r", "--repo", action="store_true", help="get the repo name")
parser.add_argument("-b", "--branch", action="store_true", help="get the branch name ")
parser.add_argument("-d", "--diffid", action="store_true", help="get the diffid of this code review")
parser.add_argument("-s", "--size", action="store_true", help="get the code change size")
parser.add_argument("-f", "--format", action="store_true", help="format gitlab url to startwith ssh://git@")


args = parser.parse_args()
answer = args.reviewid

# if args.reviewid:
#     print("query the ph review id information:" , str(args.reviewid))

##query the information from ph
settings = config.ConfigParser('/home/david/bin/config.ini')
PH_Host = settings['ph_host']
PH_Token = settings['ph_token']
Credential_Phid = settings['credential_Phid']
Logging_File_Path = settings['logging_path']

##prepare the data
api_parameters=[ args.reviewid ]

#connect handle
#TODO: add exception handle
phab = Phabricator(host=PH_Host, token=PH_Token)
#review_info = phab.differential.query(json_data)

review_info = phab.differential.query(ids=api_parameters)

repo_phid= review_info.response[0]['repositoryPHID']
##output
if args.repo:
    gitlab_repo_url=""
    #print("repoPHID ", repo_phid)
    Respository_List = phab.diffusion.repository.search(
        queryKey="active", constraints={
            'phids':[repo_phid]},   attachments={
            "uris": True, "projects": True})
    URI_Info_List = Respository_List['data'][0]['attachments']['uris']['uris']
    git_lab_uri_exist = False
    for index,URI_Info in enumerate(URI_Info_List):
        URI_Str = URI_Info['fields']['uri']['display']
        if URI_Str.find("gitlab.test.com") != -1 :
            gitlab_repo_url=URI_Str
            break;
    if args.format:
        gitlab_repo_url=gitlab_repo_url.replace('http://','ssh://git@')
    if args.branch or args.diffid or args.size:
        print("repourl ", gitlab_repo_url)
    else:
        print(gitlab_repo_url)

if args.branch:
    if args.repo or args.diffid or args.size:
        print("branch ",  review_info.response[0]['branch'])
    else:
        print(review_info.response[0]['branch'])

if args.diffid:
    if args.repo or args.branch or args.size:
        print("diffid ",  review_info.response[0]['diffs'])
    else:
        print(review_info.response[0]['diffs'])

if args.size:
    if args.repo or args.branch or args.diffid:
        print("size:", review_info.response[0]['lineCount'])
    else:
        print(review_info.response[0]['lineCount'])

## by default, print branch 
if not args.size and not args.diffid and not args.branch and not args.repo:
    print(review_info.response[0]['branch'])

