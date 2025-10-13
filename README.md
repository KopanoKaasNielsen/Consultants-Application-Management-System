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
