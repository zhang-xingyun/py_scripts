from typing import List, Optional, Union

from fordring import feishu
from fordring.atlassian import Jira
from fordring.feishu import Session
from fordring.feishu.post import Post, PostAtItem, PostLinkItem, PostTextItem
from hatbc.resource_manager import get_resource
from hatbc.workflow.trace import make_traceable

from hdflow.work_report.enum import IssueStatus, IssueType
from hdflow.work_report.jira_work_report import JiraWorkReport

__all__ = [
    "feishu_notifies_task_worklogs_statistics",
]


@make_traceable
def feishu_notifies_task_worklogs_statistics(
    bot_token: str,
    jira_work_report: JiraWorkReport,
    task_status: List[Union[IssueStatus, str]] = None,
    document_link: str = None,
    session: Optional[Session] = None,
    jira_client: Optional[Jira] = None,
):
    """Feishu task worklogs statistics.

    Parameters
    ----------
    bot_token : str
        Feishu roboot token.
    jira_work_report : JiraWorkReport
        hdflow.work_report.jira_work_report.JiraWorkReport.
    task_status : List[Union[IssueStatus, str]]
        Need to get task status, by default None.
    document_link : str
        document feishu token link, by default None.
    session : Optional[Session]
        fordring.feishu.session, by default None.
    jira_client : Optional[Jira]
        fordring.atlassian.Jira, by default None.

    Returns
    -------
    ret : Dict
        Response result
    """
    if jira_client is None:
        jira_client = get_resource(Jira)

    if session is None:
        session = get_resource(Session)

    assignee_worklog_statistics = {}
    task_status = [IssueStatus.value_of(status) for status in task_status]
    for issue_info in jira_work_report.issue_info_list:
        if issue_info.issuetype != IssueType.Task.value:
            continue

        if issue_info.assignee["name"] not in assignee_worklog_statistics:
            assignee_worklog_statistics[issue_info.assignee["name"]] = {
                "email": issue_info.assignee["email"],
                "task_work": set(),
                "no_task_work": set(),
                "task_total": set(),
            }

        if issue_info.progress:
            assignee_worklog_statistics[issue_info.assignee["name"]][
                "task_work"
            ].add(issue_info.issue_key)

        if task_status is not None and issue_info.status not in task_status:
            continue

        if not issue_info.progress:
            assignee_worklog_statistics[issue_info.assignee["name"]][
                "no_task_work"
            ].add(issue_info.issue_key)

        assignee_worklog_statistics[issue_info.assignee["name"]][
            "task_total"
        ].add(issue_info.issue_key)

    # Work statistics are in the order from large to small.
    assignees_rank = sorted(
        assignee_worklog_statistics,
        key=lambda x: (len(assignee_worklog_statistics[x]["task_work"]), x),
        reverse=True,
    )

    work_assignees = []
    no_work_assigness = []
    for user_name in assignees_rank:
        worklog_info = assignee_worklog_statistics[user_name]
        if (
            len(worklog_info["task_total"]) + len(worklog_info["task_work"])
            == 0
        ):
            continue
        if worklog_info["task_work"]:
            work_assignees.append(user_name)
        else:
            no_work_assigness.append(user_name)
    assignees_total = {"未更新": no_work_assigness, "已更新": work_assignees}

    content = []
    if document_link:
        content.append(
            [
                PostTextItem(text="日报："),
                PostLinkItem(
                    text=jira_work_report.title_with_time(), href=document_link
                ),
            ]
        )
    if len(work_assignees) + len(no_work_assigness) != 0:
        content.append(
            [
                PostTextItem(
                    text=f"填写率：{round(len(work_assignees) / (len(work_assignees) + len(no_work_assigness)) * 100, 2)}%（填写人数 / 总人数）"  # noqa
                ),
            ],
        )
    content.append([])
    content.append(
        [
            PostTextItem(text="个人更新情况："),
        ],
    )
    content.append(
        [
            PostTextItem(text="（未更新数 / 实际更新数 / 需更新数）"),
        ],
    )

    jira_jql_link = "{url}/issues/?jql=issuekey in ({issue_keys})"
    for assignee_type, assignees in assignees_total.items():
        if len(assignees) == 0:
            continue
        content.append(
            [
                PostTextItem(
                    text=f"-------------------{assignee_type}------------------"  # noqa
                ),
            ],
        )
        for user_name in assignees:
            worklog_info = assignee_worklog_statistics[user_name]
            resp = feishu.user.get_user_id(
                emails=[worklog_info["email"]],
                session=session,
            )
            feishu.check_success(resp)
            user_id = resp["data"]["user_list"][0].get("user_id", None)
            # External users cannot find user_id
            if user_id is not None:
                resp = feishu.user.get_user_info(
                    user_id=user_id,
                    session=session,
                )
                feishu.check_success(resp)
                user_name = resp["data"]["user"]["name"]

            content.append(
                [
                    PostTextItem(text=user_name)
                    if worklog_info["task_work"] or not user_id
                    else PostAtItem(user_id=user_id),
                    PostTextItem(text="："),
                    PostLinkItem(
                        text=str(len(worklog_info["no_task_work"])),
                        href=jira_jql_link.format(
                            url=jira_client.url,
                            issue_keys=", ".join(worklog_info["no_task_work"]),
                        ),
                    ),
                    PostTextItem(text=" / "),
                    PostLinkItem(
                        text=str(len(worklog_info["task_work"])),
                        href=jira_jql_link.format(
                            url=jira_client.url,
                            issue_keys=", ".join(worklog_info["task_work"]),
                        ),
                    ),
                    PostTextItem(text=" / "),
                    PostLinkItem(
                        text=str(len(worklog_info["task_total"])),
                        href=jira_jql_link.format(
                            url=jira_client.url,
                            issue_keys=", ".join(worklog_info["task_total"]),
                        ),
                    ),
                ]
            )
    feishu_post = Post(
        title=jira_work_report.title_with_time(),
        content=content,
    )
    resp = feishu.bot.send_msg(feishu_post, bot_token)
    feishu.check_success(resp)
    return resp
