import requests
import sys

revision_id = sys.argv[1]
file_name = sys.argv[2]
build_url = sys.argv[3]
title = sys.argv[4]

ph_api_token = ''
ph_api_revision_edit = 'https://cr.test.com/api/differential.revision.edit'

msg = open(file_name, 'r').read()
msg = title + '\nBuild Url:' + build_url + '\n' + msg

data = dict()
data['api.token'] = ph_api_token
data['transactions[0][type]'] = 'comment'
data['transactions[0][value]'] = msg
data['objectIdentifier'] = revision_id
requests.post(ph_api_revision_edit, data=data)
