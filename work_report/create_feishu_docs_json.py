import datetime
import logging
import re
import uuid
from typing import Dict, List, Optional

import requests
from fordring import feishu
from fordring.atlassian import Jira
from fordring.feishu import Session
from fordring.feishu.doc_data import (
    Block,
    Body,
    Document,
    Gallery,
    HorizontalLine,
    ImageItem,
    Paragraph,
    ParagraphElement,
    Person,
    RGBColor,
    Table,
    TableCell,
    TableRow,
    TextRun,
    Title,
)
from hatbc.resource_manager import get_resource

from hdflow.work_report.create_feishu_dosc_json_base import (
    _create_person_tablecell,
    _create_textrun_block,
    _create_textrun_tablecell,
)
from hdflow.work_report.enum import IssueStatus, IssueType
from hdflow.work_report.jira_work_report import JiraWorkReport

__all__ = ["jira_work_report_to_feishu_doc"]


logger = logging.getLogger(__name__)


def _download(url: str):
    try:
        resp = requests.get(url)
    except Exception as e:
        logger.error(f"get out image {url}: {e}")
        image_info = None
    else:
        if "image" not in resp.headers["Content-Type"]:
            image_info = None
        else:
            image_type = resp.headers["Content-Type"].split("/")[-1]
            image_name = (
                f"feishu_work_report_{uuid.uuid4().hex[:6]}.{image_type}"
            )
            image_info = {
                "name": image_name,
                "content": url,
                "mimeType": resp.headers["Content-Type"],
                "size": len(resp.content),
                "bytes": resp.content,
            }

    return image_info


def _create_filter_ids_elements(
    filter_ids: List[int],
    link_template: str,
    jira_url_prefix: str,
):
    return [
        ParagraphElement(
            type="textRun",
            textRun=TextRun(
                text=f"{filter_id}" if value else " ",
                link=value,
            ),
        )
        for filter_id in filter_ids
        for value in (
            None,
            link_template.format(url=jira_url_prefix, filter_id=filter_id),
        )
    ]


def _create_introduction_blocks(
    filter_ids: List[int],
    progress_latest: bool,
    jira_url_prefix: str,
    create_time: datetime.datetime,
    start_time: Optional[datetime.datetime] = None,
    end_time: Optional[datetime.datetime] = None,
):
    start_time = start_time.strftime("%Y/%m/%d") if start_time else "None"
    end_time = end_time.strftime("%Y/%m/%d") if end_time else "None"
    create_time = create_time.strftime("%Y-%m-%d %H:%M")
    return [
        Block(
            type="paragraph",
            paragraph=Paragraph(
                elements=[
                    ParagraphElement(
                        type="textRun",
                        textRun=TextRun(
                            text=f"统计时间：{create_time}",  # noqa
                        ),
                    )
                ]
            ),
        ),
        Block(
            type="paragraph",
            paragraph=Paragraph(
                elements=[
                    ParagraphElement(
                        type="textRun",
                        textRun=TextRun(
                            text=f"时间范围：{start_time}~{end_time}",
                        ),
                    )
                ]
            ),
        ),
        Block(
            type="paragraph",
            paragraph=Paragraph(
                elements=[
                    ParagraphElement(
                        type="textRun",
                        textRun=TextRun(
                            text=f"进展获取选择：{'最新进展' if progress_latest else '全部进展'}",  # noqa
                        ),
                    )
                ]
            ),
        ),
        Block(
            type="paragraph",
            paragraph=Paragraph(
                elements=[
                    ParagraphElement(
                        type="textRun",
                        textRun=TextRun(
                            text="问题列表：",
                        ),
                    )
                ]
                + _create_filter_ids_elements(
                    filter_ids=filter_ids,
                    link_template="{url}/issues/?filter={filter_id}",
                    jira_url_prefix=jira_url_prefix,
                )
            ),
        ),
        Block(
            type="paragraph",
            paragraph=Paragraph(
                elements=[
                    ParagraphElement(
                        type="textRun",
                        textRun=TextRun(
                            text="甘特图：",
                        ),
                    )
                ]
                + _create_filter_ids_elements(
                    filter_ids=filter_ids,
                    link_template="{url}/secure/WBSGanttMain.jspa?filter={filter_id}",  # noqa
                    jira_url_prefix=jira_url_prefix,
                )
            ),
        ),
    ]


