import sys

file1 = open(sys.argv[1], 'r').readlines()
file2 = open(sys.argv[2], 'r').readlines()
flag = sys.argv[3]
ret_list = list()

for one in file1:
    tmp = one.strip()
    if len(tmp) == 0:
        continue
    if tmp[-2:] == '.h':
        continue
    print(tmp)
    ret = "False"
    for tow in file2:
        tmp2 = tow.strip()
        if len(tmp2) == 0:
            continue
        if tmp2.find(tmp) > 0:
            ret = "True"
    print(ret)
    ret_list.append(ret)

f_obj = open('rebuild_flag.txt','w')
if flag in ret_list:
    print('rebuild')
    f_obj.write('1')
else:
    f_obj.write('0')
f_obj.close()
