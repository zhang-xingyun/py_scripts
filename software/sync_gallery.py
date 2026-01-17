import requests
import yaml
import logging
import base64
from gitlab_app.models import GalleryApprover


def load_yaml(filename):
    with open(filename) as file:
        return yaml.load(file, Loader=yaml.FullLoader)


logging.basicConfig(
    format='%(levelname)s:%(asctime)s : %(lineno)d :%(message)s',
    datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)


class Gallery(object):

    def __init__(self):
        self.exclude_path = \
            '/mnt/hgfs/sharedir/repo/gitlab_data/pyecharts_django/scripts' \
            '/exclude_list.yaml'
        self.url_token = 'https://gallery.test.com/api/auth/token-create'
        self.group_url = 'https://gallery.test.com/api/groups/'
        self.password = 'xxxxx'
        self.username = 'test'
        self.token = self.get_token()
        self.projects = list()
        self.groups = list()

    def get_token(self):
        data = dict()
        data['username'] = self.username
        data['password'] = base64.b64decode(self.password)
        r = requests.post(self.url_token, data)
        return r.json()['token']

    def get_top_groups(self):
        headers = dict()
        headers['Cookie'] = 'jwt=' + self.token
        r = requests.get(self.group_url, headers=headers)
        top_groups = [g['id'] for g in r.json()['sub_groups']]
        logging.info("Top groups is:")
        logging.info(top_groups)
        return top_groups

    def get_projects(self):
        top_groups = self.get_top_groups()
        logging.info('top_groups:' + str(top_groups))
        for group in top_groups:
            # if not group == 187:
            #     continue
            self.get_group_projects(group, '')
        logging.info('Project list:')
        logging.info(self.projects)
        self.update_gallery_sql(self.projects)
        logging.info('Group list:')
        logging.info(self.groups)
        self.update_gallery_sql(self.groups)

    def get_group_projects(self, group_id, parent_group_full_name):
        logging.debug('start to get project from group:' + str(group_id))
        group_url = self.group_url + str(group_id) + '/'
        headers = dict()
        headers['Cookie'] = 'jwt=' + self.token
        r = requests.get(group_url, headers=headers)
        logging.debug(r.json())
        if parent_group_full_name:
            group_full_name = parent_group_full_name + '.' + r.json()['name']
        else:
            group_full_name = r.json()['name']

        if r.json()['parent_groups']:
            parent_id = r.json()['parent_groups'][-1]['id']
        else:
            parent_id = 0
        group_tmp = dict()
        group_tmp['category_id'] = group_id
        group_tmp['name'] = r.json()['name']
        group_tmp['parent_id'] = parent_id
        group_tmp['full_name'] = group_full_name
        group_tmp['category'] = 'group'

        self.groups.append(group_tmp)
        projects = r.json()['projects']
        logging.info('Project in group:' + str(group_id))
        if projects:
            for project in projects:
                logging.info(project['id'])
                project_tmp = dict()
                project_tmp['category_id'] = project['id']
                project_tmp['name'] = project['name']
                project_tmp['parent_id'] = group_id
                project_tmp['full_name'] = group_full_name + '|' + project[
                    'name']
                project_tmp['category'] = 'project'
                self.projects.append(project_tmp)

        sub_groups = r.json()['sub_groups']
        if not sub_groups:
            return
        for group in sub_groups:
            self.get_group_projects(group['id'], group_full_name)

    def update_gallery_sql(self, g_ps: list):
        for g_p in g_ps:
            full_name = g_p['full_name']
            name = g_p['name']
            g_p.pop('full_name')
            g_p.pop('name')
            g_in_db = GalleryApprover.objects.filter(name=name,
                                                     full_name=full_name)
            if not g_in_db:
                g_p['auto_created'] = True
            try:
                GalleryApprover.objects.update_or_create(
                    g_p,
                    full_name=full_name,
                    name=name)
                success_msg = 'Insert gallery success: ' + str(full_name)
                logging.info(success_msg)
            except Exception as e:
                error_msg = 'Insert gallery error: ' + str(e)
                logging.error(error_msg)


def run():
    Gallery_api = Gallery()
    Gallery_api.get_token()
    Gallery_api.get_projects()
