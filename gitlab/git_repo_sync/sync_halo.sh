#!/bin/bash
mkdir halo
cd halo
repo init -u git@gitlab.test.com:ptd/manifest.git -b br2.1 -m $1.xml
repo sync
repo forall -c git remote remove gitlab
repo forall -c git remote -vv
repo forall -c 'git remote add new ssh://git@gitlab.test.com/auto/"${REPO_PATH}"'
repo forall -r kernel -c 'git remote set-url new ssh://git@gitlab.test.com/auto/kernel-4.14'
repo forall -c git remote -vv
repo forall -c git checkout -b $2
repo forall -c git push new $2:$2
