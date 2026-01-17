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

class DES():
    def __init__(self):
        logging.basicConfig(level = logging.INFO,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.gl = gitlab.Gitlab.from_config('trigger', 'python-gitlab.cfg')
        self.gl.auth()
        self.projects_attributes = dict()
        self.groups_attributes = dict()

    def read_excel(self, file_name, table_name):
        output = dict()
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
            if tmp_dict['repo_tag'] == '保留':
                tmp_dict['repo_tag'] = '在用'
            output[tmp_dict['repo_id']] = tmp_dict
            #print(tmp_dict)
        return output

    def save_pkl(self, file_name, data):
        print(time.ctime(), 'to be write')
        f_obj = open(file_name, 'wb')
        pickle.dump(data, f_obj)
        f_obj.close()

    def read_pkl(self, file_name):
        f_obj = open(file_name, 'rb')
        return pickle.load(f_obj)

    def get_all_groups(self, group_id):
        group = self.gl.groups.get(group_id)
        self.groups_attributes[group.attributes['id']] = group.attributes
        subgroups = group.subgroups.list(all=True, retry_transient_errors=True)
        for subgroup in subgroups:
            self.get_all_groups(subgroup.id)

    def get_p_g(self, query_group_list):
        print(time.ctime(), 'get_groups')
        for group_id in query_group_list:
            self.get_all_groups(group_id)
        print('group list:',self.groups_attributes.keys())
        for group_id in self.groups_attributes.keys():
            print('group:', group_id)
            group = self.gl.groups.get(group_id, retry_transient_errors=True)
            projects = group.projects.list(all=True, retry_transient_errors=True)
            for single_project in projects:
                print('project:', single_project.id)
                try:
                    project = self.gl.projects.get(single_project.id, retry_transient_errors=True)
                except Exception as e:
                    print('project error:', single_project.id)
                    print(e)
                    continue
                self.projects_attributes[project.attributes['id']] = project.attributes
        self.save_pkl('projects_attributes.pkl', self.projects_attributes)
        self.save_pkl('groups_attributes.pkl', self.groups_attributes)

    def get_project_info(self):
        project_data = self.read_pkl('projects_attributes.pkl')
        #excel_data = self.read_excel('2.xlsx', 'Sheet1')
        for project_id, data in project_data.items():
            r_project = None
            r_dep = None
            r_status = None
            r_release = None
            r_contorl = None
            r_accept = None
            #if project_id in excel_data.keys():
            #    r_dep = excel_data[project_id]['repo_dep']
            #    r_status = excel_data[project_id]['repo_tag']
            tmp = '项目:%s\r\n归属:%s\r\n状态:%s\r\n发布:%s\r\n分支管控:%s\r\n审批人:%s\r\n\r\n' % (r_project, r_dep, r_status, r_release, r_contorl, r_accept)
            if data['description']:
                tmp = tmp + data['description']
            #print('---------------------------')
            #print(project_id, tmp)
            #if project_id != 7679:
            #    continue
            #print(project_id)
            #print(tmp)
            self.set_des(project_id, tmp)
 
    def set_des(self, project_id, content):
        try:
            project = self.gl.projects.get(project_id, retry_transient_errors=True)
        except Exception as e:
            print('1', project_id, e)
            return
        project.description = content
        project.tag_list = dict()
        try:
            project.save(retry_transient_errors=True)
        except Exception as e:
            print('2', project_id, e)
            return

def main():
    des = DES()
    #des.get_p_g([1503])
    des.get_project_info()
    #des.set_des(7124)
    #excel_data = tags.read_excel('tobetag.xlsx','project -mark')
    #tags.save_pkl('tag.pkl',excel_data)
    #excel_data = tags.read_pkl('tag.pkl')
    #tags.set_tags(excel_data)

if __name__ == "__main__":
    main()
