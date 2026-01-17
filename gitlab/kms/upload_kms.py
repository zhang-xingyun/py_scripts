import requests
import logging
import base64
import os
import argparse
import sys

#log level
logger = logging.getLogger()
logging.basicConfig(level = logging.INFO,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

URL = 'http://kms.test.com'

#固定目录id
#parentfolderid = 1670

#api
#get token
login_url = URL + '/api/services/Org/UserLogin'

#check token
check_token_url = URL + '/api/services/Org/CheckUserTokenValidity'

#upload file step1
start_upload_file_url = URL + '/api/services/Transfer/StartUploadFile'

#upload file step2
upload_file_block_url = URL+ '/api/services/Transfer/UploadFileBlock'

#upload file step3
end_upload_file_url = URL + '/api/services/Transfer/EndUploadFile'

#create folder
create_folder_url = URL + '/api/services/Folder/CreateFolder'
#get folder id
get_folder_name_url = URL + '/api/services/File/GetChildrenFolderAndFileList'

#check folder In Folder
check_folder_in_folder_url = URL + '/api/services/Folder/IsExistfolderInFolderByfolderName'

#login user
#username = 'test3'
#password = 'edoc2'

username = 'cmobot'
password = 'Dsl.ose-34'

#post headers
headers={'Content-type':'application/json', 'Accept':'application/json'}

def user_login(user_name, password):
    """
    login to kms system
    :param user_name: [string]
    :param password: [string]
    :return: token
    """
    payload = {'UserName':user_name, 'Password':password}
    resp = requests.post(url=login_url, json=payload, headers=headers).json()
    if not public_assertion(resp):
        return False
    token = resp['data']
    # logger.info('get user token is successful!')
    return token

def check_token_validation(token):
    '''
    check user token
    :param token: [string]
    :return:[bool]
    '''
    resp = requests.get(url=check_token_url, params={"Token": token}).json()
    logger.debug(f"kms check token validation response: {resp}")
    if not public_assertion(resp):
            return False
    if resp["data"]:
        # logger.info('check user token is successful!')
        return True
    return False

def public_assertion(result):
    """
    公共断言
    :param:  http request response
    :return: None
    """
    if 'errorCode' in result and result['errorCode'] == 0:
        return result
    elif 'result' in result and result['result'] == 0:
        return result
    elif 'Code' in result and result['Code'] == 0:
        if 'Result' in result and result['Result'] != 0:
            if 'Message' in result.keys():
                logger.error(f'error messages : {result["Message"]}')
            return False
        return result
    else:
        logger.error(f"kms http request returned error! response: {result}")
        return False


def upload_file(token, parentfolderid, file_path, file_name=""):
    """
    upload file to kms
    :param file_name: file name showed in kms system. Use origin file name if a null string passed in. remote file name
    :param file_path: [string] the local path of file to upload. local file name
    :return: [bool] success or not
    upload a file to kms has 3 steps:
    1. upload file metadata;
    2. upload file blocks;
    3. finish file uploading.
    """
    import os
    import time
    from hashlib import sha256
    if file_name == "":
        file_name = os.path.basename(file_path)

    with open(file_path, 'rb') as fd:
        file_content = fd.read()
    file_size = len(file_content)
    file_code = sha256(file_content).hexdigest()
    upload_id = time.time().hex()
    logger.info(f"file_name: {file_name}, file_code: {file_code}")
    # step 1
    data_upload_start = {
        "parentId": parentfolderid,  # 父文件夹ID,
        "name": file_name,  # 文件名
        "Remark": "kms file",  # 文件备注
        "FileSize": file_size,
        "fileCode": "",
        "isUpdateFileVersion": False,
        "token": token,
        "fileId": 0,
        "uploadId": upload_id,
        "defaultSecurityLevel": 0,
    }
    resp_upload_start = requests.post(url=start_upload_file_url, json=data_upload_start).json()
    logger.info(f'resp_upload_start msg :{resp_upload_start}')
    if not public_assertion(resp_upload_start):
        return False

    # step 2
    batch_size = file_size  # max file block size
    upload_id = resp_upload_start["UploadId"]

    data_upload_block = {
        "dataSize": batch_size,
        "filePos": 0,
        "uploadId": upload_id,
        "regionHash": resp_upload_start["RegionHash"],
        "token": token
    }
    for i in range(0, file_size, batch_size):
        if file_size - i < batch_size:
            data_upload_block["dataSize"] = file_size - i
        data_to_send = file_content[i: data_upload_block["dataSize"]]
        base64_data_to_send = base64.b64encode(data_to_send)
        base64_data_to_send_str = base64_data_to_send.decode("utf-8")
        data_upload_block["blockData"] = base64_data_to_send_str

        resp_upload_block = requests.post(url=upload_file_block_url, json=data_upload_block).json()
        logger.info(f'resp_upload_block msg:{resp_upload_block}')
        if not public_assertion(resp_upload_block):
            return False

    # step 3
    data_upload_end = {
        "uploadId": upload_id,
        "RegionHash": resp_upload_start["RegionHash"],
        "Token": token
    }
    resp_upload_end = requests.post(url=end_upload_file_url, json=data_upload_end).json()
    logger.info(f'resp_upload_end msg:{resp_upload_end}')
    if not public_assertion(resp_upload_end):
        return False

    logger.info(f"upload file {file_name} succeeded! file_code: {file_code}")
    return True

def create_folder(token, folder_name, parentfolderid):
    folder_data = {
        'Name': folder_name,
        'FolderCode': '',
        'Remark': '',
        'ParentFolderId': parentfolderid,
        'token': token
    }
    create_folder_data = requests.post(url=create_folder_url, json=folder_data).json()
    if create_folder_data["result"] == 806:
        logger.warning(f'{folder_name} is exists, No need to recreate!')
    elif create_folder_data["result"] == 0:
        logger.info(f'create folder successful!folder id:{create_folder_data["data"]["FolderId"]}')
    return create_folder_data

def check_folder_in_folder(token, folderid, dir_path):
    path_list = dir_path.split('/')
    folder_name = path_list[len(path_list)-1]
    folder_data = {
        'token': token,
        'folderName': folder_name,
        'folderId': folderid
    }
    check_folder_data = requests.get(url=check_folder_in_folder_url, params=folder_data).json()
    if check_folder_data['data'] == False:
        return True
    logger.error(f'{folder_name} is exists, No need to recreate!')
    sys.exit(1)

def findAllFile(base):
    file_list = list()
    folder_list = list()
    for root, ds, fs in os.walk(base):
        folder_list.append(root)
        for f in fs:
            fullname = os.path.join(root, f)
            file_list.append(fullname)
    return file_list,folder_list

#upload folder and files
def upload(token, folder_name, parentfolderid):
    file_list, folder_list = findAllFile(folder_name)
    dict1 = dict()
    msg = create_folder(token, folder_name, parentfolderid)
    if msg['result'] == 806:
        logger.error(f'{folder_name} is exsits, No need to recreate!')
        return False
    dict1[folder_name] = msg["data"]["FolderId"]
    try:
        for folder in folder_list:
            if folder == folder_name:
                continue
            a = folder.split('/')
            folder_name = a[len(a)-1]
            a.pop()
            parentfolder = '/'.join(a)
            parentfolderid = dict1[parentfolder]
            new_create_folderid = create_folder(token, folder_name, parentfolderid)["data"]["FolderId"]
            dict1[folder] = new_create_folderid
        #upload file
        for f in file_list:
            a = f.split('/')
            a.pop()
            folder_path = '/'.join(a)
            upload_file(token, dict1[folder_path], f, file_name='')
    except Exception as e:
        logger.error(e)
        return False



def upload_dir(token, pfid ,dir_path):
    path_list = dir_path.split('/')
    folder_name = path_list[len(path_list)-1]
    path_list.pop()
    os.chdir('/'.join(path_list))
    parentfolderid = pfid
    upload(token, folder_name, parentfolderid)

def get_folder_id(token, pfid, folder_name):
    argsxml = '<GetListArgs><PageNum>1</PageNum><PageSize>1000</PageSize></GetListArgs>'
    folder_data = {
        'token': token,
        'folderId': pfid,
        'strArgsXml': argsxml
    }
    folder_data = requests.get(url=get_folder_name_url, params=folder_data).json()
    if not public_assertion(folder_data):
        return False
    dict1=dict()
    for i in folder_data['data']['fileInfo']:
        dict1[i['FileName']]=i['FileId']
    print(dict1[folder_name])
    return dict1[folder_name]

def main():
    token = user_login(username, password)
    check_token_validation(token)
    # dir_path = "/root/vscode/scripts/test_3092"
    # parentfolderid = 1670
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--func',
                        metavar=str(), required=True,
                        help="input func",
                        type=str)
    parser.add_argument('-p', '--dirpath',
                        metavar=str(),
                        help="input upload  folder path",
                        type=str)

    parser.add_argument('-i', '--pfid',
                        metavar=int(), required=True,
                        help="input parentfolderid",
                        type=int)
    parser.add_argument('-n', '--name',
                        metavar=str(),
                        help="input folder name",
                        type=str)
    args = parser.parse_args()
    if args.func == 'upload':
        check_folder_in_folder(token, args.pfid, args.dirpath)
        upload_dir(token, args.pfid, args.dirpath)
    elif args.func == 'search':
        get_folder_id(token, args.pfid, args.name)
if __name__=='__main__':
    main()
