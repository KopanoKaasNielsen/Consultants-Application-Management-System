# Service Health Dashboard

The service health dashboard provides superusers with a consolidated view of live operational telemetry.

## Accessing the dashboard

* URL: `/admin/health/`
* Permissions: restricted to superusers or administrators assigned the `Admin` role.
* Refresh cadence: 60 seconds (configurable via `ADMIN_SERVICE_HEALTH_REFRESH_INTERVAL`).

## Data sources

The dashboard aggregates metrics from three core subsystems:

1. **AuditLog** – supplies request throughput, average response latency, error counts, and top endpoints.
2. **Role-based throttling** – exposes the configured Django REST Framework rate limits per role.
3. **Celery worker pool** – reports queue depth, worker availability, and task counts.

## API endpoint

Metrics are served by the authenticated API endpoint: `GET /api/metrics/`.

The payload includes:

| Field | Description |
| --- | --- |
| `request_throughput_per_minute` | Requests observed in the most recent minute. |
| `average_response_time_ms` | Mean response time from audit logs in the past 15 minutes. |
| `recent_errors` | Count of high or critical alerts raised in the last 15 minutes. |
| `top_endpoints` | Up to five endpoints with the highest traffic in the last hour. |
| `active_alerts` | Alerts surfaced in the last hour with severity data. |
| `throttle` | Role-based throttle configuration summary. |
| `celery` | Worker status, queue length, and task counts. |

## Front-end behaviour

* Visualisations are rendered with Chart.js (template) and Recharts (React component).
* The React page is located at `frontend/src/pages/ServiceHealth.jsx` with unit coverage in `frontend/src/pages/__tests__/ServiceHealth.test.jsx`.
* Automatic refresh keeps the timeline chart and metrics current.

## Troubleshooting

* If Celery is not configured locally, the queue metrics gracefully report an `unavailable` status.
* Throttle data comes directly from the role-based throttle class; ensure rate settings are present in `REST_FRAMEWORK["ROLE_BASED_THROTTLE_RATES"]` for custom roles.
