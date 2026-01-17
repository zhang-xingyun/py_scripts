import datetime
import re
from queue import LifoQueue, Queue
from typing import Dict, List, Optional, Union

from fordring.atlassian import Jira
from hatbc.resource_manager import get_resource

from hdflow.work_report import jira_type
from hdflow.work_report.enum import IssueStatus, IssueType
from hdflow.work_report.jira_type import USELESS_KEY, IssueBase


def create_issue_info(issue: Dict, jira_client: Jira):
    task = issue["fields"]
    issuetype = task["issuetype"]
    issuetype = issuetype["name"]
    classtype = getattr(jira_type, issuetype.replace("-", "_"), None)
    if classtype is None:
        return None
    return classtype(issue, jira_client)


class JiraWorkReport:
    def __init__(
        self,
        title: str,
        filter_ids: List[int],
        create_time: datetime.datetime,
        progress_latest: bool,
        start_time: Optional[datetime.datetime] = None,
        end_time: Optional[datetime.datetime] = None,
        issue_info_list: Optional[List[IssueBase]] = None,
    ):
        self.title = title
        self.filter_ids = filter_ids
        self.start_time = start_time
        self.end_time = end_time
        self.create_time = create_time
        self.progress_latest = progress_latest
        if issue_info_list is None:
            self.issue_info_list = []
        else:
            self.issue_info_list = issue_info_list

    def append(self, issue_info: IssueBase):
        self.issue_info_list.append(issue_info)

    def pop(self, index: int):
        return self.issue_info_list.pop(index)

    def title_with_time(self, daytime: Optional[datetime.datetime] = None):
        if self.start_time is None or self.end_time is None:
            if daytime is None:
                return self.title
            else:
                daytime = daytime.strftime("%Y-%m-%d")
                return f"{self.title} {daytime}"
        else:
            start_time = self.start_time.strftime("%Y-%m-%d")
            end_time = self.end_time.strftime("%Y-%m-%d")
            if start_time == end_time:
                return f"{self.title} {start_time}"
            else:
                return f"{self.title} {start_time}~{end_time}"


class IssueGraph:
    def __init__(
        self,
        status_filter: Dict = None,
        selected_user_filter: List[str] = None,
        unselected_user_filter: List[str] = None,
    ):
        self.issues = {}
        self.edges = {}
        self.status_filter = status_filter
        self.selected_user_filter = selected_user_filter
        self.unselected_user_filter = unselected_user_filter

    def issue_in_graph(self, issue: Union[IssueBase, str]):
        if isinstance(issue, IssueBase):
            issue_key = issue.issue_key
        else:
            issue_key = issue
        return issue_key in self.issues

    def add_issue(self, issue: IssueBase):
        if issue.issue_key not in self.issues:
            self.issues[issue.issue_key] = issue

    def add_edges(
        self,
        parent_issue: Union[IssueBase, str],
        children_issue: Union[IssueBase, str],
    ):
        if isinstance(parent_issue, IssueBase):
            parent_issue_key = parent_issue.issue_key
        else:
            parent_issue_key = parent_issue

        if isinstance(children_issue, IssueBase):
            children_issue_key = children_issue.issue_key
        else:
            children_issue_key = children_issue

        if parent_issue_key not in self.edges:
            self.edges[parent_issue_key] = []
        if children_issue_key not in self.edges[parent_issue_key]:
            self.edges[parent_issue_key].append(children_issue_key)

    def check_issue(self, issue: IssueBase):
        if (
            self.selected_user_filter is not None
            and issue.assignee["name"] not in self.selected_user_filter
        ):
            return False

        if (
            self.unselected_user_filter is not None
            and issue.assignee["name"] in self.unselected_user_filter
        ):
            return False

        if (
            self.status_filter is not None
            and issue.issuetype not in self.status_filter
        ):
            return False

        if (
            self.status_filter[issue.issuetype] is not None
            and issue.status not in self.status_filter[issue.issuetype]
        ):
            return False

        return True

    def create_graph_from_issues(
        self, issues, jira_client: Optional[Jira] = None
    ):
        if jira_client is None:
            jira_client = get_resource(Jira)

        original_keys = []
        issue_queue = Queue()
        for issue in issues:
            issue_info = create_issue_info(issue, jira_client)
            if issue_info is None:
                continue
            if not self.check_issue(issue_info):
                continue
            original_keys.append(issue_info.issue_key)
            issue_queue.put(issue_info)

        while not issue_queue.empty():
            issue_info = issue_queue.get()
            self.add_issue(issue_info)
            parent_keys = issue_info.get_parent_key()
            mark_keys = [key for key in parent_keys if key in original_keys]
            if mark_keys:
                parent_keys = mark_keys
            for key in parent_keys:
                if not self.issue_in_graph(key) and key not in USELESS_KEY:
                    parent_issue = create_issue_info(
                        jira_client.issue(key), jira_client
                    )
                    if parent_issue is None:
                        continue
                    if not self.check_issue(parent_issue):
                        continue
                    issue_queue.put(parent_issue)
                    self.add_issue(parent_issue)
                self.add_edges(key, issue_info)

            children_keys = issue_info.get_children_key()
            mark_keys = [key for key in children_keys if key in original_keys]
            if mark_keys:
                children_keys = mark_keys
            for key in children_keys:
                if key in USELESS_KEY:
                    continue
                if not self.issue_in_graph(key):
                    children_issue = create_issue_info(
                        jira_client.issue(key), jira_client
                    )
                    if children_issue is None:
                        continue
                    if not self.check_issue(children_issue):
                        continue
                    issue_queue.put(children_issue)
                    self.add_issue(children_issue)
                self.add_edges(issue_info, key)

    def get_issue_dfs_sequence(self):
        issue_dfs_sequence = []
        issue_queue = LifoQueue()

        for key in USELESS_KEY:
            issue_queue.put((key, 0))

        while not issue_queue.empty():
            issue_key, level = issue_queue.get()
            if issue_key not in USELESS_KEY:
                issue_info = self.issues[issue_key]
                issue_info.level = level

                if (
                    issue_info.issuetype != IssueType.Task.value
                    and issue_key not in self.edges
                ):
                    continue

                issue_dfs_sequence.append(issue_info)

            if issue_key not in self.edges:
                continue

            self.edges[issue_key].sort(key=lambda x: self.issues[x])
            for key in self.edges[issue_key]:
                issue_queue.put((key, level + 1))

        return issue_dfs_sequence


