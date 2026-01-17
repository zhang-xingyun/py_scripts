import datetime
import logging
from abc import ABCMeta, abstractmethod
from typing import Dict, List, Optional

from fordring.atlassian import Jira

from hdflow.work_report.enum import IssueLinkType, IssueNoMeanKey

LAST_ISSUE_KEY = "JIRA-LastIssue"
NO_EPIC_ISSUE_KEY = "JIRA-NoEpic"
NO_STORY_ISSUE_KEY = "JIRA-NoStory"
NO_TASK_ISSUE_KEY = "JIRA-NoTask"


USELESS_KEY = [
    LAST_ISSUE_KEY,
    NO_EPIC_ISSUE_KEY,
    NO_STORY_ISSUE_KEY,
    NO_TASK_ISSUE_KEY,
]

NO_STATUS = "No-Status"
NO_PRIORITY = "No-Priority"

OBJECT_TYPE_PREFIX = "[SensingCICD][ObjType]"
ROOT_CAUSE_PREFIX = "[SensingCICD][RootCause]"


def info_from_tags(tags, prefix):
    res = list()
    for tag in tags:
        if tag.startswith(prefix):
            res.append(tag.replace(prefix, ""))
    return res


logger = logging.getLogger(__name__)


class IssueBase(metaclass=ABCMeta):
    jira_client = None

    def __init__(self, issue: Dict, jira_client: Jira):
        self._issue = issue
        self.issue_key: str
        self.summary: str
        self.issuetype: str
        self.reporter: Dict
        self.assignee: Dict
        self.priority: str
        self.status: str
        self.labels: List[str]
        self.objtypes: List[str]
        self.rootcauses: List[str]
        self.planstart: Optional[datetime.datetime] = None
        self.planend: Optional[datetime.datetime] = None
        self.created: Optional[datetime.datetime] = None
        self._progress: Optional[List[Dict]] = None
        self._attachments: Optional[List[Dict]] = None
        self._init_attrs()
        self.level = 1
        self._changelogs: Optional[List[Dict]] = None
        self.mark_time = datetime.datetime.now()
        if IssueBase.jira_client is None:
            IssueBase.jira_client = jira_client

    def __lt__(self, other):
        if self.issuetype == other.issuetype:
            return self.issue_key < other.issue_key

        return self.issuetype < other.issuetype

    def _init_attrs(self):
        self.issue_key = self._issue["key"]

        fields = self._issue["fields"]
        self.summary = fields["summary"]
        self.issuetype = fields["issuetype"]["name"]
        self.reporter = {
            "name": fields["reporter"]["name"],
            "email": fields["reporter"]["emailAddress"],
        }
        self.assignee = {
            "name": fields["assignee"]["name"]
            if fields.get("assignee")
            else "",
            "email": fields["assignee"]["emailAddress"]
            if fields.get("assignee")
            else "",
        }
        self.priority = fields["priority"]["name"]
        self.status = fields["status"]["name"]

        self.labels = fields["labels"]
        self.objtypes = info_from_tags(self.labels, OBJECT_TYPE_PREFIX)
        self.rootcauses = info_from_tags(self.labels, ROOT_CAUSE_PREFIX)

        created = fields["created"]
        self.created = (
            created
            if created is None
            else datetime.datetime.strptime(
                created[: created.rfind(".")], "%Y-%m-%dT%H:%M:%S"
            )
        )

        planstart = fields.get(IssueNoMeanKey.PlanStart.value)
        self.planstart = (
            planstart
            if planstart is None
            else datetime.datetime.strptime(planstart, "%Y-%m-%d")
        )

        planend = fields.get(IssueNoMeanKey.PlanEnd.value)
        self.planend = (
            planend
            if planend is None
            else datetime.datetime.strptime(planend, "%Y-%m-%d")
        )

    @property
    def attachments(self):
        if self._attachments is None:
            fields = self._issue["fields"]
            attachments = fields.get("attachment", {})
            self._attachments = {}
            for attachment in attachments:
                if "mimeType" not in attachment:
                    continue
                if "image" not in attachment["mimeType"]:
                    continue
                try:
                    attachment_bytes = IssueBase.jira_client.get(
                        path=attachment["content"],
                        absolute=True,
                        not_json_response=True,
                    )
                except Exception as e:
                    logger.error(
                        f"get out image {attachment['content']}: {e}"
                    )  # noqa
                    self._attachments[attachment["filename"]] = None
                else:
                    self._attachments[attachment["filename"]] = {
                        "id": attachment["id"],
                        "name": attachment["filename"],
                        "content": attachment["content"],
                        "mimeType": attachment["mimeType"],
                        "size": attachment["size"],
                        "bytes": attachment_bytes,
                    }
        return self._attachments

    @property
    def progress(self):
        if self._progress is None:
            fields = self._issue["fields"]
            worklog = fields.get("worklog", {})
            self._progress = []
            if worklog and worklog["maxResults"] < worklog["total"]:
                worklog = IssueBase.jira_client.issue_get_worklog(
                    self.issue_key
                )
            worklogs = worklog.get("worklogs", [])
            for worklog in worklogs:
                comment_text = worklog["comment"]
                comment_time = worklog["created"]
                comment_author = worklog["author"]["name"]
                comment_timespent = worklog["timeSpent"]
                comment_time = datetime.datetime.strptime(
                    comment_time[: comment_time.rfind(".")],
                    "%Y-%m-%dT%H:%M:%S",
                )
                self._progress.append(
                    {
                        "text": f"TimeSpent: {comment_timespent}\n{comment_text}",  # noqa
                        "time": comment_time,
                        "author": comment_author,
                    }
                )

            comment = fields.get("comment", {})
            comments = comment.get("comments", [])
            for comment in comments:
                comment_text = comment.get("body", "")
                comment_time = comment["created"]
                comment_author = comment["author"]["name"]
                comment_time = datetime.datetime.strptime(
                    comment_time[: comment_time.rfind(".")],
                    "%Y-%m-%dT%H:%M:%S",
                )
                self._progress.append(
                    {
                        "text": comment_text,
                        "time": comment_time,
                        "author": comment_author,
                    }
                )

            self._progress.sort(key=lambda x: x["time"], reverse=True)
        return self._progress

    @progress.setter
    def progress(self, value: List[Dict]):
        self._progress = value

    @property
    def changelogs(self):
        if self._changelogs is None:
            issue_info = IssueBase.jira_client.issue(
                self.issue_key, expand="changelog"
            )
            histories = issue_info["changelog"].get("histories", [])
            self._changelogs = []
            for history in histories:
                update_time = history["created"]
                update_time = datetime.datetime.strptime(
                    update_time[: update_time.rfind(".")], "%Y-%m-%dT%H:%M:%S"
                )
                items = history.get("items", [])
                for item in items:
                    item.update(update_time=update_time)
                    self._changelogs.append(item)
            self._changelogs.sort(
                key=lambda x: x["update_time"], reverse=True
            )  # noqa
        return self._changelogs

    def back(self, back_time: datetime.datetime):
        """Backtracking issue status and priority."""
        fields = self._issue["fields"]
        self.status = fields["status"]["name"]
        self.priority = fields["priority"]["name"]

        if back_time < self.created:
            self.status = NO_STATUS
            self.priority = NO_PRIORITY
            return

        if self.mark_time <= back_time:
            return

        mark_key = "toString"
        back_key = "fromString"
        changelogs = filter(
            lambda x: back_time < x["update_time"] < self.mark_time,
            self.changelogs,
        )
        for changelog in changelogs:
            if (
                changelog["field"] == "status"
                and changelog[mark_key] == self.status
            ):
                self.status = changelog[back_key]
            elif (
                changelog["field"] == "priority"
                and changelog[mark_key] == self.priority
            ):
                self.priority = changelog[back_key]

        self.mark_time = back_time

    @abstractmethod
    def get_parent_key(self):
        pass

    @abstractmethod
    def get_children_key(self):
        pass