def _create_summary(
    issue_info: Dict,
    jira_url_prefix: str,
    headinglevel: int = None,
    list_type: str = None,
    list_number: int = None,
    session: Optional[Session] = None,
):
    if session is None:
        session = get_resource(Session)

    if list_type is not None:
        list_att = {
            "type": list_type,
            "indentLevel": headinglevel,
            "number": list_number,
        }
    resp = feishu.user.get_user_id(
        emails=[issue_info.assignee["email"]],
        session=session,
    )
    feishu.check_success(resp)
    user_id = resp["data"]["user_list"][0].get("user_id", None)
    paragraph = Paragraph(
        headinglevel=headinglevel,
        list_att=list_att,
        elements=[
            ParagraphElement(
                type="textRun",
                textRun=TextRun(
                    text=issue_info.summary,
                    link=f"{jira_url_prefix}/browse/{issue_info.issue_key}",
                ),
            ),
            ParagraphElement(
                type="textRun",
                textRun=TextRun(
                    text=issue_info.assignee["name"],
                ),
            )
            if user_id is None
            else ParagraphElement(
                type="person",
                person=Person(
                    openId=user_id,
                ),
            ),
        ],
    )
    return paragraph


def _init_feishu_table():
    column_infos = [
        {"name": "题目", "width": 320},
        {"name": "责任人", "width": 110},
        {"name": "优先级", "width": 100},
        {"name": "状态", "width": 100},
        {"name": "计划开始时间", "width": 100},
        {"name": "计划结束时间", "width": 100},
        {"name": "进展", "width": 630},
    ]
    table = Table(
        columnsize=len(column_infos),
        columnwidth=[column_info["width"] for column_info in column_infos],
    )
    table.insert_row(
        tablerow=TableRow(
            tableCells=[
                _create_textrun_tablecell(text=column_info["name"])
                for column_info in column_infos
            ]
        )
    )
    return table


def _add_feishu_table_row(
    table: Table,
    issue_info: Dict,
    jira_url_prefix: str,
    critical_time_begin: datetime.datetime,
    image_upload_node_token: str = None,
):
    table.insert_row(
        tablerow=TableRow(
            tableCells=[
                _create_textrun_tablecell(
                    text=issue_info.summary,
                    link=f"{jira_url_prefix}/browse/{issue_info.issue_key}",
                ),
                _create_person_tablecell(assignee=issue_info.assignee),
                _create_textrun_tablecell(text=issue_info.priority),
                _create_textrun_tablecell(text=issue_info.status),
                _create_textrun_tablecell(
                    text=issue_info.planstart.strftime("%Y-%m-%d")
                    if issue_info.planstart
                    else None
                ),
                _create_textrun_tablecell(
                    text=issue_info.planend.strftime("%Y-%m-%d")
                    if issue_info.planend
                    else None
                ),
                _create_progress_tablecell(
                    progress_list=issue_info.progress,
                    attachments=issue_info.attachments,
                    planend=issue_info.planend,
                    status=issue_info.status,
                    critical_time_begin=critical_time_begin,
                    image_upload_node_token=image_upload_node_token,
                    jira_url_prefix=jira_url_prefix,
                ),
            ]
        )
    )


def _create_gallery_block(
    image_url: str,
    attachments: Dict,
    image_upload_node_token: str = None,
    session: Optional[Session] = None,
):
    if session is None:
        session = get_resource(Session)

    if attachments is not None and image_url in attachments:
        attachment_info = attachments[image_url]
    else:
        attachment_info = _download(url=image_url)

    if attachment_info is None:
        return _create_textrun_block(text=image_url)
    else:
        resp = feishu.material.upload_material(
            file_bytes=attachment_info["bytes"],
            file_name=attachment_info["name"],
            file_size=attachment_info["size"],
            parent_node_token=image_upload_node_token,
            session=session,
        )
        feishu.check_success(resp)
        return Block(
            type="gallery",
            gallery=Gallery(
                imagelist=[
                    ImageItem(
                        fileToken=resp["data"]["file_token"],
                    )
                ]
            ),
        )


def _create_text_blocks(
    text: str,
    link: str = None,
    align: str = "left",
    bold: bool = False,
    headinglevel: int = None,
    textcolor: Optional[RGBColor] = None,
    backcolor: Optional[RGBColor] = None,
    attachments: Dict = None,
    image_upload_node_token: str = None,
    session: Optional[Session] = None,
):
    if session is None:
        session = get_resource(Session)

    blocks = []
    sentences = text.split("\n") if text is not None else [None]
    for sentence in sentences:
        while sentence:
            image_name = re.search(
                r"\^?!((https?://.*?)|(.*\.((png)|(jpg)|(jpeg)|(gif))))(\|.*?)?!\^?",  # noqa
                sentence,
            )
            if image_upload_node_token is None or image_name is None:
                blocks.append(
                    _create_textrun_block(
                        headinglevel=headinglevel,
                        align=align,
                        text=sentence,
                        link=link,
                        bold=bold,
                        textcolor=textcolor,
                        backcolor=backcolor,
                    )
                )
                sentence = None
            else:
                if not sentence[: image_name.start()].isspace():
                    blocks.append(
                        _create_textrun_block(
                            headinglevel=headinglevel,
                            align=align,
                            text=sentence[: image_name.start()],
                            link=link,
                            bold=bold,
                            textcolor=textcolor,
                            backcolor=backcolor,
                        )
                    )
                blocks.append(
                    _create_gallery_block(
                        image_url=image_name.group(1),
                        attachments=attachments,
                        image_upload_node_token=image_upload_node_token,
                        session=session,
                    )
                )
                sentence = sentence[image_name.end() :]
    return blocks


