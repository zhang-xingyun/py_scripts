#!/usr/bin/python
# -*- coding: utf-8 -*-
import re
import os
import time
import argparse

def get_fillter_lst( filter_path, repo_name ):
    f_name = open(filter_path, "r")
    result="check"
    reg=r'^\s*#.*|^\s*$'
    for line in f_name.readlines():
        if re.match(reg,line):
            continue
        line = line.strip()
        if repo_name.find(line) >= 0 : 
            result="filter"
            break
    f_name.close()
    print(result)
    return 

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("filter", type=str, help="the filter filename")
    parser.add_argument("repo", type=str, help="check the repo path in filter or not")
    args = parser.parse_args()

    get_fillter_lst(args.filter, args.repo)


