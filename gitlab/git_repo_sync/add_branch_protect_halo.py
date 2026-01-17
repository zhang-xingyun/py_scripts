import gitlab
import argparse

class GitlabAPI(object):
    def __init__(self, *args, **kwargs):
        self.gl = gitlab.Gitlab.from_config('trigger', ['python-gitlab.cfg'])

    def add_branch_protect(self, project_id, branch_name, merge_rule, push_rule):
        project = self.gl.projects.get(project_id)
        try:
            project.protectedbranches.create({
                'name': branch_name,
                'merge_access_level': merge_rule,
                'push_access_level': push_rule
            })
        except Exception as e:
            print(e)
        check_branch = project.protectedbranches.get(branch_name)
        print('project id: {}'.format(project_id))
        return check_branch

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--branch_name',
                        metavar=str(), required=True,
                        help="branch_name",
                        type=str)
    args = parser.parse_args()
    project_id_list = [7748, 7753, 7754, 8090, 8089, 7870, 7869, 7868, 7783,
                        7782, 7780, 7779, 7778, 7777, 7776, 7775, 7774, 7773, 
                        7772, 7771, 7770, 7769, 7768, 7767, 7766, 7765, 7764, 
                        7763, 7762, 7761, 7760, 7759, 7758, 7757, 7755, 7752, 
                        7751, 7750, 7749, 8229]
    protect_branch_name = args.branch_name
    merge_rule = gitlab.DEVELOPER_ACCESS
    push_rule = gitlab.DEVELOPER_ACCESS
    obj = GitlabAPI()
    for project_id in project_id_list:
        result = obj.add_branch_protect(project_id, protect_branch_name, merge_rule, push_rule)
        print(result)

if __name__ == '__main__':
    main()
