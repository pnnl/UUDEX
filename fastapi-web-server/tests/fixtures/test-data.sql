-- Insert known test data
INSERT INTO participant (
    participant_uuid,
    participant_short_name,
    participant_long_name,
    description,
    root_org_sw,
    active_sw,
    create_datetime
) VALUES (
    '4b3b819e-94bd-4adf-b461-17ccb58ac870',
    'Test Participant',
    'Test Participant Long Name',
    'Test Description',
    'Y',
    'Y',
    CURRENT_TIMESTAMP
);

-- Insert test endpoint with admin privileges
INSERT INTO endpoint (
    endpoint_uuid,
    endpoint_user_name,
    certificate_dn,
    description,
    active_sw,
    uudex_administrator_sw,      -- Set to Y for admin
    participant_administrator_sw, -- Set to Y for admin
    create_datetime,
    participant_id
) VALUES (
    '4b3b819e-94bd-4adf-b461-17ccb58ac870',
    'test_admin',
    '4b3b819e-94bd-4adf-b461-17ccb58ac870__app_rt_1',
    'Test Admin Endpoint',
    'Y',
    'Y',  -- UUDEX admin
    'Y',  -- Participant admin
    CURRENT_TIMESTAMP,
    1
);

-- Insert non-admin endpoint for testing permissions
INSERT INTO endpoint (
    endpoint_uuid,
    endpoint_user_name,
    certificate_dn,
    description,
    active_sw,
    uudex_administrator_sw,
    participant_administrator_sw,
    create_datetime,
    participant_id
) VALUES (
    '5c4c92af-05bd-4adf-b461-17ccb58ac871',
    'test_user',
    '5c4c92af-05bd-4adf-b461-17ccb58ac871__app_rt_1',
    'Test Regular User Endpoint',
    'Y',
    'N',  -- Not UUDEX admin
    'N',  -- Not participant admin
    CURRENT_TIMESTAMP,
    1
);

-- Add more test data as needed
