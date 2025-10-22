# Deployment & Monitoring Notes

- **Render multi-environment architecture**
  - Three Render web services are defined in `render.yaml`: `cams-dev`, `cams-staging`, and `cams-prod`. Each service tracks its own Git branch (`develop`, `staging`, and `main` respectively) and auto-deploys when commits land on the matching branch.
  - Each service provisions an isolated PostgreSQL database (`cams-*-db`) whose connection string is exposed to Django through both the shared `DATABASE_URL` and an environment-specific variable (`DEV_DATABASE_URL`, `STAGING_DATABASE_URL`, `PROD_DATABASE_URL`).
  - The Django settings modules (`backend.settings.dev`, `.staging`, `.prod`) read dedicated `*_ALLOWED_HOSTS` and `*_CSRF_TRUSTED_ORIGINS` variables, preventing development or staging URLs from leaking into production.
  - When running tests (detected via `PYTEST_CURRENT_TEST` or by setting `DJANGO_USE_TEST_DATABASE`), the development and staging settings automatically switch to the corresponding `*_TEST_DATABASE_URL` whenever it is provided. Configure those variables in CI to ensure pytest never touches live data.
  - Developers should branch from `develop`. Promotion follows Git Flow semantics: merge feature branches into `develop`, raise promotion PRs from `develop` → `staging` for UAT, and only promote into `main` once staging validation is complete. Each merge triggers the matching Render deployment without impacting the other environments.

- **Bootstrapping the staging environment**
  1. Create the `staging` branch in Git if it does not already exist (`git checkout -b staging` followed by `git push origin staging`). The Render blueprint will not trigger a build for the staging service until the branch exists remotely.
  2. Push at least one commit to `staging` so the first deployment can complete. Until that deployment finishes, requests to `https://cams-staging.onrender.com/` return Render's default "not found" response.
  3. After the initial build succeeds, confirm the service is live by hitting `https://cams-staging.onrender.com/health/`. The JSON payload should report `{ "status": "ok" }` when the container is up.
  4. Subsequent pushes to `staging` will redeploy automatically; the staging database (`cams-staging-db`) is preserved between deploys.

- The application exposes a lightweight health endpoint at `/health/` that returns a JSON payload containing the service status and database connectivity indicator.
- Configure your hosting platform or uptime monitoring tool to poll this endpoint for availability checks.
- Because the endpoint avoids opening new database connections, it remains responsive even when the database is under load or temporarily unavailable.
- JWT-protected dashboards expect tokens signed with ``JWT_AUTH_SECRET`` (defaults to ``SECRET_KEY`` when unset). Set ``JWT_AUTH_ALGORITHM`` (default ``HS256``) or ``JWT_AUTH_ALGORITHMS`` for multi-algorithm validation when configuring external identity providers.

## Docker & CI/CD Suggestions

The existing deployment can be extended to meet the "codex/setup-docker-deployment" goals with the following approach:

1. **Backend Dockerfile (Django API)**
   - Use an official Python base image (e.g., ``python:3.11-slim``).
   - Copy ``requirements.txt`` (and optional ``constraints.txt``) before the full source to leverage Docker layer caching.
   - Install system dependencies required by ``psycopg``/``psycopg2`` and any build tools (``libpq-dev``, ``gcc``, etc.).
   - Set ``PYTHONDONTWRITEBYTECODE=1`` and ``PYTHONUNBUFFERED=1`` for predictable behavior in containers.
   - Collect static files in a production stage (``python manage.py collectstatic --noinput``) and expose them via a shared volume or copy step.
   - Run the app with ``gunicorn`` or ``uvicorn`` behind ``daphne`` according to the project's ASGI/WSGI configuration.

2. **Frontend Dockerfile (React)**
   - Base on ``node:20-alpine`` (or the project's node version).
   - Install dependencies with ``npm ci`` (or ``yarn install --frozen-lockfile``) and build static assets.
   - Serve the production build through ``nginx`` or the framework's recommended static file server.

3. **docker-compose.yml**
   - Define separate services: ``web`` (Django), ``frontend`` (React build server or nginx), and ``db`` (PostgreSQL).
   - Configure a named volume for Postgres data persistence and another for Django static assets if the web container needs to share them with nginx.
   - Expose ports ``8000`` (API) and ``3000`` or ``80`` (frontend), wiring them behind an internal Docker network.
   - Pass environment variables via ``env_file`` pointing to ``.env`` and ``.env.frontend`` as needed.

4. **Environment Management**
   - Create ``.env.example`` enumerating all required variables (database credentials, ``DJANGO_SETTINGS_MODULE``, ``ALLOWED_HOSTS``, ``SECRET_KEY``, etc.).
   - Use Docker Compose profiles (``profile: ["dev"]`` vs. ``profile: ["prod"]``) to switch between local development and production-ready settings (e.g., enabling ``DEBUG`` only in development).

5. **Static Files & Media**
   - During the backend build, run ``collectstatic`` and place the output in a dedicated stage or shared volume.
   - If the React build assets should be served by Django, copy them into the ``static`` directory during ``collectstatic`` or mount the frontend build output into nginx.

6. **Startup Script**
   - Create an entrypoint script for the Django container that runs migrations (``python manage.py migrate``) before starting the application server. Include logic to wait for the Postgres service using ``wait-for-it`` or ``django-environ`` utilities.

7. **CI/CD Workflow**
   - Add a GitHub Actions workflow (e.g., ``.github/workflows/deploy.yml``) that:
     - Checks out code, sets up Python/Node, and caches dependencies.
     - Builds backend and frontend Docker images, runs unit tests via ``docker-compose run --rm web pytest`` (or ``python manage.py test``), and lints if applicable.
     - Pushes tagged images to the container registry (GitHub Packages, GHCR, or Docker Hub).
     - Triggers deployment steps (e.g., ``ssh`` to server, call to hosting provider, or infrastructure-as-code pipeline).

8. **Verification**
   - Validate the setup locally with ``docker-compose up --build`` to ensure both services and the database start cleanly.
   - Document troubleshooting steps (e.g., ensuring `.env` values are present, Postgres volume permissions) in ``DEPLOYMENT.md`` or a dedicated ``docs/docker.md`` file.
