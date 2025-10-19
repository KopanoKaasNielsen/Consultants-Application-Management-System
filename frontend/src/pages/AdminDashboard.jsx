import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const STATUS_COLOURS = {
  approved: '#16a34a',
  pending: '#2563eb',
  rejected: '#dc2626',
  revoked: '#d97706',
};

export async function fetchAdminStats(endpoint = '/api/admin/stats/', options = {}) {
  const { token } = options;
  const headers = { Accept: 'application/json' };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(endpoint, { headers });
  if (!response.ok) {
    const error = new Error(`Failed to fetch admin stats (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function normaliseStatusBreakdown(breakdown) {
  if (!breakdown) {
    return [];
  }
  return [
    { key: 'approved', label: 'Approved', value: Number(breakdown.approved) || 0 },
    { key: 'pending', label: 'Pending', value: Number(breakdown.pending) || 0 },
    { key: 'rejected', label: 'Rejected', value: Number(breakdown.rejected) || 0 },
    { key: 'revoked', label: 'Revoked', value: Number(breakdown.revoked) || 0 },
  ];
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return Number(value).toLocaleString();
}

function buildMonthlyTrend(trend) {
  if (!Array.isArray(trend)) {
    return [];
  }
  return trend.map((entry) => ({
    month: entry.month || '—',
    total: Number(entry.total) || 0,
  }));
}

function buildCertificateData(statuses) {
  if (!Array.isArray(statuses)) {
    return [];
  }
  return statuses.map((status, index) => ({
    id: `${status.status || index}`,
    status: status.status || 'unknown',
    label: status.label || status.status || 'Unknown',
    count: Number(status.count) || 0,
  }));
}

function AdminDashboard({ endpoint = '/api/admin/stats/', token, initialData = null }) {
  const [stats, setStats] = useState(initialData);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(!initialData);

  useEffect(() => {
    let isMounted = true;
    if (initialData) {
      return () => {
        isMounted = false;
      };
    }

    async function loadStats() {
      setIsLoading(true);
      try {
        const payload = await fetchAdminStats(endpoint, { token });
        if (isMounted) {
          setStats(payload);
          setError(null);
        }
      } catch (loadError) {
        if (isMounted) {
          setError(loadError);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadStats();
    return () => {
      isMounted = false;
    };
  }, [endpoint, token, initialData]);

  const statusSummary = useMemo(
    () => normaliseStatusBreakdown(stats?.status_breakdown),
    [stats],
  );
  const monthlyTrend = useMemo(() => buildMonthlyTrend(stats?.monthly_trends), [stats]);
  const certificateData = useMemo(
    () => buildCertificateData(stats?.certificate_statuses),
    [stats],
  );

  if (error) {
    return (
      <div className="admin-dashboard" role="alert">
        <p>Could not load admin analytics. Please try again later.</p>
      </div>
    );
  }

  return (
    <div className="admin-dashboard" aria-live="polite">
      {isLoading && (
        <p className="text-muted" role="status">
          Loading analytics…
        </p>
      )}

      {stats && (
        <>
          <section className="admin-dashboard__summary" aria-label="Key metrics">
            <article className="summary-card">
              <h2>Total applications</h2>
              <p className="summary-value">{formatNumber(stats.total_applications)}</p>
            </article>
            {statusSummary.map((item) => (
              <article key={item.key} className="summary-card">
                <h3>{item.label}</h3>
                <p className="summary-value" data-status={item.key}>
                  {formatNumber(item.value)}
                </p>
              </article>
            ))}
          </section>

          <section className="admin-dashboard__charts" aria-label="Application trends">
            <article className="chart-card">
              <header>
                <h3>Monthly submissions</h3>
                <p className="text-muted">Applications grouped by submission month.</p>
              </header>
              {monthlyTrend.length ? (
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={monthlyTrend} margin={{ top: 16, right: 16, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Line type="monotone" dataKey="total" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-muted">No submission data available.</p>
              )}
            </article>

            <article className="chart-card">
              <header>
                <h3>Certificate statuses</h3>
                <p className="text-muted">Active vs revoked certificate distribution.</p>
              </header>
              {certificateData.length ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={certificateData} margin={{ top: 16, right: 16, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="count" fill="#d97706">
                      {certificateData.map((entry) => (
                        <Cell key={entry.id} fill={STATUS_COLOURS[entry.status] || '#6b7280'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-muted">No certificate analytics available.</p>
              )}
            </article>
          </section>
        </>
      )}
    </div>
  );
}

export default AdminDashboard;
