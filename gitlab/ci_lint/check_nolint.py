#!/usr/bin/env python
import urllib
import urllib2
import logging
import json
import argparse


API_TOKEN = ''
diff_query = 'https://cr.test.com/api/differential.querydiffs'


def get_ph_data(url, data):
    data = urllib.urlencode(data)
    req = urllib2.Request(url, data)
    response = urllib2.urlopen(req)
    ret = ""
    if response.getcode() != 200:
        logging.error("Error occurred while processing request to PH")
        return ret
    try:
        ret = json.loads(response.read())
    except:
        logging.error("Error occurred when parsing PH response")
    return ret


def get_nolint(diff_id):
    """
    Phabricator request
    """
    data = dict()
    data['api.token'] = API_TOKEN
    data['ids[0]'] = diff_id
    response = get_ph_data(diff_query, data)
    ret = ""
    try:
        ret = response['result'][str(diff_id)]['lintStatus']
    except:
        logging.error("Error occurred when get lintstatus ")
    return ret


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--diff_id',
                        metavar=str(), required=True,
                        help="input diff_id",
                        type=str)
    args = parser.parse_args()
    lint_status = get_nolint(int(args.diff_id))
    print "lint_status: {}".format(lint_status)
    try:
        if lint_status == '4':
            with open('nolint', 'w') as f:
                f.write('nolint')
    except:
        logging.error("create nolint file ")

if __name__ == '__main__':
    main()
