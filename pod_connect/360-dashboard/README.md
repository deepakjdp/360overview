# 360-Degree Dashboard

A plan and a working prototype for a 360 view across multiple applications (Claims, Capitation, Member Preference, Contact) and their upstream and downstream systems.

| Path | What it is |
|---|---|
| [`PLAN.md`](PLAN.md) | Phased delivery plan, architecture, roles, risks |
| [`templates/`](templates/) | CSV templates to fill in during discovery: applications, dependencies, business flows |
| [`prototype/`](prototype/) | Runnable Grafana + PostgreSQL demo with **synthetic** sample data |

---

## 1. Run the prototype

Requires Docker with Docker Compose.

```bash
cd 360-dashboard/prototype
docker compose up -d
```

Open http://localhost:3000 and log in with `admin` / `admin`. The dashboard **360 Overview (prototype, sample data)** is the home page.

Stop and remove everything:
```bash
docker compose down -v
```

Notes:
- Sample data is generated relative to the current time, so it always looks live. Restart with `docker compose down -v && docker compose up -d` to regenerate it.
- Postgres is also exposed on `localhost:5433` (user, password and database: `grafana` / `grafana` / `demo360`) if you want to explore the tables.
- Without Docker you can load [`db/01-schema.sql`](prototype/db/01-schema.sql) and [`db/02-seed.sql`](prototype/db/02-seed.sql) into any PostgreSQL 13+ database and add it to Grafana as a PostgreSQL data source with the UID `pg360`.

---

## 2. What you see

The demo story: **`claims-adjudication` went DOWN 30 minutes ago.** The dashboard shows how that spreads.

| Section | What it shows |
|---|---|
| **L1 Executive 360** | One tile per domain, coloured by the worst application in it. Capitation and Contact show **IMPACTED** because an upstream system is down. |
| **L2 Domain view** | Application status table, a dependency map (arrows = upstream → downstream, colour = status), and a hop table showing both ends of each interface. |
| **Claims** | Received, backlog, oldest waiting claim, rejection rate, 4-hour adjudication SLA, intake-to-paid time, and a per-hour flow chart. |
| **Capitation** | Monthly runs with status and a reconciliation check (records vs expected). |
| **Member Preference and Contact** | 15-minute propagation SLA, failed or pending changes, bounce rate, queue depth. |
| **L4 Transaction trace** | Type a claim ID in the **Claim ID** box at the top (for example `CLM-000042`) to see where it is and what happened to the same member. |

### Status meanings

| Status | Meaning |
|---|---|
| HEALTHY | Application up |
| DEGRADED | Up but slow or erroring |
| IMPACTED | The application itself is up, but an upstream application is DOWN, so it cannot work correctly |
| DOWN | Not responding |

The IMPACTED logic is the core of a 360 view. It lives in the `v_app_status` view in [`01-schema.sql`](prototype/db/01-schema.sql) and walks the `dependencies` table recursively, so the effect passes through any number of hops.

---

## 3. How the prototype is built

```
Postgres (sample tables + views)  ->  Grafana (SQL panels)
```

| Table | Purpose |
|---|---|
| `applications` | Inventory (from `templates/application-inventory.csv`) |
| `dependencies` | Upstream → downstream links (from `templates/dependency-map.csv`) |
| `app_health` | Health samples over time (status, latency, error rate, restarts) |
| `claims`, `capitation_runs`, `preference_changes`, `contact_requests` | Business data per domain |
| `v_latest_health`, `v_app_status` | Views that drive the status tiles, map and tables |

---

## 4. Moving from prototype to real data

1. **Fill in the templates** in [`templates/`](templates/) with your real applications, dependencies and flows. Load them into `applications` and `dependencies`, for example with `\copy` in `psql`.
2. **Feed `app_health`** from your real source. Pick whichever you have:
   - Prometheus: use it as a Grafana data source and rewrite the health panels with PromQL such as `up` or `kube_deployment_status_replicas_available`. The pod alerts in [`../openshift-alerts/`](../openshift-alerts/README.md) use the same metrics.
   - Synthetic checks: write Blackbox Exporter results (`probe_success`) into `app_health` using a small scheduled job.
   - Splunk: use a saved search or the Splunk data source plugin.
3. **Feed the business tables** with a scheduled ETL or CDC from a **read replica or reporting store**, never from production databases directly. Keep to the same columns, or adjust the panel queries.
4. **Use a shared key** (member ID plus a correlation ID) across systems so the L4 trace works end to end.
5. **Edit panels** in Grafana. Each panel is a plain SQL query, so changing a metric means editing SQL.
6. **Security:** claims and member data is PHI/PII. Before real data goes in, add Grafana roles and teams, mask or aggregate member-level fields, restrict the L4 panels, and get compliance sign-off. Change the default `admin` password and database credentials.

### Already using Splunk or Power BI?
The layout transfers directly: L1 domain tiles, L2 status and dependency view, domain KPIs, L4 trace. Reuse the SQL in [`grafana/dashboards/360-overview.json`](prototype/grafana/dashboards/360-overview.json) as a guide for the measures. In Splunk, use a lookup table for the dependencies and compute the IMPACTED status in the search.

---

## 5. Folder layout

```
360-dashboard/
  README.md
  PLAN.md
  templates/
    application-inventory.csv
    dependency-map.csv
    business-flows.csv
  prototype/
    docker-compose.yml
    db/
      01-schema.sql          tables and status views
      02-seed.sql            synthetic sample data
    grafana/
      provisioning/
        datasources/datasource.yml
        dashboards/dashboards.yml
      dashboards/
        360-overview.json    the dashboard
```

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| Panels show "No data" | Postgres still starting; wait 10 seconds and refresh. Check `docker compose logs postgres`. |
| Dashboard not listed | Check `docker compose logs grafana` for provisioning errors. |
| Port 3000 or 5433 in use | Change the left side of the `ports` mapping in `docker-compose.yml`. |
| Data looks stale or changes after a long time | Sample data is created once at start. Regenerate with `docker compose down -v && docker compose up -d`. |
| Dependency map empty | Grafana 10.x node graph needs both queries (A: nodes, B: edges). Do not remove either. |

---

## 7. Validation status

The SQL schema, seed data and all 25 panel queries were run against PostgreSQL 16 and returned results with no errors. The JSON and YAML files parse. I could not run Docker or Grafana in the environment where this was built, so the Grafana rendering (layout, colours, node graph) has not been visually checked. If a panel looks wrong, tell me which one and I'll adjust it.
