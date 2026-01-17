import requests
import os
import sys

ph_api_token = ''
ph_api_differential_querydiffs = 'https://cr.test.com/api/differential.querydiffs'
ph_api_differential_querydiffs_data = None

DIFF_ID = sys.argv[1]

data = dict()
data['api.token'] = ph_api_token
#data['ids[0]'] = os.environ.get('DIFF_ID')
data['ids[0]'] = DIFF_ID
changes = requests.post(ph_api_differential_querydiffs, data=data).json()['result'][DIFF_ID]['changes']
#changes = requests.post(ph_api_differential_querydiffs, data=data).json()['result'][os.environ.get('DIFF_ID')]['changes']
file_count = 0
for change in changes:
    file_count = file_count + 1
    currentPath = change['currentPath']
    #print('currentPath', currentPath)
    if ".c" in currentPath or ".cpp" in currentPath or ".h" in currentPath or ".cxx" in currentPath or ".hpp" in currentPath:
        print("YES")
        break