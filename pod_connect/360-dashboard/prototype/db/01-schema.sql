-- 360 dashboard prototype: schema + views.
-- Replace the sample tables with your real reporting store / ETL targets (see ../README.md).

CREATE TABLE applications (
    app_id      text PRIMARY KEY,
    app_name    text NOT NULL,
    domain      text NOT NULL,          -- Claims | Capitation | Member Preference | Contact
    tier        int  NOT NULL,          -- 1 = critical
    owner_team  text NOT NULL,
    platform    text NOT NULL
);

-- from_app_id is UPSTREAM of to_app_id (data/requests flow from -> to)
CREATE TABLE dependencies (
    from_app_id    text NOT NULL REFERENCES applications(app_id),
    to_app_id      text NOT NULL REFERENCES applications(app_id),
    interface_type text NOT NULL,       -- REST | Kafka | File/SFTP | MQ | DB
    criticality    text NOT NULL,
    PRIMARY KEY (from_app_id, to_app_id)
);

-- Health samples (in real life: from Prometheus / synthetic checks / Splunk)
CREATE TABLE app_health (
    app_id         text NOT NULL REFERENCES applications(app_id),
    checked_at     timestamptz NOT NULL,
    status         text NOT NULL CHECK (status IN ('UP','DEGRADED','DOWN')),
    latency_ms     int,
    error_rate_pct numeric(5,1),
    pod_restarts   int
);
CREATE INDEX app_health_app_time ON app_health (app_id, checked_at DESC);

CREATE TABLE claims (
    claim_id       text PRIMARY KEY,
    member_id      text NOT NULL,
    received_at    timestamptz NOT NULL,
    adjudicated_at timestamptz,
    paid_at        timestamptz,
    status         text NOT NULL,       -- RECEIVED | ADJUDICATED | PAID | REJECTED
    amount         numeric(12,2)
);
CREATE INDEX claims_received ON claims (received_at);

CREATE TABLE capitation_runs (
    run_id         serial PRIMARY KEY,
    run_month      date NOT NULL,
    started_at     timestamptz,
    finished_at    timestamptz,
    status         text NOT NULL,       -- RUNNING | COMPLETED | FAILED
    record_count   int,
    expected_count int,
    amount_total   numeric(14,2)
);

CREATE TABLE preference_changes (
    change_id    serial PRIMARY KEY,
    member_id    text NOT NULL,
    changed_at   timestamptz NOT NULL,
    delivered_at timestamptz,           -- when propagated to Contact
    status       text NOT NULL          -- DELIVERED | PENDING | FAILED
);
CREATE INDEX pref_changed ON preference_changes (changed_at);

CREATE TABLE contact_requests (
    request_id   serial PRIMARY KEY,
    member_id    text NOT NULL,
    requested_at timestamptz NOT NULL,
    channel      text NOT NULL,         -- EMAIL | SMS | MAIL | PHONE
    status       text NOT NULL,         -- SENT | BOUNCED | FAILED | QUEUED
    sent_at      timestamptz
);
CREATE INDEX contact_requested ON contact_requests (requested_at);

-- Latest health sample per application
CREATE VIEW v_latest_health AS
SELECT DISTINCT ON (app_id)
       app_id, checked_at, status, latency_ms, error_rate_pct, pod_restarts
FROM app_health
ORDER BY app_id, checked_at DESC;

-- Effective status per application, including impact from DOWN upstream systems.
-- status_code: 0 HEALTHY, 1 DEGRADED, 2 IMPACTED (an upstream is DOWN), 3 DOWN
CREATE VIEW v_app_status AS
WITH RECURSIVE down AS (
    SELECT app_id FROM v_latest_health WHERE status = 'DOWN'
),
impacted(app_id) AS (
    SELECT d.to_app_id
    FROM dependencies d JOIN down ON d.from_app_id = down.app_id
    UNION
    SELECT d.to_app_id
    FROM dependencies d JOIN impacted i ON d.from_app_id = i.app_id
)
SELECT a.app_id,
       a.app_name,
       a.domain,
       a.tier,
       a.owner_team,
       h.status AS own_status,
       h.latency_ms,
       h.error_rate_pct,
       h.pod_restarts,
       h.checked_at,
       s.code AS status_code,
       CASE s.code WHEN 0 THEN 'HEALTHY'
                   WHEN 1 THEN 'DEGRADED'
                   WHEN 2 THEN 'IMPACTED'
                   ELSE 'DOWN' END AS status
FROM applications a
JOIN v_latest_health h ON h.app_id = a.app_id
CROSS JOIN LATERAL (
    SELECT GREATEST(
        CASE h.status WHEN 'UP' THEN 0 WHEN 'DEGRADED' THEN 1 ELSE 3 END,
        CASE WHEN a.app_id IN (SELECT app_id FROM impacted) THEN 2 ELSE 0 END
    ) AS code
) s;
