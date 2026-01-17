import sys
import logging
import gitlab
import mechanize
import argparse
from http import cookiejar


class Gitlab:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.gl = gitlab.Gitlab.from_config('trigger', ['python-gitlab.cfg'])
    
    def init_user(self):
        br = mechanize.Browser()
        cj = cookiejar.CookieJar()
        br.set_cookiejar(cj)
        br.set_handle_equiv(True)
        br.set_handle_gzip(True)
        br.set_handle_redirect(True)
        br.set_handle_referer(True)
        br.set_handle_robots(False)
        br.set_handle_refresh(
            mechanize._http.HTTPRefreshProcessor(), max_time=1)
        br.set_debug_http(False)
        br.addheaders = [
            ('User-agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:15.0) Gecko/20100101 Firefox/15.0.1')]
        response = br.open('http://gitlab.test.com')
        br.select_form(nr=0)
        br.form['username'] = self.username
        br.form['password'] = self.password
        br.submit()
        return br

    def set_user_external(self):
        try:
            user = self.gl.users.list(username=self.username)[0]
            user.external = True
            user.save()
            logging.info("{} set external".format(self.username))
            return True
        except Exception as e:
            logging.error(e)
            logging.error("please check username or password")
            return False

    def check_user_status(self):
        user = self.gl.users.list(username=self.username)[0]
        user_status = user.external
        if  user_status is True:
            logging.info("{} external status: {}".format(self.username, user_status))
            logging.info("{} set external successfully".format(self.username))
            return 0
        logging.error("{} external status: {}".format(self.username, user_status))
        logging.error("{} set external failed".format(self.username))
        logging.error("please check username or password")
        return -1

def main():
    parser = argparse.ArgumentParser(description='Process some args.')
    parser.add_argument('-u', '--username',
                        metavar=str(), required=True,
                        help="username",
                        type=str)
    parser.add_argument('-p', '--password',
                        metavar=str(), required=True,
                        help="password",
                        type=str)
    args = parser.parse_args()
    obj = Gitlab(args.username, args.password)
    obj.init_user()
    user_result = obj.set_user_external()
    if user_result:
        check_result = obj.check_user_status()
        return check_result
    return -1

if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(asctime)s: %(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)
    sys.exit(main())