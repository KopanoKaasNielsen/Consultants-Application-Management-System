# Admin Analytics Dashboard Suggestions

This document outlines implementation ideas and recommendations for building the admin analytics dashboard requested in the project brief.

## Access Control and Routing
- Add a Django class-based view (e.g., `AdminDashboardView`) under `consultant_app/views/admin_dashboard.py`.
- Decorate the view with `@staff_member_required` or extend `UserPassesTestMixin` to restrict access to superusers and staff.
- Map the `/admin-dashboard/` URL within `consultant_app/urls.py` to render the dashboard template.
- Protect the API endpoint `/api/admin/stats/` with DRF permissions such as `IsAdminUser`.

## Data Aggregation Endpoint
- Implement a DRF view (e.g., `AdminStatsView`) that returns aggregated counts for:
  - Total consultant applications.
  - Approved, pending, rejected, and revoked statuses.
- Compute monthly application trends using `Application.objects.annotate(month=TruncMonth(...))` and aggregate counts.
- Expose certificate status distribution by counting related certificate model states.
- Serialize the results with a dedicated serializer (`AdminStatsSerializer`) to ensure consistent JSON structure.

## Frontend Dashboard Page
- Create `frontend/src/pages/AdminDashboard.jsx` with React hooks to fetch data from `/api/admin/stats/` using a token-aware client.
- Use a responsive layout via CSS Grid or Flexbox to arrange metric cards and charts.
- Incorporate chart components (e.g., `recharts` or `chart.js`) to render:
  - Line chart: monthly application trends.
  - Bar or pie chart: distribution of certificate statuses.
- Handle loading and error states gracefully, displaying fallback UI when API calls fail.

## Template Integration
- Build a Django template `consultant_app/templates/admin_dashboard.html` that mounts the React component or provides server-rendered fallbacks.
- Ensure the template extends the admin base layout and includes necessary static assets.

## Testing Strategy
- Write unit tests for the DRF view verifying:
  - Access is restricted to staff/superusers.
  - Aggregated counts match fixture data.
- Add serializer tests to confirm the JSON schema.
- Implement frontend tests (e.g., Jest/React Testing Library) covering data fetching and chart rendering logic.

## Performance and UX Considerations
- Cache heavy aggregations using Django cache framework or `prefetch_related` to reduce database load.
- Paginate or limit historical data if the dataset is large.
- Ensure the dashboard layout is mobile-friendly using responsive breakpoints and touch-friendly chart components.

These suggestions aim to provide a structured approach for implementing the requested dashboard while meeting the outlined acceptance criteria.
