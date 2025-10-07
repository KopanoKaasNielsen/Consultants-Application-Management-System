# Deployment & Monitoring Notes

- The application exposes a lightweight health endpoint at `/health/` that returns a JSON payload containing the service status and database connectivity indicator.
- Configure your hosting platform or uptime monitoring tool to poll this endpoint for availability checks.
- Because the endpoint avoids opening new database connections, it remains responsive even when the database is under load or temporarily unavailable.
- JWT-protected dashboards expect tokens signed with ``JWT_AUTH_SECRET`` (defaults to ``SECRET_KEY`` when unset). Set ``JWT_AUTH_ALGORITHM`` (default ``HS256``) or ``JWT_AUTH_ALGORITHMS`` for multi-algorithm validation when configuring external identity providers.
