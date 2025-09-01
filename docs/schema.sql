
-- create table sys_map
create table if not exists sys_map (
    N_ID integer primary key autoincrement,
    C_CATEGORY varchar(64) not null,

    C_LEFT varchar(64) not null,
    C_RIGHT varchar(64) not null,
    N_ORDER integer not null default 0,

    in_used tinyint not null default 0,
    created_at datetime not null default current_timestamp,
    updated_at datetime not null default current_timestamp on update current_timestamp,

    constraint uk_sys_map_category_left_right unique (C_CATEGORY, C_LEFT, C_RIGHT)
);

-- create table sys_map_category
create table if not exists sys_dict (
    N_ID integer primary key autoincrement,
    C_CATEGORY varchar(64) not null,

    N_KEY integer not null,
    C_VALUE varchar(64) not null,
    N_ORDER integer not null default 0,

    in_used integer not null default 0,
    created_at datetime not null default current_timestamp,
    updated_at datetime not null default current_timestamp on update current_timestamp,

    constraint uk_sys_dict_category_key unique (C_CATEGORY, N_KEY)
);
