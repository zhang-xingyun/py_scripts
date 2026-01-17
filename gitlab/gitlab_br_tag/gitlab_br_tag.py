#!/usr/bin/python3
# Coding: UTF-8 
import xmltodict
import json
import sys
import gitlab

# 初始登录信息
gl = gitlab.Gitlab('https://gitlab.test.com', private_token='', api_version='4')
gl.auth()

def get_repo_from_xml(xml_file,manifest_repo,manifest_br):
    
    xml = open(xml_file, encoding='utf-8').read()
    xml_dict = xmltodict.parse(xml)
    jsonStr = json.dumps(xml_dict)
    data_dict = json.loads(jsonStr)
    manifest_remote = [data_dict['manifest']['remote']]
    print (manifest_remote)
    default = data_dict['manifest']['default']

    projects_list=[]

    for project in data_dict['manifest']['project']:
        print(project)
        # path = project['@path'].strip()
        try:
            name = project['@name'].strip()
            if '@revision' in project.keys():
                revision = project['@revision'].strip()
            else:
                revision = default['@revision'].strip()
            remote = default['@remote']
            if '@remote' in project.keys():
                remote = project['@remote']
            print(remote)
            for remotes in manifest_remote:
                print(remotes)
                try:
                    for i in remotes:
                        if i['@name'].strip() == remote.strip():
                            fetch = i['@fetch'].strip()
                except :
                    if remotes['@name'].strip() == remote.strip():
                            fetch = remotes['@fetch'].strip()  
            repo_path = "https://" + fetch.split('@')[1] + '/' + name
            project_info=[repo_path,revision]
            # local_path = path
            projects_list.append(project_info)
        except Exception as e:
            print('no project')
    manifestprojects_info=[manifest_repo,manifest_br]  
    projects_list.append(manifestprojects_info) 
    print (projects_list)
    return projects_list
    
def search_project(project):
    if project.endswith("]"):
        project = project[project.rfind('|'):-1][1:]
        print ('链接模式',project)
    if project.endswith("/"):
        project = project[:-1]
        print ('多个斜线',project)
    print ('标准输入',project)
    full_path=(project.split('test.com/')[1:][0]).split('/')[:-1]
    projectname=project.split('/')[-1]
    print ('全路径',full_path)
    print (projectname)
    projects = gl.projects.list(search='{}'.format(projectname),all=True)
    print(projects)
    for i in projects:
        if i.name.lower()==projectname.lower() and i.attributes['web_url']==project.lower():
            a=i.attributes["namespace"]['full_path']
            b=i.attributes['web_url']
            print (a,b)
            return i

def branch_create(proj_info,new_Branch):
    print(proj_info)
    source_branch=proj_info[1]
    project = search_project(proj_info[0])
    print(project)

    try:
        nb = project.branches.get(new_Branch)
        print(new_Branch,"分支已经存在")
        return Exception('error')
    except Exception as e:
        print(new_Branch,'分支不存在,开始建立新分支')
        # nb_protect = nb.protect(developers_can_push=True, developers_can_merge=True)
        branch_create = project.branches.create({'branch': new_Branch,'ref': source_branch})
        nb = project.branches.get(new_Branch)
        
        print (new_Branch,'分支创建完成')
        
        
        
        
def branch_delete(project,delete_branch):
    project = search_project(project)
    try:
        branch_delete = project.branches.delete(delete_branch)
    except Exception as e:
        print(new_Branch,'分支删除失败')
        
def label_delete(project,delete_label):
    project = search_project(project)
    try:
        label_delete = project.labels.delete(delete_label)
    except Exception as e:
        print(delete_label,'label删除失败')

def tag_delete(project,delete_tag):
    project = search_project(project)
    try:
        tag_delete = project.tags.delete(delete_tag)       
    except Exception as e:
        print(delete_tag,'tag删除失败')        

def tag_create(project,source_branch,create_tag):
    project = search_project(project)
    try:
        tag_create = project.tags.create({'tag_name': create_tag, 'ref': source_branch})       
    except Exception as e:
        print(create_tag,'tag创建失败')           
        
if __name__ == "__main__":
    action_type =sys.argv[1]
    project_urls = sys.argv[2]
    project_branch = sys.argv[3]
    xml_file= sys.argv[4]
    source_branch = sys.argv[3]
    print (xml_file)
    project_url_list=project_urls.split(',')
    print('project_list',project_urls)
    print(project_url_list)
    projects_list=[]
    if xml_file=="noxml":
        projects=project_url_list
        for project in projects:   
            project_info=[project,source_branch]
            projects_list.append(project_info)
    else:
        projects_list=get_repo_from_xml(xml_file,project_urls,project_branch)
    print(projects_list)
    for project in projects_list:
        print (project)
        if action_type=='branch-create':
            new_Branch = sys.argv[5]
            branch_create(project,new_Branch)
        elif action_type=='branch-delete':
            delete_branch= sys.argv[5]
            branch_delete(project[0],delete_branch)
        elif action_type=='tag-delete':
            delete_tag =sys.argv[5]
            tag_delete(project[0],delete_tag)
        elif action_type=='tag-create':
            create_tag =sys.argv[5]
            tag_create(project[0],source_branch,create_tag)        
        else:
            print('action_type 输入错误，请重新确认')

