# Consultants Application Management System

## Asynchronous confirmation emails

The consultant onboarding flow now ships with a lightweight Celery worker so the
submission confirmation email can be delivered outside the request/response
cycle.

1. **Configure Redis/Celery environment variables** (optional) – by default the
   project falls back to `redis://127.0.0.1:6379/0`.
   ```bash
   export CELERY_BROKER_URL="redis://127.0.0.1:6379/0"
   export CELERY_RESULT_BACKEND="redis://127.0.0.1:6379/0"
   ```
   The worker also honours `CELERY_TASK_ALWAYS_EAGER` and
   `CELERY_TASK_EAGER_PROPAGATES`, which are helpful for local testing.

2. **Start Redis** – for example using Docker:
   ```bash
   docker run --rm -p 6379:6379 redis:7
   ```

3. **Run the Celery worker** alongside Django:
   ```bash
   celery -A consultant_app.tasks worker -l info
   ```

4. **Queue a confirmation email manually** using the new management command. It
   accepts either a consultant primary key or the consultant's email address.
   ```bash
   python manage.py send_test_confirmation_email consultant@example.com
   ```

With `CELERY_TASK_ALWAYS_EAGER=true` the task executes synchronously, which is
useful when running the Django test suite or working without a running worker.

## Role-based access control

The CAMS dashboards enforce dedicated user roles backed by Django groups. To
initialise the required groups in a new environment run:

```bash
python manage.py seed_groups
```

After seeding the groups you can promote users to specific roles by assigning
them to the relevant group(s):

| Role        | Groups to assign                                                  |
|-------------|-------------------------------------------------------------------|
| Admin       | `Admins`                                                          |
| Staff       | `CounterStaff`, `BackOffice`, `DISAgents`, `SeniorImmigration` or `Staff` |
| Board       | `BoardCommittee`                                                  |
| Consultant  | `Consultants` or `Applicant`                                      |

Administrators can access the audit dashboard and impersonation tools, staff
members can work with vetting dashboards and analytics, board members access
decision dashboards, and consultants are restricted to their own application
portal.

### API role matrix

The REST API mirrors the same role-based restrictions. Use the table below to
identify which roles can access each endpoint:

| Endpoint | Method | Description | Allowed roles |
|----------|--------|-------------|----------------|
| `/api/consultants/validate/` | `POST` | Validate consultant registration fields for uniqueness. | Public (no authentication required) |
| `/api/staff/consultants/` | `GET` | Paginated consultant dashboard data. | Staff, Admin |
| `/api/staff/consultants/export/pdf/` | `GET` | Download the consultant dashboard as a PDF export. | Staff, Admin |
| `/api/staff/consultants/export/csv/` | `GET` | Download the consultant dashboard as a CSV export. | Staff, Admin |
| `/api/staff/logs/` | `GET` | View application audit log entries. | Staff, Admin |
| `/api/audit-logs/` | `GET` | Paginated security audit log entries with action metadata, client IP and context fields. | Admin |

The dedicated audit log endpoint is restricted to administrators because it
exposes potentially sensitive metadata such as the originating IP address and
structured context for each security event.

**Rate limits:** consultant tokens may perform up to 60 requests per minute, staff tokens are
limited to 30 requests per minute, and board tokens to 15 requests per minute. Admin tokens are
exempt from throttling.

## Monitoring and real-time alerts

Critical security events are surfaced through a combination of Sentry error
tracking, Slack notifications and email alerts. To enable the integrations set
the following environment variables:

```bash
export SENTRY_DSN="https://example.ingest.sentry.io/12345"
export SENTRY_ENVIRONMENT="production"  # Optional override for environment tagging

export SECURITY_ALERT_SLACK_WEBHOOK="https://hooks.slack.com/services/..."
export SECURITY_ALERT_EMAIL_RECIPIENTS="secops@example.com,platform@example.com"
export SECURITY_ALERT_EMAIL_SENDER="alerts@example.com"
export SECURITY_ALERT_EMAIL_SUBJECT_PREFIX="CAMS"
export SECURITY_ALERT_LOGIN_FAILURE_THRESHOLD="5"  # Override the default threshold
```

Any audit log entry flagged with a `critical` or `high` severity, certificate
revocations, HTTP 5xx errors or repeated login failures automatically trigger an
alert. Alerts contain contextual metadata (user, endpoint, IP address, etc.) and
are delivered via the configured Slack webhook and email recipients. Celery
dispatches the notifications, respecting the existing
`CELERY_TASK_ALWAYS_EAGER=true` shortcut for local testing.

The monitoring API at `/api/health/` provides a JSON summary including the
current database status, timestamp and the number of recent critical events (last
15 minutes). It can be used by uptime monitors to confirm that the alerting
pipeline is healthy.

## Sharing logs with ChatGPT Plus

Security-sensitive investigations sometimes need lightweight context from the
audit trail. The project now ships with a helper command that gathers recent
events into a redacted export that can be safely pasted into ChatGPT Plus (or
similar support channels) for debugging assistance without exposing client IP
addresses or user contact information by default.

```bash
python manage.py export_audit_logs --limit 20  # Markdown table ready for pasting
```

Use the `--format json` switch if you prefer a machine-readable export, and add
`--include-ip` or `--include-contact-details` if you explicitly need those
fields in the shared transcript.
