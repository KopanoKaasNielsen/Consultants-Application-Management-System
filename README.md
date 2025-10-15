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
