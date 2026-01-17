from collections import OrderedDict
import sys
import requests
import pickle
import time

sys.setrecursionlimit(999999)

API_TOKEN = ''
differential_query = 'https://cr.test.com/api/differential.revision.search'
differential_diff_search = 'https://cr.test.com/api/differential.diff.search'
diffusion_repository_search = 'https://cr.test.com/api/diffusion.repository.search'
user_search = 'https://cr.test.com/api/user.search'
transaction_search = 'https://cr.test.com/api/transaction.search'
#from_time = '1577807999'

id_list = list()
diff_list = list()
repository_list = list()
user_list = list()
transaction_dict = dict()

id_file = 'ids.pkl'
diff_file = 'diffs.pkl'
repository_file = 'repository.pkl'
user_file = 'users.pkl'
transaction_file = 'transaction.pkl'

def save_pkl(file_name,data):
    f_obj = open(file_name, 'wb')
    pickle.dump(data, f_obj)
    f_obj.close()

def read_pkl(file_name):
    f_obj = open(file_name, 'rb')
    return pickle.load(f_obj)

def get_ids(after=None):
    data = OrderedDict()
    data['api.token'] = API_TOKEN
    data['queryKey[queryKey]'] = 'all'
    # data['constraints[createdStart]'] = from_time
    data['order[0]'] = '-id'
    if after:
        data['after'] = after
    while True:
        try:
            result = requests.post(differential_query, data=data).json()
            break
        except Exception as e:
            print(e)
            time.sleep(60)
    before = result['result']['cursor']['before']
    after = result['result']['cursor']['after']
    
    id_list.extend(result['result']['data'])
    print("total id is %d" % len(id_list))
    save_pkl(id_file,id_list)

    if after:
        print("next id query will start from %s" % after)
        get_ids(after)
    

def get_diffs(after=None):
    data = OrderedDict()
    data['api.token'] = API_TOKEN
    data['queryKey[queryKey]'] = 'all'
    data['order[0]'] = '-id'
    if after:
        data['after'] = after
    while True:
        try:
            result = requests.post(differential_diff_search, data=data).json()
            break
        except Exception as e:
            print(e)
            time.sleep(60)
    before = result['result']['cursor']['before']
    after = result['result']['cursor']['after']
        
    diff_list.extend(result['result']['data'])
    print("total diff is %d" % len(diff_list))
    save_pkl(diff_file,diff_list)

    if after:
        print("next diff query will start from %s" % after)
        get_diffs(after)

def get_repository(after=None):
    data = OrderedDict()
    data['api.token'] = API_TOKEN
    data['queryKey[queryKey]'] = 'all'
    data['order[0]'] = '-id'
    if after:
        data['after'] = after
    while True:
        try:
            result = requests.post(diffusion_repository_search, data=data).json()
            break
        except Exception as e:
            print(e)
            time.sleep(60)
    before = result['result']['cursor']['before']
    after = result['result']['cursor']['after']
        
    repository_list.extend(result['result']['data'])
    print("total repository is %d" % len(repository_list))
    save_pkl(repository_file,repository_list)

    if after:
        print("next repository query will start from %s" % after)
        get_repository(after)

def get_user(after=None):
    data = OrderedDict()
    data['api.token'] = API_TOKEN
    data['queryKey[queryKey]'] = 'all'
    data['order[0]'] = '-id'
    if after:
        data['after'] = after
    while True:
        try:
            result = requests.post(user_search, data=data).json()
            break
        except Exception as e:
            print(e)
            time.sleep(60)
    before = result['result']['cursor']['before']
    after = result['result']['cursor']['after']
        
    user_list.extend(result['result']['data'])
    print("total user is %d" % len(user_list))
    save_pkl(user_file,user_list)

    if after:
        print("next user query will start from %s" % after)
        get_user(after)

if __name__ == "__main__":
    get_ids()
    print("finish ids total size is %d " % len(id_list))
    print("save to %s" % id_file)
    save_pkl(id_file,id_list) 
    
    get_diffs()
    print("finish diffs total size is %d " % len(diff_list))
    print("save to %s" % diff_file)
    save_pkl(diff_file,diff_list)
    
    get_repository()
    print("finish repository total size is %d " % len(repository_list))
    print("save to %s" % repository_file)
    save_pkl(repository_file,repository_list)
    
    get_user()
    print("finish user total size is %d " % len(user_list))
    print("save to %s" % user_file)
    save_pkl(user_file,user_list)
