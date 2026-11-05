--
-- Target DBMS : PostgreSQL 9.x+
--

CREATE DATABASE uudex;
\c uudex
--
-- TABLE: auth_group
--

CREATE TABLE auth_group(
    group_id           serial          NOT NULL,
    group_uuid         char(36)        NOT NULL,
    group_name         varchar(40)     NOT NULL,
    description        varchar(255),
    create_datetime    timestamp       NOT NULL,
    update_datetime    timestamp       NOT NULL,
    CONSTRAINT pk_auth_group PRIMARY KEY (group_id)
)
;



--
-- TABLE: auth_role
--

CREATE TABLE auth_role(
    role_id            serial          NOT NULL,
    role_uuid          char(36)        NOT NULL,
    role_name          varchar(40)     NOT NULL,
    description        varchar(255),
    create_datetime    timestamp       NOT NULL,
    update_datetime    timestamp       NOT NULL,
    CONSTRAINT pk_auth_role PRIMARY KEY (role_id)
)
;



-- --
-- -- TABLE: contact
-- --

-- CREATE TABLE contact(
--     contact_id        serial         NOT NULL,
--     contact_name      varchar(30)    NOT NULL,
--     contact_number    varchar(15)    NOT NULL,
--     participant_id    int4           NOT NULL,
--     CONSTRAINT pk_contact PRIMARY KEY (contact_id)
-- )
-- ;



-- --
-- -- TABLE: dataset
-- --

-- CREATE TABLE dataset(
--     dataset_id                       serial           NOT NULL,
--     dataset_uuid                     char(36)         NOT NULL,
--     dataset_name                     varchar(255)     NOT NULL,
--     description                      varchar(255)     NOT NULL,
--     properties                       varchar(1024),
--     payload                          bytea            NOT NULL,
--     payload_size                     int4             NOT NULL,
--     payload_md5_hash                 char(32)         NOT NULL,
--     payload_compression_algorithm    varchar(15)      NOT NULL
--                                      CHECK (payload_compression_algorithm in ('LZMA', 'NONE', 'AVRO')),
--     version_number                   int4             NOT NULL,
--     create_datetime                  timestamp        NOT NULL,
--     owner_participant_id             int4             NOT NULL,
--     subject_id                       int4             NOT NULL,
--     CONSTRAINT pk_dataset PRIMARY KEY (dataset_id)
-- )
-- ;



-- --
-- -- TABLE: dataset_definition
-- --

-- CREATE TABLE dataset_definition(
--     dataset_definition_id      serial            NOT NULL,
--     dataset_definition_uuid    char(36)          NOT NULL,
--     dataset_definition_name    varchar(100)      NOT NULL,
--     description                varchar(255),
--     schema                     varchar(32768),
--     create_datetime            timestamp         NOT NULL,
--     CONSTRAINT pk_dataset_definition PRIMARY KEY (dataset_definition_id)
-- )
-- ;



-- --
-- -- TABLE: endpoint
-- --

-- CREATE TABLE endpoint(
--     endpoint_id           serial          NOT NULL,
--     endpoint_uuid         char(36)        NOT NULL,
--     endpoint_user_name    varchar(30)     NOT NULL,
--     certificate_dn        varchar(255)    NOT NULL,
--     description           varchar(255),
--     active_sw             char(1)         NOT NULL
--                           CHECK (upper(active_sw) in ('Y','N')),
--     create_datetime       timestamp       NOT NULL,
--     participant_id        int4            NOT NULL,
--     CONSTRAINT pk_endpoint PRIMARY KEY (endpoint_id)
-- )
-- ;



-- --
-- -- TABLE: grant_scope
-- --

-- CREATE TABLE grant_scope(
--     grant_scope_id      int4           NOT NULL,
--     grant_scope_name    varchar(40)
--                         CHECK (upper(grant_scope_name) in ('ALLOW_ONLY', 'ALLOW_EXCEPT', 'ALLOW_ALL', 'ALLOW_NONE')),
--     CONSTRAINT pk_permission_target_type PRIMARY KEY (grant_scope_id)
-- )
-- ;



