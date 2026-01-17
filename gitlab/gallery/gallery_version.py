import json
import os
import requests
import yaml
import datetime
import logging


def load_yaml(filename):
    with open(filename) as file:
        return yaml.load(file, Loader=yaml.FullLoader)


logging.basicConfig(
    format='%(levelname)s:%(asctime)s : %(lineno)d :%(message)s',
    datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)


class Gallery(object):

    def __init__(self):
        self.exclude_path = 'exclude_list.yaml'
        self.url_token = 'https://gallery.test.com/api/auth/token-create'
        self.group_url = 'https://gallery.test.com/api/groups/'
        self.password = ''
        self.username = ''
        self.exclude_dict = self.get_exclude()
        self.token = self.get_token()
        self.projects = list()

    def get_token(self):
        data = dict()
        data['username'] = self.username
        data['password'] = self.password
        r = requests.post(self.url_token, data)
        return r.json()['token']

    def get_exclude(self):
        exclude_conf = load_yaml(self.exclude_path)
        exclude_dict = dict()
        exclude_dict['project'] = list()
        exclude_dict['group'] = list()
        if 'project' in exclude_conf.keys():
            exclude_dict['project'] = exclude_conf['project']
        if 'group' in exclude_conf.keys():
            exclude_dict['group'] = exclude_conf['group']
        logging.info('exclude_dic:' + str(exclude_dict))
        return exclude_dict

    def get_top_groups(self):
        headers = dict()
        headers['Cookie'] = 'jwt=' + self.token
        r = requests.get(self.group_url, headers=headers)
        top_groups = [g['id'] for g in r.json()['sub_groups'] if
                      g['id'] not in self.exclude_dict['group']]
        logging.info("Top groups is:")
        logging.info(top_groups)
        return top_groups

    def get_projects(self):
        top_groups = self.get_top_groups()
        for group in top_groups:
            self.get_group_projects(group)
        logging.info('Project list:')
        logging.info(self.projects)

    def get_group_projects(self, group_id):
        logging.debug('start to get project from group:' + str(group_id))
        group_url = self.group_url + str(group_id) + '/'
        headers = dict()
        headers['Cookie'] = 'jwt=' + self.token
        r = requests.get(group_url, headers=headers)
        logging.debug(r.json())
        projects = r.json()['projects']
        logging.info('Project in group:' + str(group_id))
        if projects:
            for project in projects:
                if project['id'] not in self.exclude_dict['project']:
                    logging.info(project['id'])
                    self.projects.append(project['id'])

        sub_groups = r.json()['sub_groups']
        if not sub_groups:
            return
        for group in sub_groups:
            if group['id'] in self.exclude_dict['group']:
                continue
            self.get_group_projects(group['id'])

    def get_linux(self):
        date_now = datetime.datetime.today()
        date_from = (date_now - datetime.timedelta(days=30))
        date_str = date_from.strftime("%Y-%m-%d")
        print('date_str:' + str(date_str))
        headers = dict()
        headers['Cookie'] = 'jwt=' + self.token
        # self.projects = [1660]
        for proj in self.projects:
            logging.info("try to handle verison for %s", proj)
            branch_url = 'https://gallery.test.com/api/projects/%s' \
                         '/?category=project&per_page=3000&page=1&status' \
                         '=snapshot' % proj
            r = requests.get(branch_url, headers=headers)
            version_list = r.json()['versions']
            if len(version_list) <= 10:
                logging.info('本项目snapshot版本数小于10个，不处理。')
                logging.debug(version_list)
                continue
            for i in range(10, len(version_list)):
                if version_list[i]['status'] != 'snapshot':
                    continue
                create_time = version_list[i]['create_time'].split('T')[0]
                logging.debug('create time:' + create_time)
                if create_time < date_str:
                    msg = version_list[i]['version'] + ' ' \
                          + version_list[i]['create_time'] + ' need delete'
                    logging.info(msg)
                    delete_url = 'https://gallery.test.com/api/artifacts/' \
                                 + str(version_list[i]['id'])
                    logging.info('delete ' + delete_url)
                    # 删除操作，需要操作，将try里第二行注释打开
                    try:
                        logging.info('Execute delete')
                        # ret = requests.delete(delete_url, headers=headers)
                    except Exception as e:
                        logging.error(delete_url + ' with error: ' + str(e))
                    # sys.exit(1)
                else:
                    msg = version_list[i]['version'] \
                          + ' ' + create_time + ' 在一个月以内，不处理'
                    logging.info(msg)
        return None


Gallery_api = Gallery()
Gallery_api.get_token()
Gallery_api.get_projects()
Gallery_api.get_linux()
