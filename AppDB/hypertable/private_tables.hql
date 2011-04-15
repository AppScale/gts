CREATE NAMESPACE "/appscale";
USE "/appscale";
CREATE TABLE USERS__(
	"email",
	"pw",
	"date_creation",
	"date_change",
	"date_last_login",
	"applications",
	"appdrop_rem_token",
	"appdrop_rem_token_exp",
	"visit_cnt",
	"cookie",
	"cookie_ip",
	"cookie_exp",
	"cksum",
        "enabled"
);

CREATE TABLE APPS__(
	"name",
	"language",
	"version",
	"owner",
	"admins_list",
	"host",
	"port",
	"creation_date",
	"last_time_updated_date",
	"yaml_file",
	"cksum",
        "num_entries",
        "tar_ball",
        "enabled",
        "classes",
        "indexes"
);

