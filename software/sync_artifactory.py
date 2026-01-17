# -*- coding:utf-8 -*-
import json
import requests
import pathlib
import logging
import base64
from gitlab_app.models import ArtifactoryApprover
from gitlab_app.models import ArtifactoryRepo

logging.basicConfig(
    format='%(levelname)s:%(asctime)s : %(lineno)d :%(message)s',
    datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)


class PhraseArt(object):

    def __init__(self, username, password, domain_name):
        self.username = username
        self.password = base64.b64decode(password)
        self.domain = domain_name
        self.repo_list = list()
        self.aas_info_ls = []  # # 定义[] 存储artifactory 文件信息

        # 获取当前文件的目录路径current_path 在下载文件时使用
        self.current_path = pathlib.Path().resolve()
        # 定义url类型 此url提供详细的repo列表信息
        self.url_repo = self.domain + "/artifactory/api/repositories/"
        # 定义url类型 此url提供详细的路径信息
        self.url_ass = self.domain + "/artifactory/api/storage/"
        # 定义url类型 此url提供下载文件功能
        self.url_a = self.domain + "/artifactory/"

        # 定义url集合 存储artifactory url 存储阶段未用到
        self.art_infos = list()

    def get_repos(self):
        """获取所有的repositories列表"""
        logging.info("Start to get repositories in %s" % self.domain)
        r = requests.get(self.url_repo, auth=(self.username, self.password))
        if r.status_code == 200:
            data = json.loads(r.content)
            if data:
                logging.debug(data)
                for rep in data:
                    rep_tmp = dict()
                    rep_tmp['name'] = rep['key']
                    rep_tmp['type'] = rep['type']
                    rep_tmp['api_url'] = rep['url']
                    rep_tmp['domain'] = self.domain
                    rep_tmp['api_url'] = rep['url']
                    self.repo_list.append(rep_tmp)
        logging.debug(self.repo_list)
        self.update_repo_sql()

    def get_repo_path(self):
        type_list = ['LOCAL', 'VIRTUAL']
        r_in_db = ArtifactoryRepo.objects.filter(domain=self.domain,
                                                 type__in=type_list)
        if r_in_db:
            for repo in r_in_db:
                # if not repo.name == 'conan-snapshot':
                #     continue
                repo_url = self.url_ass + repo.name
                dir_start_depth = 0
                self.get_path_infos(repo_url, dir_start_depth, repo.path_depth)
        logging.debug(self.art_infos)
        self.update_artifactory_path_sql()

    def update_repo_sql(self):
        for repo in self.repo_list:
            name = repo['name']
            domain = repo['domain']
            repo.pop('name')
            repo.pop('domain')
            try:
                ArtifactoryRepo.objects.update_or_create(
                    repo,
                    name=name, domain=domain)
                success_msg = 'Insert gallery repo success: ' + name
                logging.info(success_msg)
            except Exception as e:
                error_msg = 'Insert gallery repo error: ' + str(e)
                logging.error(error_msg)

    # 传入url 获取详细信息
    def get_path_infos(self, url, dir_depth, target_depth):
        """基于路径深度，获取所有文件的详细信息和目录"""
        logging.info("URI: " + str(url))
        logging.debug('dir_depth:' + str(dir_depth))

        r = requests.get(url, auth=(self.username, self.password))
        if r.status_code == 200:
            data = json.loads(r.content)
            art_tmp = dict()
            art_tmp['repo'] = data.get("repo", None)
            art_tmp['api_url'] = data.get("uri", None)
            if art_tmp['api_url']:
                art_tmp['path'] = data.get("uri", None).split(
                    '/artifactory/api/storage/')[1]
                art_tmp[
                    'web_url'] = self.url_a + 'webapp/#/artifacts/browse/' \
                                              'tree/General/' + art_tmp['path']
            art_tmp['domain'] = self.domain
            self.art_infos.append(art_tmp)
            if target_depth == 0:
                return
            # 获取children
            children = data.get("children", None)
            if children:
                # 遍历children 获取详细信息
                dir_depth = dir_depth + 1
                for ci in children:
                    # 如果不是folder 那么获取它的详细信息
                    if not ci.get("folder", None):
                        # 请求文件的url 获取详细的信息
                        file_res = requests.get("%s%s" % (url, ci.get("uri")),
                                                auth=(
                                                    self.username,
                                                    self.password))
                        if file_res.status_code == 200:
                            file_json = json.loads(file_res.content)
                            # 将数据转换为str 便于存储在txt
                            file_json = str(file_json)
                            self.aas_info_ls.append(file_json)
                    # 如果是folder 递归处理
                    else:
                        # 递归处理是目录的url
                        if dir_depth <= target_depth:
                            self.get_path_infos(str(url) + ci.get("uri"),
                                                dir_depth, target_depth)

    def update_artifactory_path_sql(self):
        for arti in self.art_infos:
            path = arti['path']
            domain = arti['domain']
            arti.pop('path')
            arti.pop('domain')
            g_in_db = ArtifactoryApprover.objects.filter(path=path,
                                                         domain=domain)
            if not g_in_db:
                arti['auto_created'] = True
            try:
                ArtifactoryApprover.objects.update_or_create(
                    arti,
                    path=path, domain=domain)
                success_msg = 'Insert gallery path success: ' + arti['api_url']
                logging.info(success_msg)
            except Exception as e:
                error_msg = 'Insert gallery path error: ' + str(e)
                logging.error(error_msg)

    # 程序执行主函数
    def gather(self):
        self.get_repos()
        self.get_repo_path()


def run():
    domain_list = list()
    domain_list.append({
        'name': 'http://art.k8s-idc.test.com',
    })
    domain_list.append({
        'name': 'http://ci.test.com:8081',
    })

    for domain in domain_list:
        phrase_obj = PhraseArt("test", "xxxxx", domain['name'])
        phrase_obj.gather()
