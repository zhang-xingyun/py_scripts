#### get_project_ids.py ####
# gets all project ids for a gitlab group
# assumes GitLab 'private_token' is set to env. variable called $GITLAB_TOKEN

import sys
import gitlab

# authenticate
gl = gitlab.Gitlab('https://gitlab.test.com/', private_token='')

def project_create(group_id,project_url):
	target_url=project_url
	group_id=group_id
	target_pro_name=target_url.split('/')[-1]
	target_subg=target_url.rstrip(target_pro_name)
	group = gl.groups.get(group_id)


	paths_subg=target_subg.split(group.attributes['full_path'])[1]
	list_path=paths_subg[1:][:-1].split('/')
	# list_path=['subgroup1','subg-bb','subg-cc','subg-dd']
	len(list_path)
	print ('group',len(list_path))
	group_full_path =group.attributes['full_path']

	for i in range(len(list_path)):
		print(list_path[i])
		try:
			subgroup = gl.groups.create({'name': list_path[i], 'path': list_path[i], 'parent_id': group_id})
			group_id=subgroup.attributes['id']
			print ('subgroup-creat###########',subgroup.attributes['id'])
		except Exception as e:
			groups_search = gl.groups.list(search=list_path[i])
			group_full_path =group_full_path+'/'+list_path[i]
			for group_search in groups_search:
				if group_search.attributes['full_path']==group_full_path:
					group_id=group_search.attributes['id']

	project = gl.projects.create({'name': target_pro_name, 'namespace_id': group_id})
    

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
    print (projects_list)
    return projects_list
	
	
if __name__ == "__main__":
	source_type =sys.argv[1]
	group_id =sys.argv[2]
    project_urls = sys.argv[3]
	if action_type=='xml':
		projects=project_url_list
	else:
		projects=projects_list=get_repo_from_xml(xml_file)
	for project in projects:
		project_create(group_id,project)