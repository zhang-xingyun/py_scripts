import gitlab

ids = [7657,7516,6913,6809,5935,5737,5417,3354,2882]

gl = gitlab.Gitlab.from_config('trigger', 'python-gitlab.cfg')
gl.auth()

for s_id in ids:
    print(s_id)
    project = gl.projects.get(s_id, retry_transient_errors=True)
    #print(dir(project))
    project.archive()
    #break


