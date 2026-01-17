from typing import Dict, Optional, Union

from fordring import feishu
from fordring.feishu import Session
from fordring.feishu.doc_data import (
    Block,
    Body,
    Paragraph,
    ParagraphElement,
    Person,
    RGBColor,
    TableCell,
    TextRun,
)
from hatbc.resource_manager import get_resource


def _create_textrun_block(
    text: str,
    link: str = None,
    align: str = "left",
    bold: bool = False,
    headinglevel: int = None,
    textcolor: Optional[RGBColor] = None,
    backcolor: Optional[RGBColor] = None,
):
    return Block(
        type="paragraph",
        paragraph=Paragraph(
            headinglevel=headinglevel,
            align=align,
            elements=[
                ParagraphElement(
                    type="textRun",
                    textRun=TextRun(
                        text=text,
                        link=link,
                        bold=bold,
                        textcolor=textcolor,
                        backcolor=backcolor,
                    ),
                )
            ],
        ),
    )


def _create_textrun_tablecell(
    text: str,
    link: str = None,
    align: str = "left",
    bold: bool = False,
    headinglevel: int = None,
    textcolor: Optional[RGBColor] = None,
    backcolor: Optional[RGBColor] = None,
):
    return TableCell(
        body=Body(
            blocks=[
                _create_textrun_block(
                    align=align,
                    headinglevel=headinglevel,
                    text=text,
                    link=link,
                    bold=bold,
                    textcolor=textcolor,
                    backcolor=backcolor,
                )
            ]
        )
    )


def _create_person_tablecell(
    assignee: Union[str, Dict], session: Optional[Session] = None
):
    if session is None:
        session = get_resource(Session)

    if isinstance(assignee, str):
        assignee = {
            "name": assignee,
            "email": assignee,
        }

    resp = feishu.user.get_user_id(
        emails=[assignee["email"]],
        session=session,
    )
    feishu.check_success(resp)
    user_id = resp["data"]["user_list"][0].get("user_id", None)
    if user_id is None:
        paragraph = Paragraph(
            elements=[
                ParagraphElement(
                    type="textRun",
                    textRun=TextRun(
                        text=assignee["name"],
                    ),
                )
            ]
        )
    else:
        paragraph = Paragraph(
            elements=[
                ParagraphElement(
                    type="person",
                    person=Person(
                        openId=user_id,
                    ),
                )
            ]
        )
    return TableCell(
        body=Body(blocks=[Block(type="paragraph", paragraph=paragraph)])
    )
