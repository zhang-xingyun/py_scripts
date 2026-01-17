import yaml
import os
import argparse

data = dict()
data2 = dict()
data3 = dict()

def make_config(title, url):
    data = dict()
    data_temp = dict()
    url_tmp = url.replace('https://gallery.test.com/download/', '')
    url_list = url_tmp.split('/')
    postfix_tmp= url_list[len(url_list)-1]
    postfix = postfix_tmp.split('.')[-1]
    version = url_list[len(url_list)-2]
    status = url_list[len(url_list)-7]
    project = url_list[len(url_list)-9]
    group = '.'.join(url_list[:-9])
    data_temp['group'] = group
    data_temp['project'] = project
    data_temp['status'] = status
    data_temp['version'] = version
    data_temp['postfix'] = postfix
    data[title] = data_temp
    print(data)
    return data

def write_config(data):
    curpath = os.path.dirname(os.path.realpath(__file__))
    yamlpath = os.path.join(curpath, "ci.yaml")
    with open(yamlpath, "a", encoding="utf-8") as f:
        yaml.dump(data, f)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--url',
                        metavar=str(), required=True,
                        help="gallery url",
                        type=str)
    parser.add_argument('-t', '--title',
                        metavar=str(), required=True,
                        help="config title",
                        type=str)
    args = parser.parse_args()
    data = make_config(args.title, args.url)
    write_config(data)

if __name__ == '__main__':
    main()