def progress_filter(
    issue_info_list: List[IssueBase],
    start_time: Optional[Union[str, datetime.datetime]] = None,
    end_time: Optional[Union[str, datetime.datetime]] = None,
    progress_latest: bool = True,
    progress_regexp: str = "【进展】",
):
    filter_start_time = start_time if start_time else datetime.datetime.min
    filter_end_time = end_time if end_time else datetime.datetime.max

    for issue_info in issue_info_list:
        issue_info.progress = list(
            filter(
                lambda x: filter_start_time <= x.get("time") <= filter_end_time
                and (
                    re.search(progress_regexp, x.get("text")) is not None
                    or x.get("text").startswith("TimeSpent")
                ),
                issue_info.progress,
            )
        )
        if progress_latest and issue_info.progress:
            issue_info.progress = issue_info.progress[0:1]

    return issue_info_list


def generate_jira_work_report(
    title: str,
    filter_ids: List[int],
    start_time: Optional[Union[str, datetime.datetime]] = None,
    end_time: Optional[Union[str, datetime.datetime]] = None,
    epic_status: List[Union[IssueStatus, str]] = None,
    story_status: List[Union[IssueStatus, str]] = None,
    task_status: List[Union[IssueStatus, str]] = None,
    selected_user_filter: List[str] = None,
    unselected_user_filter: List[str] = None,
    progress_latest: bool = True,
    progress_regexp: str = "【进展】",
    jira_client: Optional[Jira] = None,
    start: int = 0,
    limit: int = 1000,
):
    """Generate JiraWorkReport.

    Parameters
    ----------
    title : str
        jira work report title.
    filter_ids : List[int]
        jira filter_id list.
    start_time : str, datetime.datetime
        The start time of jira progress to be obtained,
        by default datetime.datetime.min.
    end_time : str, datetime.datetime
        The end time of jira progress to be obtained,
        by default datetime.datetime.max.
    epic_status: List[Union[IssueStatus, str]]
        The status of the Epic to be obtained, by default None.
    story_status : List[Union[IssueStatus, str]]
        The status of the Story to be obtained, by default None.
    task_status : List[Union[IssueStatus, str]]
        The status of the Task to be obtained, by default None.
    selected_user_filter: List[str]
        selected user, by default None.
    unselected_user_filter: List[str]
        selected user, by default None.
    progress_latest : bool
        Only get the latest progress, by default True.
    progress_regexp : str
        progess regexp, by default "【进展】".
    jira_client : Jira
        fordring.atlassian.Jira
    start : int
        Jira.jql start index
    limit : int
        Jira.jql limit

    Returns
    -------
    jira_work_report : :py:class:`JiraWorkReport`
        JiraWorkReport.issue_info_list : :jira_type.py:class:`IssueBase`
            jira tree structure pre-order results
            Use IssueBase.level to identify levels
    e.g.
              Epic0                Epic1
             /    |               /    |
        Story00  Story01    Story10  Story11
        /    |                |         |
    task000 task001         task101  task111

    JiraWorkReport.issue_info_list = [
        Epic0,      # level=1
        Story00,    # level=2
        Task000,    # level=3
        task001,    # level=3
        Story01,    # level=2
        Epic1,      # level=1
        Story10,    # level=2
        task101,    # level=3
        Story11,    # level=2
        Task111,    # level=3
    ]
    """

    if jira_client is None:
        jira_client = get_resource(Jira)

    if isinstance(start_time, str):
        start_time = datetime.datetime.strptime(
            start_time, "%Y-%m-%d %H:%M:%S"
        )
    if isinstance(end_time, str):
        end_time = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")

    epic_status = (
        [IssueStatus.value_of(status) for status in epic_status]
        if epic_status
        else None
    )
    story_status = (
        [IssueStatus.value_of(status) for status in story_status]
        if story_status
        else None
    )
    task_status = (
        [IssueStatus.value_of(status) for status in task_status]
        if task_status
        else None
    )

    status_filter = {
        IssueType.Epic.value: epic_status,
        IssueType.Story.value: story_status,
        IssueType.Task.value: task_status,
    }

    issue_graph = IssueGraph(
        status_filter=status_filter,
        selected_user_filter=selected_user_filter,
        unselected_user_filter=unselected_user_filter,
    )

    for filter_id in filter_ids:
        jql = jira_client.get_filter(filter_id).get("jql")
        result = jira_client.jql(jql, start=start, limit=limit)
        issues = result.get("issues", [])
        issue_graph.create_graph_from_issues(issues)

    issue_info_list = issue_graph.get_issue_dfs_sequence()

    issue_info_list = progress_filter(
        issue_info_list=issue_info_list,
        start_time=start_time,
        end_time=end_time,
        progress_latest=progress_latest,
        progress_regexp=progress_regexp,
    )

    return JiraWorkReport(
        title=title,
        filter_ids=filter_ids,
        create_time=datetime.datetime.now(),
        progress_latest=progress_latest,
        start_time=start_time,
        end_time=end_time,
        issue_info_list=issue_info_list,
    )
