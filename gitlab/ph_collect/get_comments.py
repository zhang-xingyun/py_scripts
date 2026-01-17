from collections import OrderedDict
import sys
import requests
import pickle
import time
import multiprocessing


sys.setrecursionlimit(999999)

API_TOKEN = ''
transaction_search = 'https://cr.test.com/api/transaction.search'
#from_time = '1577807999'

def save_pkl(file_name,data):
    f_obj = open(file_name, 'wb')
    pickle.dump(data, f_obj)
    f_obj.close()

def read_pkl(file_name):
    f_obj = open(file_name, 'rb')
    return pickle.load(f_obj)

def func(listTemp, n):
    for i in range(0, len(listTemp), n):
        yield listTemp[i:i + n]

def get_comments(tmp_ids_data, data_file):
    print(len(tmp_ids_data))
    output = dict()
    for i in tmp_ids_data:
        phcase_id = i['phid']
        case_id = i['id']
        print('process id %s' % case_id)
        data = OrderedDict()
        data['api.token'] = API_TOKEN
        data['objectIdentifier'] = phcase_id

        while True:
            try:
                result = requests.post(transaction_search, data=data).json()
                break
            except Exception as e:
                print(e)
                time.sleep(60)

        output[case_id] = result['result']['data']
        #time.sleep(10)
        save_pkl(data_file,output)
        #break
    print("total size is %d for %s" % (len(output), data_file))
    save_pkl(data_file,output)

if __name__ == "__main__":
    process_num = 40
    ids_data =  read_pkl('ids.pkl')
    ids_data_len = len(ids_data)
    ids_data_split = func(ids_data, (int(ids_data_len / process_num) + 1 ))
    total_result = dict()
    total_process_list = list() 
    for i,i_data in enumerate(ids_data_split):
        data_file = 'transaction_' + str(i) + '.pkl'
        tmp_p = multiprocessing.Process(target = get_comments, args = (i_data, data_file))
        total_process_list.append(tmp_p)

    for i in total_process_list:
        i.start()

    for i in total_process_list:
        i.join()

    for i in range(len(total_process_list)):
        data_file = 'transaction_' + str(i) + '.pkl'
        print('merge %s' % data_file)
        tmp_data = read_pkl(data_file)
        total_result.update(tmp_data)
    #for i in total_result:
    #    print(i,total_result[i])
    print(len(total_result))
    save_pkl('transaction.pkl',total_result)




