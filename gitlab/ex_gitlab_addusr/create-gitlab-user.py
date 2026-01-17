# -*- coding:utf-8 -*-
import sys
import gitlab
import random

#登录信息           
gl = gitlab.Gitlab('https://gitlab.test.com', private_token='')
gl.auth()

def random_password():
    list1 = []
    list2 = []
    list3 = []
    #把字母加入序列中
    for i in range(65,90):
        list1.append(chr(i))
    for i in range(97,122):
        list2.append(chr(i))
    for i  in range(1,10):
        list3.append(i)
    # print (list1,list2,list3)
    password_list = random.sample(list1, 1)+random.sample(list2, 1) +random.sample(list3, 6)
    # print (password_list)
    password_list_str = [str(i) for i in password_list]
    password = ''.join(password_list_str)
    # print (password)
    return password

def usr_create():    
    usr_name= sys.argv[1]
    print(usr_name)
    usr_email=sys.argv[2]
    password =random_password()
    isExternal=sys.argv[3]
    group = gl.groups.get(sys.argv[4])
    if len(sys.argv)==6:
        email_user_admin = sys.argv[5]
    else:
        email_user_admin=sys.argv[2]

    print('开始创建用户--username:' +usr_name)
    gl.users.create({'email':usr_email,
                'password': password,
                'username': usr_name,
                'name': usr_name,
                'external':isExternal ,
                'skip_confirmation':'true',
                'note':email_user_admin
                })
    try:
        usr_verify = gl.users.list(username=usr_name)
        print ('创建用户完成',usr_name,password)
        id = usr_verify[0].id
        
        group.members.create({'user_id': id,'access_level': '20'}) 
    except Exception as e:
        print (usr_name,'创建用户失败')
             #增加失败飞书提醒
        
if __name__ == "__main__":      
    # print ('aa')
    # usrlist_to_add=[]
    # usr_list()
    # for usrinfo in usrlist_to_add:
        # print ('usrinfo',usrinfo)
        # usr_create(usrinfo)
    usr_create()