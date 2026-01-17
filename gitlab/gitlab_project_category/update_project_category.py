import sys
import logging
import gitlab
import argparse



class Gitlab:
    def __init__(self, id_list, owner, project):
        self.id_list = id_list
        self.owner = owner
        self.project = project
        self.tag_list = []
        self.success = []
        self.failed = []
        self.gl = gitlab.Gitlab.from_config('trigger', ['python-gitlab.cfg'])

    def change_project_taglist(self):
        for id in self.id_list:
            gitlab_project = None
            try:
                gitlab_project = self.gl.projects.get(id)
            except:
                print('cannot find the gitlab_project with id:'+id)
                self.failed.append(id)
            if gitlab_project is not None:
                newtag = 'owner:'+self.owner+',project:'+self.project
                self.tag_list.append(newtag)
                gitlab_project.tag_list = self.tag_list
                gitlab_project.save()
                print('id:'+id+' was added in category: '+newtag+'successfully!')
                self.success.append(id)
        if len(self.failed):
            raise Exception(print("The following ids failed:" + str(self.failed)))

def main():
    parser = argparse.ArgumentParser(description='Process some args.')
    parser.add_argument('-i', '--id',
                        metavar=str(), required=True,
                        help="id",
                        type=str)
    parser.add_argument('-o', '--owner',
                        metavar=str(), required=True,
                        help="owner",
                        type=str)
    parser.add_argument('-p', '--project',
                        metavar=str(), required=True,
                        help="project",
                        type=str)
    args = parser.parse_args()
    id_list = list(filter(None,args.id.split('|')))
    obj = Gitlab(id_list, args.owner, args.project)
    obj.change_project_taglist()


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(asctime)s: %(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)
    sys.exit(main())