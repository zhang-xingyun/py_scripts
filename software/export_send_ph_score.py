# coding: utf-8
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
import smtplib
from email.mime.text import MIMEText
import pathlib
from openpyxl import Workbook
from configparser import ConfigParser
from gitlab_app.models import PHCodeReviewInline


class ExportScore(object):
    path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def export(self):
        wb = Workbook()
        ws = wb.active
        ws.append(['作者', '分数', 'above', 'below', '确认', '评分人', '链接',
                   '仓库', 'message', '文件名', '评论内容', '回复内容', '开始行数',
                   '结束行数', '评论时间', '状态', '备注'])

        content = PHCodeReviewInline.objects.all().order_by('-created_at')
        if len(content) == 0:
            return
        for content in content:
            extra = ''
            if content.auto_score:
                extra = '系统自动评分'
            if content.author == content.reviewer:
                extra = '自己评论'

            ws.append([
                content.author,
                content.score,
                content.above,
                content.below,
                content.confirm,
                content.reviewer,
                content.url,
                content.repo_name,
                content.title,
                content.file_name,
                content.comment,
                content.reply_comment,
                content.line,
                content.line + content.length - 1,
                str(content.created_at)[:-6],
                content.status,
                extra
            ])
        save_path = os.path.join(self.path, '[ReviewGrade] PH代码评审意见分级.xlsx')
        wb.save(save_path)
        cp = ConfigParser()
        config = os.path.join(self.path, 'python-gitlab.cfg')
        cp.read(config)
        username = cp.get('email', 'username')
        password = cp.get('email', 'password')
        recv = [
        ]
        self.send_mail(username, password, recv, '[ReviewGrade] PH代码评审意见分级',
                       file=save_path)

    @staticmethod
    def send_mail(username, passwd, recv, title, content='',
                  mail_host='mail.test.com', port=25, file=None):
        '''
        发送邮件函数，默认使用163smtp
        :param username: 邮箱账号 xx@163.com
        :param passwd: 邮箱密码
        :param recv: 邮箱接收人地址，多个账号以逗号隔开
        :param title: 邮件标题
        :param content: 邮件内容
        :param mail_host: 邮箱服务器
        :param port: 端口号
        :return:
        '''
        if file:
            msg = MIMEMultipart()
            # 构建正文
            part_text = MIMEText(content)
            msg.attach(part_text)  # 把正文加到邮件体里面去

            # 构建邮件附件
            part_attach1 = MIMEApplication(open(file, 'rb').read())  # 打开附件
            part_attach1.add_header('Content-Disposition', 'attachment',
                                    filename=pathlib.Path(file).name)  # 为附件命名
            msg.attach(part_attach1)  # 添加附件
        else:
            msg = MIMEText(content)  # 邮件内容
        msg['Subject'] = title  # 邮件主题
        msg['From'] = username + '@test.com'  # 发送者账号
        if isinstance(recv, list):
            msg['To'] = ';'.join(recv)
        else:
            msg['To'] = recv  # 接收者账号列表
        smtp = smtplib.SMTP(mail_host, port=port)
        smtp.login(username, passwd)  # 登录
        smtp.sendmail(username + '@test.com', recv, msg.as_string())
        smtp.quit()


def run():
    ExportScore().export()
