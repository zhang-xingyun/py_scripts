import requests
import logging
import base64
import os
import sys
import json
import openpyxl
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
import pickle
import time
import gitlab

class TAGS():
    def __init__(self):
        logging.basicConfig(level = logging.INFO,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.gl = gitlab.Gitlab.from_config('trigger', 'python-gitlab.cfg')
        self.gl.auth()

    def read_excel(self, file_name, table_name):
        output = list()
        print('1')
        workbook = openpyxl.load_workbook(file_name)
        sheet = workbook[table_name]
        for line, row in enumerate(sheet.rows):
            if line == 0:
                continue
            tmp_dict = dict()
            tmp_dict['repo_id'] = row[0].value
            tmp_dict['repo_dep'] = row[1].value
            tmp_dict['repo_tag'] = row[2].value
            output.append(tmp_dict)
        return output

    def save_pkl(self, file_name, data):
        print(time.ctime(), 'to be write')
        f_obj = open(file_name, 'wb')
        pickle.dump(data, f_obj)
        f_obj.close()

    def read_pkl(self, file_name):
        f_obj = open(file_name, 'rb')
        return pickle.load(f_obj)

    def set_tags(self, output):
        print(len(output))
        for data in output:
            #if data['repo_id'] != 7679:
            #    continue
            repo_id = data['repo_id']
            repo_dep = data['repo_dep']
            repo_tag = data['repo_tag']
            if not repo_dep:
                repo_dep = '无归属'
            if not repo_tag:
                repo_tag = str()
            tag_data = ['归属部门:' + repo_dep, '标记:' + repo_tag]
            print(data['repo_id'], tag_data)
            try:
                project = self.gl.projects.get(repo_id, retry_transient_errors=True)
            except Exception as e:
                print(e)
                continue
            project.tag_list = tag_data
            project.save(retry_transient_errors=True)
        
def main():
    tags = TAGS()
    excel_data = tags.read_excel('tobetag.xlsx','project -mark')
    tags.save_pkl('tag.pkl',excel_data)
    #excel_data = tags.read_pkl('tag.pkl')
    tags.set_tags(excel_data)

if __name__ == "__main__":
    main()
