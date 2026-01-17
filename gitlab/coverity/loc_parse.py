import sys

file_name = sys.argv[1]
loc_info = open(file_name, 'r').read()

for line in loc_info.split('\n'):
    line_parse = line.split()
    #print(line_parse)
    if line.find('----') == 0:
        print(line + '------------------------')
        continue
    if len(line_parse) == 0:
        continue
    if line_parse[0] == 'Language':
        print(line + '\t\tComments Rate')
        continue
    base_count = 0
    for i,j in enumerate(line_parse):
        if j.isdigit():
            base_count = i
            break
    comment = int(line_parse[3+base_count])
    code = int(line_parse[4+base_count]) + comment
    if code == 0:
        rate = '0.0%'
    else:
        rate = str(round(comment/code,2) * 100) + '%'
    print(line + '\t\t' + rate)
    