def _create_progress_tablecell(
    progress_list: List[Dict],
    attachments: Dict,
    status: str,
    critical_time_begin: datetime.datetime,
    jira_url_prefix: str,
    planend: Optional[datetime.date] = None,
    image_upload_node_token: str = None,
    session: Optional[Session] = None,
):
    if session is None:
        session = get_resource(Session)

    body = Body()
    if planend is None:
        planend = datetime.datetime.max
    else:
        planend = datetime.datetime.combine(planend, datetime.time.max)

    total = len(progress_list)
    for i, progress in enumerate(progress_list):
        progress_text = progress.get("text", "")
        progress_time = progress.get("time")
        textcolor = None
        if progress_time is not None:
            value = f"进展更新时间: {progress_time.strftime('%Y-%m-%d %H:%M:%S')}\n{progress_text}"  # noqa
            if progress_time < critical_time_begin:
                textcolor = RGBColor(143, 149, 158)
        else:
            value = None

        if progress_time > planend and status != IssueStatus.Closed_done.value:
            textcolor = RGBColor(216, 57, 49)

        body.blocks.extend(
            _create_text_blocks(
                text=value,
                textcolor=textcolor,
                attachments=attachments,
                image_upload_node_token=image_upload_node_token,
                session=session,
            )
        )
        if i + 1 != total:
            body.append(
                Block(
                    type="horizontalLine",
                    horizontalLine=HorizontalLine(),
                )
            )
    return TableCell(body=body)


def _create_content_blocks(
    issue_info_list: List,
    critical_time_begin: datetime.datetime,
    jira_url_prefix: str,
    image_upload_node_token: str = None,
    list_type: str = "number",
):
    blocks = []
    level_map = {}
    for ind, issue_info in enumerate(issue_info_list):
        if issue_info.issuetype != IssueType.Task.value:
            if issue_info.level not in level_map:
                level_map[issue_info.level] = 1
            else:
                level_map[issue_info.level] += 1
                for level in level_map:
                    if level > issue_info.level:
                        level_map[level] = 0

            blocks.append(
                Block(
                    type="paragraph",
                    paragraph=_create_summary(
                        issue_info=issue_info,
                        headinglevel=issue_info.level,
                        list_type=list_type,
                        list_number=level_map[issue_info.level],
                        jira_url_prefix=jira_url_prefix,
                    ),
                )
            )
        else:

            if ind == 0 or (
                ind > 0
                and (
                    issue_info_list[ind - 1].issuetype != IssueType.Task.value
                    or issue_info_list[ind - 1].level != issue_info.level
                )
            ):
                table = _init_feishu_table()
                blocks.append(Block(type="table", table=table))
            _add_feishu_table_row(
                table=table,
                issue_info=issue_info,
                critical_time_begin=critical_time_begin,
                image_upload_node_token=image_upload_node_token,
                jira_url_prefix=jira_url_prefix,
            )
    return blocks


def jira_work_report_to_feishu_doc(
    jira_work_report: JiraWorkReport,
    critical_time_begin: datetime.datetime,
    image_upload_node_token: str = None,
    jira_url_prefix: str = None,
    jira_client: Optional[Jira] = None,
):
    if jira_url_prefix is None:
        if jira_client is None:
            jira_client = get_resource(Jira)
        jira_url_prefix = jira_client.url

    body = Body(
        blocks=_create_introduction_blocks(
            filter_ids=jira_work_report.filter_ids,
            progress_latest=jira_work_report.progress_latest,
            create_time=jira_work_report.create_time,
            start_time=jira_work_report.start_time,
            end_time=jira_work_report.end_time,
            jira_url_prefix=jira_url_prefix,
        )
        + _create_content_blocks(
            issue_info_list=jira_work_report.issue_info_list,
            critical_time_begin=critical_time_begin,
            image_upload_node_token=image_upload_node_token,
            jira_url_prefix=jira_url_prefix,
        )
    )

    return Document(
        title=Title(
            title=jira_work_report.title_with_time(daytime=critical_time_begin)
        ),
        body=body,
    )
