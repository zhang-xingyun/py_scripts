import logging
import gitlab


class Gitlab:
    def __init__(self):
        self.gl = gitlab.Gitlab.from_config('trigger', ['python-gitlab.cfg'])

    def creat_project_hook(self):
        mr_lint_url = 'https://robot:xxx@ci-earth.test.com:8443/project/devops_se_scm/MR_LINT'
        hook_data = {
            'url': mr_lint_url,
            'push_events': False,
            'tag_push_events': False,
            'note_events': True,
            'confidential_note_events': False,
            'issues_events': False,
            'confidential_issues_events': False,
            'merge_requests_events': True,
            'job_events': False,
            'pipeline_events': False,
            'wiki_page_events': False,
            'enable_ssl_verification': True
        }
        projects = self.gl.projects.list(all=True)
        ex_projects=[]
        with open('sync_mr_lint_hook_ex', encoding='utf8') as f:    
            for i in f.read().split(','):
                ex_projects.append (int(i))
        print('不自动添加mr_lint的列表',ex_projects)
            

        for project in projects:
            if project.attributes['namespace']['kind'] != 'user' and project.attributes['id'] not in ex_projects:
                print (project.attributes['id'])
                hooks = project.hooks.list()
                if hooks:
                    hook_url_list = list()
                    for hook in hooks:
                        hook_url_list.append(hook.url)
                    if mr_lint_url not in hook_url_list:
                        project.hooks.create(hook_data)
                        logging.info("{} add mr lint hook".format(project.id))
                else:
                    project.hooks.create(hook_data)
                    logging.info("{} add mr lint hook".format(project.id))


def main():
    obj = Gitlab()
    obj.creat_project_hook()

if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(asctime)s: %(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)
    main()
