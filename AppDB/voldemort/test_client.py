#!/usr/bin/env python

import py_voldemort
v = py_voldemort.AppVoldemort('localhost', 9090)

v.put('key1','value1')
v.get('key1')

v.put('key2','value2')
v.get('key2')

v.remove('key2')
v.get('key2')

users_columns = ["email","pw","date_creation","date_change","date_last_login","applications","appdrop_rem_token", "appdrop_rem_token_exp","visit_cnt",  "cookie", "cookie_ip","cookie_exp", "cksum"]
users_values = ["suwanny@gmail.com", "11", "2009", "2009", "2009", "bbs", "xxx", "xxx","1", "yyy", "0.0.0.0", "2009", "zzz"]

apps_columns = ["name", "version","owner","admins_list","host","port","creation_date",  "last_time_updated_date", "yaml_file",  "cksum", "num_entries"]
apps_values = ["name",  "version","owner","admins_list","host","port","creation_date",  "last_time_updated_date", "yaml_file",  "cksum", "num_entries"]

v.put_entity("users", "suwanny", users_columns, users_values)
v.get_entity("users","suwanny",users_columns)

v.put_entity("apps", "temp_app", apps_columns, apps_values)
v.get_entity("apps","temp_app",apps_columns)


