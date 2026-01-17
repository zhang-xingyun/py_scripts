from hatbc.utils import Enum


class IssueType(Enum):
    Epic = "Epic"
    Story = "Story"
    Task = "Task"
    Bug = "Bug"
    Badcase = "Badcase"
    Simple_bug = "Simple_Bug"
    Or = "OR"


class IssueStatus(Enum):
    New = "New"
    To_do = "To Do"
    Reviewed = "reviewed"
    Open = "open"
    Reopen = "Reopen"
    Working = "Working"
    Resolved = "Resolved"
    Finished = "Finished"
    Verified = "Verified"
    Pending = "Pending"
    Feedback = "Feedback"
    Closed_rejected = "Closed - Rejected"
    Closed_done = "Closed - Done"

    Waiting_open_cn = "待启动"
    Waiting_RD_cn_old = "待研发定位"
    Waiting_RD_cn = "待研发确定"
    Solving_RD_cn = "研发解决中"
    Verified_cn = "验证中"
    Wait_verified_cn = "待持续验证"
    Rewrite_cn = "重新填写"
    Suspend_cn = "挂起"
    Non_problem_feedback_cn = "非问题反馈"
    Non_problem_closed_cn = "非问题关闭"
    Closed_done_cn = "问题解决关闭"


class IssuePriority(Enum):
    High = "High"
    Medium = "Medium"
    Low = "Low"


class IssueLinkType(Enum):
    Contain = "10406"


class IssueNoMeanKey(Enum):
    EpicKey = "customfield_10001"
    SeverityKey = "customfield_11221"
    PlanStart = "customfield_11307"
    PlanEnd = "customfield_11300"
    SpecializedClassificationKey = "customfield_13818"
