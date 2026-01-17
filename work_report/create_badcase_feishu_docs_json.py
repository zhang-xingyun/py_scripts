import datetime
from typing import Dict, List, Optional

from fordring.atlassian import Jira
from fordring.feishu.doc_data import (
    Block,
    Body,
    Document,
    MergedCell,
    RGBColor,
    Table,
    Title,
)
from hatbc.resource_manager import get_resource

from hdflow.work_report.create_feishu_dosc_json_base import (
    _create_textrun_tablecell,
)
from hdflow.work_report.enum import IssuePriority
from hdflow.work_report.jira_badcase_report import (
    BadcaseStatusMap,
    JiraBadcaseReport,
    badcase_status_statistics,
)

__all__ = ["jira_badcase_report_to_feishu_doc"]


def _create_statistics_tablecell(
    result: Dict,
    status: str,
    prioritys: List[str],
    jira_url_prefix: str,
    jira_jql_link: str,
    comparison_result: Optional[Dict] = None,
):
    comparison_size = 0
    issue_keys = []
    for priority in prioritys:
        issue_keys.extend(result[status][priority])
        if comparison_result is not None:
            comparison_size += len(comparison_result[status][priority])
    issue_size = len(issue_keys)

    signal_flag = ""
    backcolor = None
    if comparison_result is not None:
        if comparison_size == issue_size:
            backcolor = RGBColor(187, 191, 196)
        elif comparison_size < issue_size:
            signal_flag = f"( ↑ {issue_size-comparison_size} )"
        else:
            signal_flag = f"( ↓ {comparison_size-issue_size} )"

    return _create_textrun_tablecell(
        text=f" {issue_size} {signal_flag} ",
        link=jira_jql_link.format(
            url=jira_url_prefix,
            issue_keys=", ".join(issue_keys),
        ),
        backcolor=backcolor,
    )


def _create_content_blocks(
    jira_badcase_set: Dict,
    jira_url_prefix: str,
    time_labels: List[datetime.datetime],
    domain_list: List[str],
    badcase_status_map: Dict,
):
    time_label_size = len(time_labels)
    domain_size = len(domain_list)
    columnwidth = [200, 200, 150] + [100] * time_label_size * domain_size
    column = 3 + time_label_size * domain_size
    row = 2 + 8 * len(jira_badcase_set)

    table = Table(
        columnsize=column,
        rowsize=row,
        columnwidth=columnwidth,
        mergedcells=[],
    )
    jira_jql_link = "{url}/issues/?jql=issuekey in ({issue_keys})"
    for domain_idx, domain in enumerate(domain_list):
        table[
            0, 3 + domain_idx * time_label_size
        ] = _create_textrun_tablecell(  # noqa
            text=domain,
            align="center",
            bold=True,
        )
        table.append_mergedcell(
            MergedCell(
                rowStartIndex=0,
                rowEndIndex=1,
                columnStartIndex=3 + domain_idx * time_label_size,
                columnEndIndex=3 + (domain_idx + 1) * time_label_size,
            )
        )
        for time_label_idx, time_label in enumerate(time_labels):
            table[
                1, 3 + domain_idx * time_label_size + time_label_idx
            ] = _create_textrun_tablecell(
                text=time_label.strftime("%Y-%m-%d"),
                align="center",
                bold=True,
            )

        for project_idx, (project_name, jira_badcases) in enumerate(
            jira_badcase_set.items()
        ):
            table[2 + project_idx * 8, 0] = _create_textrun_tablecell(
                text=project_name,
                align="center",
                bold=True,
            )
            table.append_mergedcell(
                MergedCell(
                    rowStartIndex=2 + project_idx * 8,
                    rowEndIndex=10 + project_idx * 8,
                    columnStartIndex=0,
                    columnEndIndex=1,
                )
            )

            for status_idx, status in enumerate(badcase_status_map):
                table[
                    2 + project_idx * 8 + status_idx * 2, 1
                ] = _create_textrun_tablecell(
                    text=status,
                    align="center",
                )
                table.append_mergedcell(
                    MergedCell(
                        rowStartIndex=2 + project_idx * 8 + 2 * status_idx,
                        rowEndIndex=4 + project_idx * 8 + 2 * status_idx,
                        columnStartIndex=1,
                        columnEndIndex=2,
                    )
                )
                table[
                    2 + project_idx * 8 + status_idx * 2, 2
                ] = _create_textrun_tablecell(text="高优")
                table[
                    3 + project_idx * 8 + status_idx * 2, 2
                ] = _create_textrun_tablecell(text="中低优")

            if domain not in jira_badcases:
                continue

            next_result = None
            times_len = len(time_labels) - 1
            for time_label_idx, back_time in enumerate(reversed(time_labels)):
                result = badcase_status_statistics(
                    badcase_list=jira_badcases[domain],
                    back_time=back_time,
                    badcase_status_map=badcase_status_map,
                )
                for status_idx, status in enumerate(badcase_status_map):
                    table[
                        2 + project_idx * 8 + status_idx * 2,
                        3
                        + domain_idx * time_label_size
                        + times_len
                        - time_label_idx,
                    ] = _create_statistics_tablecell(
                        result=result,
                        comparison_result=next_result,
                        status=status,
                        prioritys=[
                            IssuePriority.High.value,
                        ],
                        jira_url_prefix=jira_url_prefix,
                        jira_jql_link=jira_jql_link,
                    )

                    table[
                        3 + project_idx * 8 + status_idx * 2,
                        3
                        + domain_idx * time_label_size
                        + times_len
                        - time_label_idx,
                    ] = _create_statistics_tablecell(
                        result=result,
                        comparison_result=next_result,
                        status=status,
                        prioritys=[
                            IssuePriority.Medium.value,
                            IssuePriority.Low.value,
                        ],
                        jira_url_prefix=jira_url_prefix,
                        jira_jql_link=jira_jql_link,
                    )
                next_result = result

    return Block(type="table", table=table)


def jira_badcase_report_to_feishu_doc(
    jira_badcase_report: JiraBadcaseReport,
    domain_set: Optional[List[str]] = None,
    time_labels: List[datetime.datetime] = None,
    badcase_status_map: Dict = None,
    jira_url_prefix: str = None,
    jira_client: Optional[Jira] = None,
):

    if jira_url_prefix is None:
        if jira_client is None:
            jira_client = get_resource(Jira)
        jira_url_prefix = jira_client.url

    if not time_labels:
        time_labels = [jira_badcase_report.create_time]
    else:
        time_labels.sort(reverse=True)

    body = Body(
        blocks=[
            _create_content_blocks(
                jira_badcase_set=jira_badcase_report.jira_badcase_set,
                time_labels=time_labels,
                domain_list=jira_badcase_report.domain_set
                if domain_set is None
                else domain_set,
                badcase_status_map=BadcaseStatusMap
                if badcase_status_map is None
                else badcase_status_map,
                jira_url_prefix=jira_url_prefix,
            )
        ]
    )

    return Document(
        title=Title(title=jira_badcase_report.title_with_time()),
        body=body,
    )
