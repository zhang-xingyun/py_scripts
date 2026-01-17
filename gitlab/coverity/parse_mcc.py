from lxml import etree
import sys

xml_data = etree.parse(sys.argv[1],etree.HTMLParser())
fnmetric_list = xml_data.getroot()[0]
mcc_level = int(sys.argv[2])
file_flag = False

if len(sys.argv) == 4:
    file_flag = True
    file_path = sys.argv[3]
    file_data = open(sys.argv[3],'r').readlines()

for fnmetric in fnmetric_list:
    file_mcc = None
    mcc = 0
    for data in fnmetric:
        if data.tag == 'file':
            file_mcc = data.text
        if data.tag == 'metrics':
            for i in data.text.split(';'):
                tmp = i.split(':')
                if tmp[0] == 'cc':
                    file_mcc = file_mcc + ' : mcc ' + tmp[1]
                    mcc = int(tmp[1])
                    break
    if file_mcc.find('/usr/include') == 0:
        continue
    if file_mcc.find('/opt/opencode/linaro') == 0:
        continue
    if mcc > mcc_level:
        if file_flag:
            for i in file_data:
                tmp = i.strp()
                if len(i) == 0:
                    continue
                if file_mcc.find(tmp) > 0:
                    print(file_mcc)
        else:
            print(file_mcc)
#for elments in root:
#    for key in elments.attrib.keys():
#        print(key,':',elments.get(key))