class Task(IssueBase):
    def __init__(self, issue: Dict, jira_client: Jira):
        super(Task, self).__init__(issue, jira_client)

    def get_parent_key(self):
        fields = self._issue["fields"]
        parent_key = []
        issuelinks = fields.get("issuelinks", [])
        for issuelink in issuelinks:
            issuelink_fields = issuelink.get("inwardIssue")
            if issuelink_fields is None:
                continue
            issuelink_type = issuelink["type"]["id"]
            if issuelink_type != IssueLinkType.Contain.value:
                continue
            parent_key.append(issuelink_fields["key"])
        if not parent_key:
            epic_key = fields.get(
                IssueNoMeanKey.EpicKey.value, NO_STORY_ISSUE_KEY
            )
            if epic_key is not None:
                parent_key.append(epic_key)

        return parent_key if parent_key else [NO_STORY_ISSUE_KEY]

    def get_children_key(self):
        return [NO_TASK_ISSUE_KEY]


class Sub_task(Task):  # noqa
    def __init__(self, issue: Dict, jira_client: Jira):
        super(Sub_task, self).__init__(issue, jira_client)


class Bug(Task):
    def __init__(self, issue: Dict, jira_client: Jira):
        super(Bug, self).__init__(issue, jira_client)


class Simple_Bug(Task):  # noqa
    def __init__(self, issue: Dict, jira_client: Jira):
        super(Simple_Bug, self).__init__(issue, jira_client)


class Badcase(Task):
    def __init__(self, issue: Dict, jira_client: Jira):
        super(Badcase, self).__init__(issue, jira_client)


class OR(Task):
    def __init__(self, issue: Dict, jira_client: Jira):
        super(OR, self).__init__(issue, jira_client)


class Story(IssueBase):
    def __init__(self, issue: Dict, jira_client: Jira):
        super(Story, self).__init__(issue, jira_client)

    def get_parent_key(self):
        fields = self._issue["fields"]
        parent_key = []
        issuelinks = fields.get("issuelinks", [])
        for issuelink in issuelinks:
            issuelink_fields = issuelink.get("inwardIssue")
            if issuelink_fields is None:
                continue
            issuelink_type = issuelink["type"]["id"]
            if issuelink_type != IssueLinkType.Contain.value:
                continue
            parent_key.append(issuelink_fields["key"])
        if not parent_key:
            epic_key = fields.get(
                IssueNoMeanKey.EpicKey.value, NO_EPIC_ISSUE_KEY
            )
            if epic_key is not None:
                parent_key.append(epic_key)

        return parent_key if parent_key else [NO_EPIC_ISSUE_KEY]

    def get_children_key(self):
        fields = self._issue["fields"]
        children_key = []
        issuelinks = fields.get("issuelinks", [])
        for issuelink in issuelinks:
            issuelink_fields = issuelink.get("outwardIssue")
            if issuelink_fields is None:
                continue
            issuelink_type = issuelink["type"]["id"]
            if issuelink_type != IssueLinkType.Contain.value:
                continue
            children_key.append(issuelink_fields["key"])

        return children_key if children_key else [NO_TASK_ISSUE_KEY]


class Epic(IssueBase):
    def __init__(self, issue: Dict, jira_client: Jira):
        super(Epic, self).__init__(issue, jira_client)

    def get_parent_key(self):
        return [LAST_ISSUE_KEY]

    def get_children_key(self):
        return [NO_STORY_ISSUE_KEY]