-- --
-- -- TABLE: participant
-- --

-- CREATE TABLE participant(
--     participant_id            serial          NOT NULL,
--     participant_uuid          char(36)        NOT NULL,
--     participant_short_name    varchar(25)     NOT NULL,
--     participant_long_name     varchar(50)     NOT NULL,
--     description               varchar(255),
--     root_org_sw               char(1)         NOT NULL
--                               CHECK (upper(root_org_sw) in ('Y','N')),
--     active_sw                 char(1)         NOT NULL
--                               CHECK (active_sw in ('Y', 'N')),
--     create_datetime           timestamp       NOT NULL,
--     CONSTRAINT pk_participant PRIMARY KEY (participant_id)
-- )
-- ;



-- --
-- -- TABLE: privilege_allowed
-- --

-- CREATE TABLE privilege_allowed(
--     privilege_allowed_id      int4           NOT NULL,
--     privilege_allowed_name    varchar(40)
--                               CHECK (upper(privilege_allowed_name) in ('BROADEST_ALLOWED_PUBLISHER_ACCESS', 'BROADEST_ALLOWED_SUBSCRIBER_ACCESS', 'BROADEST_ALLOWED_MANAGER_ACCESS')),
--     CONSTRAINT pk_privilege_constraint PRIMARY KEY (privilege_allowed_id)
-- )
-- ;



-- --
-- -- TABLE: subject
-- --

-- CREATE TABLE subject(
--     subject_id                     serial          NOT NULL,
--     subject_uuid                   char(36)        NOT NULL,
--     subject_name                   varchar(300)    NOT NULL,
--     dataset_instance_key           varchar(100)    NOT NULL,
--     description                    varchar(300),
--     subscription_type              char(20)        NOT NULL
--                                    CHECK (upper(subscription_type) in ('MEASUREMENT_VALUES', 'EVENT')),
--     fulfillment_types_available    varchar(15)     NOT NULL
--                                    CHECK (upper(fulfillment_types_available) in ('DATA_PUSH', 'DATA_NOTIFY', 'BOTH')),
--     full_queue_behavior            varchar(20)
--                                    CHECK (upper(full_queue_behavior) in('BLOCK_NEW', 'PURGE_OLD', 'NO_CONSTRAINT')),
--     max_queue_size_kb              int4,
--     max_message_count              int4,
--     priority                       int4,
--     backing_exchange_name          varchar(300),
--     create_datetime                timestamp       NOT NULL,
--     owner_participant_id           int4            NOT NULL,
--     dataset_definition_id          int4            NOT NULL,
--     CONSTRAINT pk_subject PRIMARY KEY (subject_id)
-- )
-- ;



-- --
-- -- TABLE: subject_policy
-- --

-- CREATE TABLE subject_policy(
--     subject_policy_id           serial         NOT NULL,
--     subject_policy_uuid         char(36)       NOT NULL,
--     subject_policy_type         varchar(25)    NOT NULL
--                                 CHECK (upper(subject_policy_type) in ('PARTICIPANT_AND_DATASET', 'PARTICIPANT', 'DATASET', 'GLOBAL_DEFAULT')),
--     subject_policy_type_sort    int4           NOT NULL
--                                 CHECK (subject_policy_type_sort in(1,2,3,4)),
--     action                      varchar(10)    NOT NULL
--                                 CHECK (upper(action) in ('ALLOW', 'DENY', 'REVIEW')),
--     full_queue_behavior         varchar(20)
--                                 CHECK (upper(full_queue_behavior) in('BLOCK_NEW', 'PURGE_OLD', 'NO_CONSTRAINT')),
--     max_queue_size_kb           int4,
--     max_message_count           int4,
--     max_priority                int4,
--     target_participant_id       int4,
--     dataset_definition_id       int4,
--     CONSTRAINT pk_subject_creation_policy PRIMARY KEY (subject_policy_id)
-- )
-- ;



