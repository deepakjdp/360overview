-- Sample data, relative to now() so the dashboard always looks "live".
-- Story: claims-adjudication (APP-002) went DOWN 30 minutes ago, so Capitation and
-- Contact are marked IMPACTED and new claims are piling up unadjudicated.
-- All data is synthetic. No real member information.

SELECT setseed(0.42);

INSERT INTO applications VALUES
 ('APP-001','claims-intake',      'Claims',            1,'Claims Team',     'OpenShift'),
 ('APP-002','claims-adjudication','Claims',            1,'Claims Team',     'OpenShift'),
 ('APP-003','capitation-engine',  'Capitation',        1,'Capitation Team', 'OpenShift'),
 ('APP-004','member-preference',  'Member Preference', 2,'Member Team',     'OpenShift'),
 ('APP-005','contact-service',    'Contact',           2,'Contact Team',    'OpenShift'),
 ('APP-006','provider-portal',    'Claims',            2,'Portal Team',     'VM'),
 ('APP-007','payment-gateway',    'Capitation',        1,'Payments Team',   'SaaS');

INSERT INTO dependencies VALUES
 ('APP-006','APP-001','REST',     'High'),
 ('APP-001','APP-002','Kafka',    'High'),
 ('APP-002','APP-003','File/SFTP','Medium'),
 ('APP-002','APP-005','REST',     'Medium'),
 ('APP-004','APP-005','REST',     'High'),
 ('APP-003','APP-007','File/SFTP','High');

-- Health: one sample every 5 minutes for the last 24h
INSERT INTO app_health (app_id, checked_at, status, latency_ms, error_rate_pct, pod_restarts)
SELECT app_id, t, status,
       CASE status WHEN 'DOWN' THEN NULL
                   WHEN 'DEGRADED' THEN 800 + floor(random()*1200)::int
                   ELSE 80 + floor(random()*120)::int END,
       CASE status WHEN 'DOWN' THEN 100
                   WHEN 'DEGRADED' THEN round((5 + random()*10)::numeric, 1)
                   ELSE round((random()*1)::numeric, 1) END,
       CASE status WHEN 'DOWN' THEN 5 WHEN 'DEGRADED' THEN 1 ELSE 0 END
FROM (
    SELECT a.app_id, t,
           CASE WHEN a.app_id = 'APP-002' AND t > now() - interval '30 minutes' THEN 'DOWN'
                WHEN a.app_id = 'APP-005' AND t > now() - interval '15 minutes' THEN 'DEGRADED'
                WHEN t < now() - interval '1 hour' AND random() < 0.01 THEN 'DEGRADED'
                ELSE 'UP' END AS status
    FROM applications a
    CROSS JOIN generate_series(now() - interval '24 hours', now(), interval '5 minutes') t
    OFFSET 0
) x;

-- Claims: 1200 over the last 48h. Nothing adjudicated in the last 30 min (outage).
INSERT INTO claims (claim_id, member_id, received_at, adjudicated_at, paid_at, status, amount)
WITH base AS MATERIALIZED (
    SELECT g,
           'MEM-' || lpad((1 + floor(random()*400))::int::text, 5, '0') AS member_id,
           now() - random() * interval '48 hours'          AS received_at,
           random() * random() * interval '6 hours'        AS adj_delay,
           random() * interval '12 hours'                  AS pay_delay,
           random()                                        AS r_reject,
           round((50 + random()*1950)::numeric, 2)         AS amount
    FROM generate_series(1, 1200) g
), calc AS MATERIALIZED (
    SELECT *,
           received_at + adj_delay AS adj_at,
           CASE WHEN received_at + adj_delay > now() - interval '30 minutes' THEN 'RECEIVED'
                WHEN r_reject < 0.05 THEN 'REJECTED'
                WHEN received_at + adj_delay + pay_delay > now() THEN 'ADJUDICATED'
                ELSE 'PAID' END AS status
    FROM base
)
SELECT 'CLM-' || lpad(g::text, 6, '0'),
       member_id,
       received_at,
       CASE WHEN status = 'RECEIVED' THEN NULL ELSE adj_at END,
       CASE WHEN status = 'PAID' THEN adj_at + pay_delay END,
       status,
       amount
FROM calc;

-- Capitation: monthly runs for the last 6 months (one failed, current one running)
INSERT INTO capitation_runs (run_month, started_at, finished_at, status, record_count, expected_count, amount_total)
SELECT m,
       CASE WHEN i = 0 THEN LEAST(m + interval '1 day 2 hours', now() - interval '1 hour')
            ELSE m + interval '1 day 2 hours' END,
       CASE WHEN i = 0 THEN NULL ELSE m + interval '1 day 5 hours' END,
       CASE WHEN i = 0 THEN 'RUNNING' WHEN i = 2 THEN 'FAILED' ELSE 'COMPLETED' END,
       CASE WHEN i = 0 THEN 21000 WHEN i = 2 THEN 41200 ELSE 48000 END,
       48000,
       CASE WHEN i = 0 THEN 3150000 WHEN i = 2 THEN 6180000 ELSE 7200000 END
FROM (
    SELECT i, (date_trunc('month', now()) - make_interval(months => i))::date AS m
    FROM generate_series(0, 5) i
) r;

-- Member preference changes: 800 over 48h, propagated to Contact, mostly within 15 min
INSERT INTO preference_changes (member_id, changed_at, delivered_at, status)
WITH base AS MATERIALIZED (
    SELECT 'MEM-' || lpad((1 + floor(random()*400))::int::text, 5, '0') AS member_id,
           now() - random() * interval '48 hours' AS changed_at,
           random() * random() * interval '20 minutes' AS delay,
           random() AS r
    FROM generate_series(1, 800)
)
SELECT member_id, changed_at,
       CASE WHEN changed_at + delay > now() - interval '15 minutes' OR r < 0.005 THEN NULL
            ELSE changed_at + delay END,
       CASE WHEN changed_at + delay > now() - interval '15 minutes' THEN 'PENDING'
            WHEN r < 0.005 THEN 'FAILED'
            ELSE 'DELIVERED' END
FROM base;

-- Contact requests: 1500 over 48h
INSERT INTO contact_requests (member_id, requested_at, channel, status, sent_at)
WITH base AS MATERIALIZED (
    SELECT 'MEM-' || lpad((1 + floor(random()*400))::int::text, 5, '0') AS member_id,
           now() - random() * interval '48 hours' AS requested_at,
           (ARRAY['EMAIL','SMS','MAIL','PHONE'])[1 + floor(random()*4)::int] AS channel,
           random() AS r
    FROM generate_series(1, 1500)
)
SELECT member_id, requested_at, channel,
       CASE WHEN requested_at > now() - interval '15 minutes' THEN 'QUEUED'
            WHEN r < 0.02 THEN 'FAILED'
            WHEN r < 0.07 THEN 'BOUNCED'
            ELSE 'SENT' END,
       CASE WHEN requested_at > now() - interval '15 minutes' OR r < 0.02 THEN NULL
            ELSE requested_at + random() * interval '2 minutes' END
FROM base;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO PUBLIC;
