import datetime
import logging
import re
from typing import Dict, List, Optional, Union

from fordring.atlassian import Jira
from hatbc.resource_manager import get_resource

from hdflow.work_report import jira_type
from hdflow.work_report.enum import IssuePriority, IssueStatus
from hdflow.work_report.jira_type import IssueBase

logger = logging.getLogger(__name__)


def create_issue_info(issue: Dict, jira_client: Jira):
    task = issue["fields"]
    issuetype = task["issuetype"]
    issuetype = issuetype["name"]
    classtype = getattr(jira_type, issuetype.replace("-", "_"), None)
    if classtype is None:
        return None
    return classtype(issue, jira_client)


BadcaseStatusMap = {
    IssueStatus.Waiting_RD_cn.value: [
        IssueStatus.To_do.value,
        IssueStatus.Reopen.value,
        IssueStatus.Waiting_open_cn.value,
        IssueStatus.Waiting_RD_cn_old.value,
    ],
    IssueStatus.Solving_RD_cn.value: [IssueStatus.Working.value],
    IssueStatus.Verified_cn.value: [
        IssueStatus.Resolved.value,
        IssueStatus.Verified.value,
        IssueStatus.Wait_verified_cn.value,
    ],
    IssueStatus.Closed_done_cn.value: [IssueStatus.Closed_done.value],
}


def badcase_status_statistics(
    badcase_list: List[IssueBase],
    back_time: Optional[datetime.datetime] = None,
    badcase_status_map: Optional[Dict] = BadcaseStatusMap,
):
    if back_time is None:
        back_time = datetime.datetime.now()

    for issue_info in badcase_list:
        issue_info.back(back_time=back_time)

    results = {}
    badcase_map = {}
    for target_status, status_set in badcase_status_map.items():
        badcase_map[target_status] = target_status
        for status in status_set:
            badcase_map[status] = target_status

        results[target_status] = {}
        for priority in IssuePriority:
            results[target_status][priority.value] = []

    for issue_info in badcase_list:
        if issue_info.status not in badcase_map:
            continue
        results[badcase_map[issue_info.status]][issue_info.priority].append(
            issue_info.issue_key
        )
    return results


NO_ROOTCAUSE = "No Rootcause"
NO_OBJTYPE = "No Objtype"


def filter_change_status_issue(
    issues: List[IssueBase],
    from_status: List[str],
    to_status: List[str],
    begin_time: Optional[datetime.datetime],
    end_time: Optional[datetime.datetime],
):
    result = []
    for issue in issues:
        if issue.status not in to_status:
            continue

        changelogs = filter(
            lambda x: begin_time < x["update_time"] < end_time,
            issue.changelogs,
        )
        for changelog in changelogs:
            if changelog["field"] != "status":
                continue

            if (
                changelog["fromString"] in from_status
                and changelog["toString"] == issue.status
            ):
                result.append(issue)

    return result


def badcase_objtype_rootcause_statistics(badcase_list: List[IssueBase]):
    results = {}
    for badcase in badcase_list:
        for objtype in badcase.objtypes if badcase.objtypes else [NO_OBJTYPE]:
            if objtype not in results:
                results[objtype] = {}
            for rootcause in (
                badcase.rootcauses if badcase.rootcauses else [NO_ROOTCAUSE]
            ):
                if rootcause not in results[objtype]:
                    results[objtype][rootcause] = []
                results[objtype][rootcause].append(badcase)

    return results


def badcase_objtype_assignee_statistics(badcase_list: List[IssueBase]):
    results = {}
    for badcase in badcase_list:
        for objtype in badcase.objtypes if badcase.objtypes else [NO_OBJTYPE]:
            if objtype not in results:
                results[objtype] = {}
            assignee = badcase.assignee.get("email")
            if assignee not in results[objtype]:
                results[objtype][assignee] = []
            results[objtype][assignee].append(badcase)

    return results


class JiraBadcaseReport:
    def __init__(
        self,
        title: str,
        create_time: Optional[datetime.datetime] = None,
        domain_set: Optional[List[str]] = None,
        jira_badcase_set: Optional[
            Dict[str, Dict[str, List[IssueBase]]]
        ] = None,
    ):
        self.title = title
        if create_time is None:
            self.create_time = datetime.datetime.now()
        else:
            self.create_time = create_time
        if jira_badcase_set is None:
            self.jira_badcase_set = {}
        else:
            self.jira_badcase_set = jira_badcase_set

        if domain_set is None:
            self.domain_set = []
        else:
            self.domain_set = domain_set

    def title_with_time(self, daytime: datetime.datetime = None):
        if daytime is None:
            daytime = self.create_time.strftime("%Y-%m-%d")
        else:
            daytime = daytime.strftime("%Y-%m-%d")
        return f"{self.title} {daytime}"


def generate_badcase_work_report(
    title: str,
    filter_ids: List[int],
    create_time: Optional[Union[str, datetime.datetime]] = None,
    jira_client: Optional[Jira] = None,
    start: int = 0,
    limit: int = 1000,
):
    """Generate JiraBadcaseReport.

    Parameters
    ----------
    title : str
        jira work report title.
    filter_ids : List[int]
        jira filter_id list.
    create_time : List[str]
        jira badcase work report created time, by default None.
    jira_client : Jira
        fordring.atlassian.Jira
    start : int
        Jira.jql start index
    limit : int
        Jira.jql limit

    Returns
    -------
    jira_badcase_report : :py:class:`JiraBadcaseReport`
        JiraBadcaseReport.jira_badcase_set
    e.g.

    JiraWorkReport.jira_badcase_set = {
        project_name : {
            domain_name1 : List[IssueBase],
            domain_name2 : List[IssueBase],
            domain_name3 : List[IssueBase],
        }
    }
    """
    if jira_client is None:
        jira_client = get_resource(Jira)

    if isinstance(create_time, str):
        create_time = datetime.datetime.strptime(
            create_time, "%Y-%m-%d %H:%M:%S"
        )

    jira_badcase_set = {}
    domain_set = []
    for filter_id in filter_ids:
        jira_filter_info = jira_client.get_filter(filter_id)

        jira_name = jira_filter_info.get("name")
        match_result = re.match(r"(.*)?((（|\()(.*)(）|\)))", jira_name)
        if match_result:
            project_name = match_result.group(1)
            domain_name = match_result.group(4)
        else:
            project_name = domain_name = jira_name
        if domain_name not in domain_set:
            domain_set.append(domain_name)
        logger.info(
            f"filter id：{filter_id}, 项目名：{project_name}, 领域名：{domain_name}"
        )
        jql = jira_filter_info.get("jql")
        result = jira_client.jql(jql, start=start, limit=limit)
        issues = result.get("issues", [])
        issues = [create_issue_info(issue, jira_client) for issue in issues]

        if project_name not in jira_badcase_set:
            jira_badcase_set[project_name] = {}

        jira_badcase_set[project_name][domain_name] = issues

    return JiraBadcaseReport(
        title=title,
        create_time=create_time,
        jira_badcase_set=jira_badcase_set,
        domain_set=domain_set,
    )
