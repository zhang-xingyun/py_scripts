1、本地安装python 3（我的是python 3.8.5）

2、安装插件 pip install pyPDF2==1.26.0
    C:\Users\用户名\AppData\Local\Programs\Python\Python38\Lib\site-packages\PyPDF2
打开pdf.py文件，423行，改成“P = -2047”
permissions说明
Bit position 3 is for printing, 4 is for modifying content, 5 and 6
control annotations, 9 for form fields, 10 for extraction of
text and graphics.

3、目录准备
	然后在D盘创建1个目录D:\加密，将pdf_encrypt.py拷贝到该目录下

4、执行加密操作，
a、将文档归档到文档外发目录下，然后设置水印
b、下载并解压放到‘D:\加密’目录下
c、在‘D:\加密’目录执行python脚本
d、验证加密效果后，将kms目录原文档删除，重新上传新文件




