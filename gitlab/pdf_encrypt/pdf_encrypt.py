import os
import shutil
from PyPDF2 import PdfFileWriter, PdfFileReader


if os.path.exists('D:\\no_encrypt'):
    shutil.rmtree('D:\\no_encrypt')
if os.path.exists('D:\\encrypted'):
    shutil.rmtree('D:\\encrypted')   
    
os.mkdir('D:\\no_encrypt')
os.mkdir('D:\\encrypted')


def set_encrypt(input_pdf, output):
    pdf_reader = PdfFileReader(input_pdf)
    pdf_writer = PdfFileWriter()
    #for page_num in range(pdf_reader.getNumPages()):
    #   print(input_pdf,"page:",page_num)
    #   page = pdf_reader.getPage(page_num)
    #   pdf_writer.addPage(page)
    pdf_writer.cloneReaderDocumentRoot(pdf_reader)
    pdf_writer.encrypt(user_pwd="",owner_pwd="@!@#&*(~)~()",use_128bit=True)  # 设置pdf密码
    with open(output, 'wb') as out:
    #   pdf_writer.addBookmark("hello",0)
        pdf_writer.write(out)


def file_work(dirname):
    postfix = 'pdf'
    filelist=[]
    no_encrypt_filelist=[]
    for maindir,subdir, file_name_list in os.walk(dirname):
        for filename in file_name_list:
            if filename.split('.')[-1] == postfix: 
                souece_path = os.path.join(maindir, filename)
                a_path='D:\\no_encrypt\\'+filename
                b_path='D:\\encrypted\\'+filename
                print (filename)
                
                shutil.copyfile(souece_path,a_path)
                print('copy to a_path',filename)
                try:
                    set_encrypt(a_path,b_path)
                    print('加密完成',filename)
                    shutil.copyfile(b_path,souece_path)
                    print('copy to souece_path',filename)
                    filelist.append(souece_path)
                except:
                    no_encrypt_filelist.append(souece_path)
                    pass                  
    print ('已成功加密文件清单如下',filelist)
    print ('未成功加密文件清单如下',no_encrypt_filelist)
    file = open("D:\\加密\\no_encrypted_file.txt","w")
    file.write('\n'.join(no_encrypt_filelist))
    file.close()
    

if __name__ == '__main__':  

    dirname='D:\\加密'
    file_work(dirname)

