from jira import JIRA
import os
import pickle


class GetData():
    def __init__(self):
        self.projects_attributes = dict()
        self.jira_conn = JIRA('https://jira.test.com:8443',
                              auth=('', ''))
        self.issue_folder = 'issue'

    def init_folder(self):
        if not os.path.exists(self.issue_folder):
            os.makedirs(self.issue_folder)

    def get_projects(self):
        project_list = self.jira_conn.projects()
        for project in project_list:
            self.projects_attributes[project.key] = project.raw
        self.save_pkl('jira_project.pkl', self.projects_attributes)

    def get_issues(self):
        for project_key in self.projects_attributes.keys():
            issue_raw = dict()
            sql = 'project=' + project_key + ' AND Created >= "2021-1-1"'
            issues_in_proj = self.jira_conn.search_issues(
                sql, maxResults=-1)
            for issue in issues_in_proj:
                issue_raw[issue.key] = issue.raw
            issue_path = 'issue/%s.pkl' % project_key
            self.save_pkl(issue_path, issue_raw)

    def save_pkl(self, file_name, data):
        f_obj = open(file_name, 'wb')
        pickle.dump(data, f_obj)
        f_obj.close()

    def read_pkl(self, file_name):
        f_obj = open(file_name, 'rb')
        return pickle.load(f_obj)


def main():
    get_data = GetData()
    get_data.init_folder()
    get_data.get_projects()
    get_data.get_issues()
    print('end')


if __name__ == "__main__":
    main()
