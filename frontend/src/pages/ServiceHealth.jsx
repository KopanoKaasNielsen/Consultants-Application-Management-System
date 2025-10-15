import { useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export const DEFAULT_REFRESH_INTERVAL = 60000;
export const HISTORY_LIMIT = 30;

export async function fetchServiceMetrics(endpoint = '/api/metrics/') {
  const response = await fetch(endpoint, {
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    const error = new Error(`Failed to fetch service metrics (${response.status})`);
    error.status = response.status;
    throw error;
  }

  return response.json();
}

function normaliseTimestamp(isoString) {
  if (!isoString) {
    return { label: '—', timestamp: '' };
  }

  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) {
    return { label: isoString, timestamp: isoString };
  }

  return {
    label: parsed.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }),
    timestamp: parsed.toISOString(),
  };
}

function createHistorySnapshot(metrics) {
  const timestamp = normaliseTimestamp(metrics.timestamp);
  return {
    label: timestamp.label,
    timestamp: timestamp.timestamp,
    throughput: Number(metrics.request_throughput_per_minute) || 0,
    latency: Number(metrics.average_response_time_ms) || 0,
  };
}

function formatNumber(value, options = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return Number(value).toLocaleString(undefined, options);
}

function ServiceHealth({ endpoint = '/api/metrics/', refreshInterval = DEFAULT_REFRESH_INTERVAL }) {
  const [metrics, setMetrics] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadMetrics() {
      try {
        const payload = await fetchServiceMetrics(endpoint);
        if (!isMounted) {
          return;
        }
        setMetrics(payload);
        setHistory((previous) => {
          const next = [...previous, createHistorySnapshot(payload)];
          if (next.length > HISTORY_LIMIT) {
            next.splice(0, next.length - HISTORY_LIMIT);
          }
          return next;
        });
        setError(null);
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

    loadMetrics();
    const interval = setInterval(loadMetrics, refreshInterval);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [endpoint, refreshInterval]);

  const latestTimestamp = useMemo(() => {
    if (!metrics) {
      return null;
    }
    return normaliseTimestamp(metrics.timestamp);
  }, [metrics]);

  const historyData = useMemo(
    () =>
      history.map((entry) => ({
        label: entry.label,
        throughput: entry.throughput,
        latency: entry.latency,
      })),
    [history],
  );

  const topEndpoints = useMemo(() => {
    if (!metrics || !Array.isArray(metrics.top_endpoints)) {
      return [];
    }
    return metrics.top_endpoints.map((item, index) => ({
      id: index,
      endpoint: item.endpoint || '—',
      count: Number(item.count) || 0,
    }));
  }, [metrics]);

  const alerts = metrics?.active_alerts || [];
  const throttle = metrics?.throttle;
  const celery = metrics?.celery || {};

  return (
    <div className="service-health-dashboard" aria-live="polite">
      <header className="service-health-header">
        <div>
          <h1>Service health overview</h1>
          <p className="text-muted">
            Live metrics from audit logs, throttling configuration, and Celery workers.
          </p>
        </div>
        <div className="service-health-status">
          <span className="badge" data-status={celery.status || 'unknown'}>
            {celery.status || 'unknown'}
          </span>
          <small className="text-muted">
            Updated{' '}
            <time dateTime={latestTimestamp?.timestamp || ''}>{latestTimestamp?.label || '—'}</time>
          </small>
        </div>
      </header>

      <section className="service-health-metrics" aria-label="Key metrics">
        <article className="metric">
          <h2>Request throughput</h2>
          <p className="metric__value">{formatNumber(metrics?.request_throughput_per_minute)}</p>
          <p className="metric__description">Requests per minute</p>
        </article>
        <article className="metric">
          <h2>Average response</h2>
          <p className="metric__value">
            {formatNumber(metrics?.average_response_time_ms, { maximumFractionDigits: 1 })}
          </p>
          <p className="metric__description">Milliseconds (15 min window)</p>
        </article>
        <article className="metric">
          <h2>Recent errors</h2>
          <p className="metric__value">{formatNumber(metrics?.recent_errors)}</p>
          <p className="metric__description">Critical/high events</p>
        </article>
        <article className="metric">
          <h2>Queue depth</h2>
          <p className="metric__value">{formatNumber(celery.queue_length)}</p>
          <p className="metric__description">Celery active + scheduled tasks</p>
        </article>
      </section>

      <div className="service-health-charts">
        <section className="chart-panel" aria-label="Throughput and latency trend">
          <h3>Throughput trend</h3>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={historyData} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" />
              <YAxis yAxisId="left" stroke="#2563eb" allowDecimals={false} />
              <YAxis yAxisId="right" orientation="right" stroke="#f97316" />
              <Tooltip />
              <Legend />
              <Area
                yAxisId="left"
                type="monotone"
                name="Throughput"
                dataKey="throughput"
                stroke="#2563eb"
                fill="#2563eb"
                fillOpacity={0.2}
              />
              <Area
                yAxisId="right"
                type="monotone"
                name="Avg response (ms)"
                dataKey="latency"
                stroke="#f97316"
                fill="#f97316"
                fillOpacity={0.15}
              />
            </AreaChart>
          </ResponsiveContainer>
        </section>
        <section className="chart-panel" aria-label="Top endpoints">
          <h3>Top endpoints (60 min)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={topEndpoints} layout="vertical" margin={{ top: 16, right: 16, left: 16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" allowDecimals={false} />
              <YAxis type="category" dataKey="endpoint" width={220} />
              <Tooltip />
              <Bar dataKey="count" name="Requests" fill="#0891b2" />
            </BarChart>
          </ResponsiveContainer>
        </section>
      </div>

      <section className="service-health-alerts" aria-label="Active alerts">
        <h3>Active alerts</h3>
        {alerts.length === 0 ? (
          <p className="text-muted">No alerts detected within the past hour.</p>
        ) : (
          <ul className="alert-feed">
            {alerts.map((alert) => {
              const timestamp = normaliseTimestamp(alert.timestamp);
              return (
                <li key={alert.id || `${alert.action}-${timestamp.timestamp}`} className={`alert-item alert-${(alert.severity || 'info').toLowerCase()}`}>
                  <div className="alert-item__header">
                    <strong>{alert.action || 'Alert'}</strong>
                    <span className="alert-item__meta">
                      <span>{alert.endpoint || '—'}</span>
                      <time dateTime={timestamp.timestamp}>{timestamp.label}</time>
                    </span>
                  </div>
                  {alert.details ? (
                    <pre className="alert-item__details">{JSON.stringify(alert.details, null, 2)}</pre>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="service-health-throttle" aria-label="Throttle configuration">
        <h3>Throttle configuration</h3>
        {throttle?.per_role_limits ? (
          <table>
            <thead>
              <tr>
                <th scope="col">Role</th>
                <th scope="col">Rate</th>
                <th scope="col">Window (s)</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(throttle.per_role_limits).map(([role, info]) => (
                <tr key={role}>
                  <td>{role}</td>
                  <td>{throttle.role_rates?.[role] || '—'}</td>
                  <td>{formatNumber(info?.window_seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-muted">No throttle configuration detected.</p>
        )}
      </section>

      {error ? (
        <p role="alert" className="text-danger">
          {error.message || 'Unable to load service health metrics.'}
        </p>
      ) : null}

      {isLoading && !metrics ? <p className="text-muted">Loading metrics…</p> : null}
    </div>
  );
}

export default ServiceHealth;