-- --
-- -- TABLE: subject_policy_acl_constraint
-- --

-- CREATE TABLE subject_policy_acl_constraint(
--     subject_policy_acl_constraint_id    serial    NOT NULL,
--     subject_policy_id                   int4      NOT NULL,
--     privilege_allowed_id                int4      NOT NULL,
--     grant_scope_id                      int4      NOT NULL,
--     CONSTRAINT pk_scp_constraint PRIMARY KEY (subject_policy_acl_constraint_id)
-- )
-- ;



-- --
-- -- TABLE: subject_policy_grant_allowed
-- --

-- CREATE TABLE subject_policy_grant_allowed(
--     sp_grant_allowed_id                 serial       NOT NULL,
--     object_uuid                         char(36)     NOT NULL,
--     object_type                         char(1)      NOT NULL
--                                         CHECK (lower(object_type) in ('e', 'p', 'g', 'r')),
--     create_datetime                     timestamp    NOT NULL,
--     subject_policy_acl_constraint_id    int4         NOT NULL,
--     CONSTRAINT pk_scp_permission_target PRIMARY KEY (sp_grant_allowed_id)
-- )
-- ;



-- --
-- -- TABLE: subscription
-- --

-- CREATE TABLE subscription(
--     subscription_id       serial         NOT NULL,
--     subscription_uuid     char(36)       NOT NULL,
--     subscription_name     varchar(30)    NOT NULL,
--     subscription_state    varchar(10)    NOT NULL
--                           CHECK (subscription_state in('ACTIVE', 'PAUSED')),
--     create_datetime       timestamp      NOT NULL,
--     owner_endpoint_id     int4           NOT NULL,
--     CONSTRAINT pk_subscription PRIMARY KEY (subscription_id)
-- )
-- ;



-- --
-- -- TABLE: subscription_subject
-- --

-- CREATE TABLE subscription_subject(
--     subscription_subject_id       serial          NOT NULL,
--     preferred_fulfillment_type    varchar(15)     NOT NULL
--                                   CHECK (upper(preferred_fulfillment_type) in ('DATA_PUSH', 'DATA_NOTIFY')),
--     backing_queue_name            varchar(255),
--     subject_id                    int4            NOT NULL,
--     subscription_id               int4            NOT NULL,
--     CONSTRAINT pk_subscription_subject PRIMARY KEY (subscription_subject_id)
-- )
-- ;



-- --
-- -- INDEX: uk_auth_group_1
-- --

-- CREATE UNIQUE INDEX uk_auth_group_1 ON auth_group(group_uuid)
-- ;
-- --
-- -- INDEX: uk_auth_group_2
-- --

-- CREATE UNIQUE INDEX uk_auth_group_2 ON auth_group(group_name)
-- ;
-- --
-- -- INDEX: uk_auth_role_1
-- --

-- CREATE UNIQUE INDEX uk_auth_role_1 ON auth_role(role_uuid)
-- ;
-- --
-- -- INDEX: uk_auth_role2
-- --

-- CREATE UNIQUE INDEX uk_auth_role2 ON auth_role(role_name)
-- ;
-- --
-- -- INDEX: "Ref1848"
-- --

-- CREATE INDEX "Ref1848" ON contact(participant_id)
-- ;
-- --
-- -- INDEX: uk_dataset_1
-- --

-- CREATE UNIQUE INDEX uk_dataset_1 ON dataset(dataset_uuid)
-- ;
-- --
-- -- INDEX: "Ref345"
-- --

-- CREATE INDEX "Ref345" ON dataset(subject_id)
-- ;
-- --
-- -- INDEX: "Ref1852"
-- --

-- CREATE INDEX "Ref1852" ON dataset(owner_participant_id)
-- ;
-- --
-- -- INDEX: uk_dataset_definition_1
-- --

-- CREATE UNIQUE INDEX uk_dataset_definition_1 ON dataset_definition(dataset_definition_uuid)
-- ;
-- --
-- -- INDEX: uk_dataset_definition_2
-- --

