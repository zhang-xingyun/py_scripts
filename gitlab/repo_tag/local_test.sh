#!/bin/bash

export REPO_ID='7670'
export TO_BE_TAG='b57b4b84a635f50bde9eab7f8fe91a0edd303989'
export HORIZON='HORIZON'
export CHIP='G'
export PROJECT='G'
export CUSTOMER=''
export MODEL='MODEL'
export VERSION='1.0.0'
export RELEASE_TYPE='alpha'
export DEV_BUILD_NUM='100'
export IS_COMMIT_HASH='true'
export BUILD_USER_ID=''

python3 git_tag.py
