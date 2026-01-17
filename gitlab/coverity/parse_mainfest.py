import xmltodict
import json
import sys

xml_file = sys.argv[1]
revision_id = sys.argv[2]
branch_name = sys.argv[3]
git_path = sys.argv[4]


xml = open(xml_file, encoding='utf-8').read()
xml_dict = xmltodict.parse(xml)
jsonStr = json.dumps(xml_dict)
data_dict = json.loads(jsonStr)

git_name = git_path.split('/')[-1].split('.')[0]

code_path = str()

for num, project in enumerate(data_dict['manifest']['project']):
    path = project['@path'].strip()
    name = project['@name'].strip()
    if name != git_name:
        continue
    print(num, path, name)
    data_dict['manifest']['project'][num]['@revision'] = revision_id
    if len(branch_name) != 40:
        data_dict['manifest']['project'][num]['@upstream'] = branch_name
    code_path =  project['@path'].strip()
    break

f_obj = open('code_path.txt','w')
f_obj.write(code_path)
f_obj.close()


f_obj = open('build.xml','w')
f_obj.write(xmltodict.unparse(data_dict, pretty=True))
f_obj.close()
