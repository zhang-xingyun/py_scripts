import datetime
from typing import Dict, Optional

from fordring.atlassian import Jira
from fordring.feishu.doc_data import (
    Block,
    Body,
    Document,
    MergedCell,
    Table,
    TableRow,
    Title,
)
from hatbc.resource_manager import get_resource

from hdflow.work_report.create_feishu_dosc_json_base import (
    _create_textrun_tablecell,
)
from hdflow.work_report.enum import IssueStatus
from hdflow.work_report.jira_badcase_report import (
    JiraBadcaseReport,
    badcase_objtype_rootcause_statistics,
    filter_change_status_issue,
)

__all__ = ["jira_badcase_progress_report_to_feishu_doc"]


def _init_feishu_table():
    column_infos = [
        {"name": "项目\\状态", "width": 300},
        {"name": "方向", "width": 100},
        {"name": "待研发定位总数量", "width": 150},
        {"name": "Root Cause", "width": 200},
        {"name": "本周处理数量（从待研发定位变更为研发解决中）", "width": 150},
        {"name": "研发解决中总数量", "width": 150},
    ]
    table = Table(
        columnsize=len(column_infos),
        columnwidth=[column_info["width"] for column_info in column_infos],
    )
    table.insert_row(
        tablerow=TableRow(
            tableCells=[
                _create_textrun_tablecell(
                    text=column_info["name"], bold=True, align="center"
                )
                for column_info in column_infos
            ]
        )
    )
    return table


def _add_feishu_table_row(
    table: Optional[Table],
    project_name: str,
    begin_time: Optional[datetime.datetime],
    end_time: Optional[datetime.datetime],
    jira_url_prefix: str,
    objtype: str = "",
    rootcause: str = "",
    badcase_list: Optional[Dict] = None,
):
    jira_jql_link = "{url}/issues/?jql=issuekey in ({issue_keys})"
    waiting_badcases = []
    wokring_badcases = []
    if badcase_list is not None:
        for badcase in badcase_list:
            if badcase.status in [
                IssueStatus.Waiting_RD_cn.value,
                IssueStatus.To_do.value,
                IssueStatus.Reopen.value,
            ]:
                waiting_badcases.append(badcase)
            elif badcase.status in [
                IssueStatus.Solving_RD_cn.value,
                IssueStatus.Working.value,
            ]:
                wokring_badcases.append(badcase)

        waiting_to_wokring_issues = filter_change_status_issue(
            issues=wokring_badcases,
            from_status=[
                IssueStatus.Waiting_RD_cn.value,
                IssueStatus.To_do.value,
                IssueStatus.Reopen.value,
            ],
            to_status=[
                IssueStatus.Solving_RD_cn.value,
                IssueStatus.Working.value,
            ],
            begin_time=begin_time,
            end_time=end_time,
        )

    table.insert_row(
        tablerow=TableRow(
            tableCells=[
                _create_textrun_tablecell(
                    text=project_name,
                    bold=True,
                    align="center",
                ),
                _create_textrun_tablecell(text=objtype),
                _create_textrun_tablecell(
                    text=str(len(waiting_badcases)),
                    link=jira_jql_link.format(
                        url=jira_url_prefix,
                        issue_keys=", ".join(
                            [issue.issue_key for issue in waiting_badcases]
                        ),
                    ),
                ),
                _create_textrun_tablecell(text=rootcause),
                _create_textrun_tablecell(
                    text=str(len(waiting_to_wokring_issues)),
                    link=jira_jql_link.format(
                        url=jira_url_prefix,
                        issue_keys=", ".join(
                            [
                                issue.issue_key
                                for issue in waiting_to_wokring_issues
                            ]
                        ),
                    ),
                ),
                _create_textrun_tablecell(
                    text=str(len(wokring_badcases)),
                    link=jira_jql_link.format(
                        url=jira_url_prefix,
                        issue_keys=", ".join(
                            [issue.issue_key for issue in wokring_badcases]
                        ),
                    ),
                ),
            ]
        )
    )


def _create_content_blocks(
    jira_badcase_set: Dict,
    begin_time: Optional[datetime.datetime],
    end_time: Optional[datetime.datetime],
    jira_url_prefix: str,
):
    table = _init_feishu_table()
    for project_name, jira_badcases in jira_badcase_set.items():
        badcase_list = []
        for badcases in jira_badcases.values():
            badcase_list.extend(badcases)
        results = badcase_objtype_rootcause_statistics(
            badcase_list=badcase_list
        )
        results = sorted(results.items(), key=lambda x: x[0])
        project_row_index = 0
        for objtype, rootcauses in results:
            for rootcause, badcase_list in rootcauses.items():
                _add_feishu_table_row(
                    table=table,
                    project_name=project_name,
                    objtype=objtype,
                    rootcause=rootcause,
                    badcase_list=badcase_list,
                    jira_url_prefix=jira_url_prefix,
                    begin_time=begin_time,
                    end_time=end_time,
                )
            table.append_mergedcell(
                MergedCell(
                    rowStartIndex=table.rowSize - len(rootcauses),
                    rowEndIndex=table.rowSize,
                    columnStartIndex=1,
                    columnEndIndex=2,
                )
            )
            project_row_index += len(rootcauses)
        if project_row_index:
            table.append_mergedcell(
                MergedCell(
                    rowStartIndex=table.rowSize - project_row_index,
                    rowEndIndex=table.rowSize,
                    columnStartIndex=0,
                    columnEndIndex=1,
                )
            )
        else:
            _add_feishu_table_row(
                table=table,
                project_name=project_name,
                jira_url_prefix=jira_url_prefix,
            )

    return Block(type="table", table=table)


def jira_badcase_progress_report_to_feishu_doc(
    jira_badcase_report: JiraBadcaseReport,
    begin_time: Optional[datetime.datetime],
    end_time: Optional[datetime.datetime],
    jira_url_prefix: str = None,
    jira_client: Optional[Jira] = None,
):

    if jira_url_prefix is None:
        if jira_client is None:
            jira_client = get_resource(Jira)
        jira_url_prefix = jira_client.url

    body = Body(
        blocks=[
            _create_content_blocks(
                jira_badcase_set=jira_badcase_report.jira_badcase_set,
                begin_time=begin_time,
                end_time=end_time,
                jira_url_prefix=jira_url_prefix,
            )
        ]
    )

    return Document(
        title=Title(
            title=f"{jira_badcase_report.title} {begin_time.strftime('%Y-%m-%d')}~{end_time.strftime('%Y-%m-%d')}"  # noqa
        ),
        body=body,
    )
