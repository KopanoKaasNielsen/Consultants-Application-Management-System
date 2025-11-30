# Project Structure

This document outlines the main directories in the Consultants Application Management System and their purposes.

## Top-level layout

- `apps/` – Django apps for domain areas such as users, consultants, vetting, decisions, certificates, and API utilities.
- `backend/` – Django project configuration including ASGI/WSGI entrypoints and settings modules.
- `consultant_app/` – Supporting utilities, configuration, and Celery tasks that integrate across multiple apps.
- `frontend/` – Frontend assets and build configuration for the client-facing interface.
- `static/` and `staticfiles/` – Static assets used by Django and collected files for deployment.
- `templates/` – Django templates for dashboards, authentication, and workflow-specific pages.
- `tests/` – Pytest-based integration and feature tests.
- `scripts/` – Helper scripts for maintenance tasks and operational automation.
- `docs/` – Project documentation, including this project structure overview.

## Django apps (`apps/`)

Each subdirectory inside `apps/` is a Django app with conventional `models.py`, `views.py`, `urls.py`, and `tests/` modules. Highlights include:

- `apps/api/` – API-specific utilities such as serializers, permissions, throttling, and view definitions.
- `apps/consultants/` – Consultant registration and lifecycle logic, including email handling, signals, and background tasks.
- `apps/certificates/` – Certificate models, forms, and services for managing issued documents.
- `apps/decisions/` – Decision workflows, emails, and task orchestration for application reviews.
- `apps/security/` – Security utilities, serializers, and management commands.
- `apps/users/` – User-facing features such as JWT utilities, consumers, permissions, reports, and templates.
- `apps/vetting/` – Vetting workflow pages and models.

## Project configuration (`backend/`)

- `backend/settings/` – Environment-specific settings split into `base.py`, `dev.py`, and `prod.py`.
- `backend/urls.py` – Root URL configuration.
- `backend/asgi.py` and `backend/wsgi.py` – ASGI and WSGI entrypoints.
- `backend/routing.py` – Channels routing configuration.
- `backend/health.py` – Health check endpoint for deployments.

## Cross-cutting utilities (`consultant_app/`)

- `consultant_app/apps.py` – Django app configuration for shared utilities.
- `consultant_app/settings.py` – Additional settings consumed by background tasks and integrations.
- `consultant_app/tasks/` – Celery task implementations and scheduling helpers.
- `consultant_app/management/commands/` – Custom Django management commands.
- `consultant_app/signals.py` – Signal handlers that coordinate behaviors across apps.
- `consultant_app/serializers.py` and `consultant_app/certificates.py` – Shared serializers and certificate helpers.

## Tests (`tests/`)

Pytest is configured through `pytest.ini` and `conftest.py`. Integration-oriented tests live in the `tests/` directory and target key user flows (consultant submissions, staff notifications, etc.).

## Utilities and scripts

- `scripts/` – Automation scripts for tasks like seeding data or running checks.
- `build.sh` and `bootstrap_env.py` – Environment setup and build helpers.
- `check_dependencies.py` – Dependency validation for the runtime environment.

## Deployment

- `render.yaml` – Render deployment definition.
- `DEPLOYMENT.md` – Documentation for deployment workflows and infrastructure considerations.

## Additional resources

- `README.md` – Primary project overview and setup instructions.
- `CONTRIBUTING.md` – Guidance for contributors.
- `requirements.txt` – Python dependencies.
- `manage.py` – Django management entrypoint for running commands, migrations, and development servers.

