from jira import JIRA
from gitlab_app import models


def run():
    jira_conn = JIRA('https://jira.test.com:8443',
                     auth=('', ''))
    # 构建jira自定义字段 {id:名称} 字典
    filed_name_id_dict = dict()
    cfields = jira_conn.fields()
    for field in cfields:
        filed_name_id_dict[field['id']] = field

    projects = jira_conn.projects()
    for project in projects:
        # 只采集2023年以后的bug
        sql = 'project=' + project.key + ' AND Created >= "2024-1-1"'
        issues_in_proj = jira_conn.search_issues(sql, maxResults=-1)
        for issue in issues_in_proj:
            jira_id = issue.id
            raw = issue.raw
            fields = raw['fields']
            # 以字段名称作为key的所有字段信息字典
            filed_tmp = dict()
            skip = False
            for k, v in fields.items():
                # 与纪嫣静(Yanjing)确认，只需要采集bug类型的数据
                if k == 'issuetype' and 'Bug' != v.get('name', None):
                    skip = True
                    break
                if filed_name_id_dict.get(k, None):
                    f_name = filed_name_id_dict[k]['name']
                    filed_tmp[f_name] = v
                else:
                    filed_tmp[k] = v
            if skip:
                continue
            status = fields.get('status', dict()).get('name', None)
            bug_owner = None
            # 待研发确认、研发解决中状态的BUG，
            # 根据“Assignee”字段统计每个人的BUG数
            if status in ['待研发确认', '研发解决中']:
                bug_owner = fields.get("assignee", None)
                if not bug_owner:
                    continue
            # 挂起状态的BUG，根据“回退人”字段统计每个人的BUG数
            if status in ['挂起']:
                bug_owner = filed_tmp.get("回退人", None)
                if not bug_owner:
                    continue
            # 已解决待审核、待组织测试、验证中、待持续验证、
            # 问题解决关闭状态的BUG，根据“问题解决人”字段统计每个人的BUG数
            if status in ['已解决待审核', '待组织测试',
                          '验证中', '待持续验证', '问题解决关闭']:
                bug_owner = filed_tmp.get("问题解决人", None)

            if not bug_owner or not bug_owner.get('name', None):
                owner_name = "未设置"
            else:
                owner_name = bug_owner.get('name', None)
            bug = {
                "jira_id": jira_id,
                "project_key": fields['project']['key'],
                "issue_key": issue['key'],
                "proj_name": fields['project']['name'],
                "status": status,
                "created": fields['created'],
                "updated": fields['updated'],
                "owner": owner_name,
                "type": fields['issuetype']['name'],
            }
            try:
                models.JiraBug.objects.update_or_create(bug, jira_id=jira_id)
                print(f"插入数据：{bug}")
            except Exception:
                print(f"插入数据失败：{bug}")


if __name__ == '__main__':
    run()
