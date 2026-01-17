require 'yaml'
require 'find'

module Gitlab
    class MergeRequestCheckHobot
        def initialize(project_id, target_branch, author_name, user_name)
            @project_id = project_id
            @target_branch = target_branch
            @author_name = author_name
            @user_name = user_name
            @ids = []
            @config_path = "/home/git/data/custom_hooks/config/mr"
        end

        def check_user
            if @author_name == @user_name
                puts "check user failed, user and author is same,you cannot merge"
                false
            else
                puts "check user sucessful"
                true
            end
        end

        def project_need_check?
            config_filename = @project_id.to_s + ".yaml"
            Find.find(@config_path) do |filepath|
              filename = filepath.split('/').select {|d| d != ""}.last
              if config_filename == filename
                return filepath
              end
            end
        end

        def get_config
            file_path = project_need_check?
            config = YAML.load_file(file_path)[0]
            return config
        end

        def check_white_list?
            config = get_config
            if config.keys.include?('superuser')
              if config['superuser']
                user_list = config['superuser'].split(',').select {|d| d != ""}
                if user_list.include?(@user_name)
                  puts "User is superuser, do not need check mr rule."
                  true
                else
                  puts "User is not a superuser, need check mr rule."
                  false
                end
              else
                puts "superuser is none"
                false
              end
            else
              puts "superuser field none, skip check superuser"
              false
            end
        end

        def check_mr_permission
          config = get_config
          puts config
          if config['branch'].keys.include?(@target_branch)
            user_str = config['branch'][@target_branch]['user']
            user_list = user_str.split(',').select {|d| d != ""}
            if !user_list.include?(@user_name)
              puts "check failed, no permission"
              false
            else
              puts "check successful, you can merge"
              true
            end
          else
            true
          end
        end

        def check
          if project_need_check?
            if check_white_list?
              true
            else
              check_user && check_mr_permission
            end
          else
            true
          end
        end
    end
end