-- CREATE UNIQUE INDEX uk_dataset_definition_2 ON dataset_definition(dataset_definition_name)
-- ;
-- --
-- -- INDEX: uk_endpoint_1
-- --

-- CREATE UNIQUE INDEX uk_endpoint_1 ON endpoint(certificate_dn)
-- ;
-- --
-- -- INDEX: uk_endpoint_2
-- --

-- CREATE UNIQUE INDEX uk_endpoint_2 ON endpoint(endpoint_uuid)
-- ;
-- --
-- -- INDEX: "Ref1829"
-- --

-- CREATE INDEX "Ref1829" ON endpoint(participant_id)
-- ;
-- --
-- -- INDEX: uk_participant_1
-- --

-- CREATE UNIQUE INDEX uk_participant_1 ON participant(participant_uuid)
-- ;
-- --
-- -- INDEX: uk_subject_1
-- --

-- CREATE UNIQUE INDEX uk_subject_1 ON subject(subject_name)
-- ;
-- --
-- -- INDEX: uk_subject_2
-- --

-- CREATE UNIQUE INDEX uk_subject_2 ON subject(subject_uuid)
-- ;
-- --
-- -- INDEX: "Ref4397"
-- --

-- CREATE INDEX "Ref4397" ON subject(dataset_definition_id)
-- ;
-- --
-- -- INDEX: "Ref1860"
-- --

-- CREATE INDEX "Ref1860" ON subject(owner_participant_id)
-- ;
-- --
-- -- INDEX: uk_subject_creation_policy_1
-- --

-- CREATE UNIQUE INDEX uk_subject_creation_policy_1 ON subject_policy(subject_policy_uuid)
-- ;
-- --
-- -- INDEX: "Ref4396"
-- --

-- CREATE INDEX "Ref4396" ON subject_policy(dataset_definition_id)
-- ;
-- --
-- -- INDEX: "Ref1869"
-- --

-- CREATE INDEX "Ref1869" ON subject_policy(target_participant_id)
-- ;
-- --
-- -- INDEX: scp_constraint_uk_1
-- --

-- CREATE UNIQUE INDEX scp_constraint_uk_1 ON subject_policy_acl_constraint(subject_policy_id, privilege_allowed_id)
-- ;
-- --
-- -- INDEX: "Ref3271"
-- --

-- CREATE INDEX "Ref3271" ON subject_policy_acl_constraint(subject_policy_id)
-- ;
-- --
-- -- INDEX: "Ref2882"
-- --

-- CREATE INDEX "Ref2882" ON subject_policy_acl_constraint(privilege_allowed_id)
-- ;
-- --
-- -- INDEX: "Ref3183"
-- --

-- CREATE INDEX "Ref3183" ON subject_policy_acl_constraint(grant_scope_id)
-- ;
-- --
-- -- INDEX: "Ref3381"
-- --

-- CREATE INDEX "Ref3381" ON subject_policy_grant_allowed(subject_policy_acl_constraint_id)
-- ;
-- --
-- -- INDEX: uk_subscription
-- --

-- CREATE UNIQUE INDEX uk_subscription ON subscription(subscription_name, owner_endpoint_id)
-- ;
-- --
-- -- INDEX: uk_subscription_2
-- --

-- CREATE UNIQUE INDEX uk_subscription_2 ON subscription(subscription_uuid)
-- ;
-- --
-- -- INDEX: "Ref164"
-- --

-- CREATE INDEX "Ref164" ON subscription(owner_endpoint_id)
-- ;
-- --
-- -- INDEX: uk_subscription_subject_1
-- --

-- CREATE UNIQUE INDEX uk_subscription_subject_1 ON subscription_subject(subscription_id, subject_id)
-- ;
-- --
-- -- INDEX: "Ref358"
-- --

-- CREATE INDEX "Ref358" ON subscription_subject(subject_id)
-- ;
-- --
-- -- INDEX: "Ref527"
-- --

-- CREATE INDEX "Ref527" ON subscription_subject(subscription_id)
-- ;
-- --
-- -- TABLE: contact
-- --

