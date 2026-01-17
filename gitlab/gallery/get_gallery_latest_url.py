import json
import os
import requests
import argparse
from requests.models import Response

class Gallery(object):

    # def __init__(self, project_id, status):
    #     self.url_token = 'https://gallery.test.com/api/auth/token-create'
    #     self.project_id = project_id
    #     self.pre_page = 100
    #     self.status = status
    #     self.url = 'https://gallery.test.com/api/projects/%s/?category=project&per_page=%d&page=1&status=%s' % (self.project_id, self.pre_page, self.status)
    #     self.username = 'xxxx'
    #     self.password = 'xxxx'
    #     self.token = self.get_token()

    def __init__(self, project_id):
        self.url_token = 'https://gallery.test.com/api/auth/token-create'
        self.project_id = project_id
        self.pre_page = 100
        self.url = 'https://gallery.test.com/api/projects/%s/?category=project&per_page=%d&page=1' % (self.project_id, self.pre_page)
        self.username = 'xxxx'
        self.password = 'xxxx'
        self.token = self.get_token()

    def get_token(self):
        data = dict()
        data['username'] = self.username
        data['password'] = self.password
        r = requests.post(self.url_token, data)
        return r.json()['token']

    def get_url(self):
        headers = dict()
        headers['Cookie'] = 'jwt=' + self.token
        resp = requests.get(self.url, headers=headers).json()
        return resp['versions'][0]['download_url']
        # output = list()
        # for i in r.json()['versions']:
        #     if i['version'].find(prefix) == 0:
        #         output.append([i['version'], i['download_url']])
        # return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--project_id',
                        metavar=str(), required=True,
                        help="gallery project id",
                        type=str)
    args = parser.parse_args()
    project_id = args.project_id
    # project_id = 1279
    # default_status = 'snapshot'
    # test_g = Gallery(project_id, default_status)
    test_g = Gallery(project_id)
    halo_sys_sw = test_g.get_url()
    print(halo_sys_sw)