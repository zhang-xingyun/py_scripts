该功能是用于添加自己的mr策略到gitlab
目前功能是指定仓库的指定分支可以配置指定人员mr
该功能是修改gitlab源码

merge_request_check_hobot.rb 文件需要放在指定的位置:

  /opt/gitlab/embedded/service/gitlab-rails/lib/gitlab/merge_request_check_hobot.rb

merge_request.rb 文件时gitlab源码文件需要在指定的地方添加自己的逻辑

  /opt/gitlab/embedded/service/gitlab-rails/app/models/merge_request.rb

```
  def can_be_merged_by?(user)
    access = ::Gitlab::UserAccess.new(user, project: project)
    access.can_update_branch?(target_branch)
    hobotObj = ::Gitlab::MergeRequestCheckHobot.new(project.id, target_branch, author.name, user.name)
    hobotObj.check
  end
```
需要在指定位置配置yaml配置文件才能生效
目录/home/git/data/custom_hooks/config/mr
文件名以repo id开头，.yaml结尾，
example：
/home/git/data/custom_hooks/config/mr/1.yaml


配置功能参考：http://wiki.test.com/pages/viewpage.action?pageId=196217300