-- ALTER TABLE contact ADD CONSTRAINT "Refparticipant48"
--     FOREIGN KEY (participant_id)
--     REFERENCES participant(participant_id) ON DELETE CASCADE
-- ;


-- --
-- -- TABLE: dataset
-- --

-- ALTER TABLE dataset ADD CONSTRAINT "Refsubject45"
--     FOREIGN KEY (subject_id)
--     REFERENCES subject(subject_id)
-- ;

-- ALTER TABLE dataset ADD CONSTRAINT "Refparticipant52"
--     FOREIGN KEY (owner_participant_id)
--     REFERENCES participant(participant_id)
-- ;


-- --
-- -- TABLE: endpoint
-- --

-- ALTER TABLE endpoint ADD CONSTRAINT "Refparticipant29"
--     FOREIGN KEY (participant_id)
--     REFERENCES participant(participant_id) ON DELETE CASCADE
-- ;


-- --
-- -- TABLE: subject
-- --

-- ALTER TABLE subject ADD CONSTRAINT "Refdataset_definition97"
--     FOREIGN KEY (dataset_definition_id)
--     REFERENCES dataset_definition(dataset_definition_id)
-- ;

-- ALTER TABLE subject ADD CONSTRAINT "Refparticipant60"
--     FOREIGN KEY (owner_participant_id)
--     REFERENCES participant(participant_id)
-- ;


-- --
-- -- TABLE: subject_policy
-- --

-- ALTER TABLE subject_policy ADD CONSTRAINT "Refdataset_definition96"
--     FOREIGN KEY (dataset_definition_id)
--     REFERENCES dataset_definition(dataset_definition_id) ON DELETE CASCADE
-- ;

-- ALTER TABLE subject_policy ADD CONSTRAINT "Refparticipant69"
--     FOREIGN KEY (target_participant_id)
--     REFERENCES participant(participant_id)
-- ;


-- --
-- -- TABLE: subject_policy_acl_constraint
-- --

-- ALTER TABLE subject_policy_acl_constraint ADD CONSTRAINT "Refsubject_policy71"
--     FOREIGN KEY (subject_policy_id)
--     REFERENCES subject_policy(subject_policy_id) ON DELETE CASCADE
-- ;

-- ALTER TABLE subject_policy_acl_constraint ADD CONSTRAINT "Refprivilege_allowed82"
--     FOREIGN KEY (privilege_allowed_id)
--     REFERENCES privilege_allowed(privilege_allowed_id)
-- ;

-- ALTER TABLE subject_policy_acl_constraint ADD CONSTRAINT "Refgrant_scope83"
--     FOREIGN KEY (grant_scope_id)
--     REFERENCES grant_scope(grant_scope_id)
-- ;


-- --
-- -- TABLE: subject_policy_grant_allowed
-- --

-- ALTER TABLE subject_policy_grant_allowed ADD CONSTRAINT "Refsubject_policy_acl_constraint81"
--     FOREIGN KEY (subject_policy_acl_constraint_id)
--     REFERENCES subject_policy_acl_constraint(subject_policy_acl_constraint_id) ON DELETE CASCADE
-- ;


-- --
-- -- TABLE: subscription
-- --

-- ALTER TABLE subscription ADD CONSTRAINT "Refendpoint64"
--     FOREIGN KEY (owner_endpoint_id)
--     REFERENCES endpoint(endpoint_id) ON DELETE CASCADE
-- ;


-- --
-- -- TABLE: subscription_subject
-- --

-- ALTER TABLE subscription_subject ADD CONSTRAINT "Refsubject58"
--     FOREIGN KEY (subject_id)
--     REFERENCES subject(subject_id) ON DELETE CASCADE
-- ;

-- ALTER TABLE subscription_subject ADD CONSTRAINT "Refsubscription27"
--     FOREIGN KEY (subscription_id)
--     REFERENCES subscription(subscription_id) ON DELETE CASCADE
-- ;
