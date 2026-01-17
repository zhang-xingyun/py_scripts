import gitlab
import os
import sys

class TAG():
    def __init__(self):
        self.gl = gitlab.Gitlab.from_config('trigger', 'python-gitlab.cfg')
        self.gl.auth()
        self.BUILD_USER_ID = os.environ['BUILD_USER_ID']
        self.REPO_ID = os.environ['REPO_ID']
        self.TO_BE_TAG = os.environ['TO_BE_TAG']
        self.HORIZON = os.environ['HORIZON']
        self.CHIP = os.environ['CHIP']
        self.PROJECT = os.environ['PROJECT']
        self.CUSTOMER = os.environ['CUSTOMER']
        self.MODEL = os.environ['MODEL']
        self.VERSION = os.environ['VERSION']
        self.RELEASE_TYPE = os.environ['RELEASE_TYPE']
        self.DEV_BUILD_NUM = os.environ['DEV_BUILD_NUM']
        self.IS_COMMIT_HASH = os.environ['IS_COMMIT_HASH']
        self.tag_msg = str()

    def get_tag(self):
        tag_list = list()
        tag_msg = str()
        #
        if not len(self.REPO_ID) > 0:
            print('REPO_ID error')
            sys.exit(1)
        if not len(self.TO_BE_TAG) > 0 or len(self.TO_BE_TAG) < 30:
            print('TO_BE_TAG error')
            sys.exit(1)
        #
        if len(self.HORIZON) > 0:
            tag_list.append(self.HORIZON)
        #
        if len(self.CHIP) > 0:
            tag_list.append(self.CHIP)
        #
        if len(self.PROJECT) > 0:
            tag_list.append(self.PROJECT)
        #
        if len(self.CUSTOMER) > 0:
            tag_list.append(self.CUSTOMER)
        #
        if len(self.MODEL) > 0:
            tag_list.append(self.MODEL)
        #
        if len(self.VERSION) > 0:
            tag_list.append(self.VERSION)
        #
        if len(self.RELEASE_TYPE) > 0:
            tag_list.append(self.RELEASE_TYPE)
        tag_msg = '-'.join(tag_list)
        #
        if len(self.DEV_BUILD_NUM) > 0:
            tag_msg = '.'.join([tag_msg, self.DEV_BUILD_NUM])
        #
        if self.IS_COMMIT_HASH == 'true':
            tag_msg = tag_msg + '+exp.sha.' + self.TO_BE_TAG[0:7]
        self.tag_msg = tag_msg
        print('to be tag msg is %s' % self.tag_msg)

    def exec_tag(self):
        ret = False
        project = self.gl.projects.get(int(self.REPO_ID), retry_transient_errors=True)
        members = project.members.all(all=True, retry_transient_errors=True)
        print(self.BUILD_USER_ID)
        print(self.tag_msg)
        for member in members:
            if member.attributes['username'] == self.BUILD_USER_ID and \
               member.attributes['access_level'] >= 30:
                   ret = True
        if not ret:
            print('no permission')
            sys.exit()
        tag_dict = dict()
        tag_dict['tag_name'] = self.tag_msg
        tag_dict['ref'] = self.TO_BE_TAG
        tag_dict['message'] = 'create by %s' % self.BUILD_USER_ID
        print(tag_dict) 
        project.tags.create(tag_dict)
         
def main():
    tag = TAG()
    tag.get_tag()
    tag.exec_tag()

if __name__ == "__main__":
    main()
