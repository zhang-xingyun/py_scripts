from configobj import ConfigObj


def ConfigParser(path_file):
    config_info = {}
    config = ConfigObj(path_file, list_values=True)

    config_info['ph_host'] = config['ph.server']['Ph_host']
    config_info['ph_token'] = config['ph.user']['Ph_token']
    config_info['credential_Phid'] = config['ph.user']['Credential_Phid']
    config_info['ph_repos'] = []
    config_info['logging_path'] = config['log']['logging_path']
    sections = config['ph.repo']
    repos_str = sections['repo']
    repos_list = repos_str.split('\n')
    for repo in repos_list:
        repo_dict = {}
        repo_list = repo.split(',')
        if len(repo_list) != 3:
            continue
        repo_dict['repo_name'] = repo_list[0]
        repo_dict['repo_desc'] = repo_list[1]
        repo_dict['gitlab_uri'] = repo_list[2]
        config_info['ph_repos'].append(repo_dict)
    return config_info
