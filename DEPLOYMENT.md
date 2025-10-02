# Deployment & Monitoring Notes

- The application exposes a lightweight health endpoint at `/health/` that returns a JSON payload containing the service status and database connectivity indicator.
- Configure your hosting platform or uptime monitoring tool to poll this endpoint for availability checks.
- Because the endpoint avoids opening new database connections, it remains responsive even when the database is under load or temporarily unavailable.
