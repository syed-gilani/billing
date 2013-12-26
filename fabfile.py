#!/usr/bin/env python

import deploy.fab_common as common

#
# Configurations that are specific to this app
#
common.CommonFabTask.update_deployment_configs({
    "dev": {
        "app_name":"reebill-dev", 
        # TODO rename os_user to app_os_user for clarity and differentiation from host_os_configs
        "os_user":"reebill-dev", 
        "os_group":"reebill-dev",
        "default_deployment_dir":"/var/local/reebill-dev/billing",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/reebill-dev/billing",
            "www": "/var/local/reebill-dev/billing/www",
            "skyliner": "/var/local/reebill-dev/billing/skyliner",
            "doc": "/home/reebill-dev/doc",
            "mydoc": "/tmp",
        },
        "config_files": [
            ("conf/reebill-dev-template.cfg", "/var/local/reebill-dev/billing/reebill/reebill.cfg"),
        ],
    },
})
common.CommonFabTask.set_default_deployment_config_key("dev")
