(function (window, document) {
  'use strict';

  if (!window.React || !window.ReactDOM || !window.Recharts) {
    return;
  }

  var React = window.React;
  var Recharts = window.Recharts;
  var useEffect = React.useEffect;
  var useMemo = React.useMemo;
  var useState = React.useState;
  var createElement = React.createElement;

  var STATUS_COLOURS = {
    approved: '#16a34a',
    pending: '#2563eb',
    rejected: '#dc2626',
    revoked: '#d97706',
  };

  function parseInitialPayload(element) {
    if (!element || !element.dataset.initial) {
      return null;
    }
    try {
      return JSON.parse(element.dataset.initial);
    } catch (error) {
      console.warn('Failed to parse admin dashboard initial payload:', error); // eslint-disable-line no-console
      return null;
    }
  }

  function formatNumber(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return '—';
    }
    return Number(value).toLocaleString();
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

  function buildMonthlyTrend(trend) {
    if (!Array.isArray(trend)) {
      return [];
    }
    return trend.map(function (entry, index) {
      return {
        id: index,
        month: entry.month || '—',
        total: Number(entry.total) || 0,
      };
    });
  }

  function buildCertificateData(statuses) {
    if (!Array.isArray(statuses)) {
      return [];
    }
    return statuses.map(function (entry, index) {
      return {
        id: entry.status || index,
        status: entry.status || 'unknown',
        label: entry.label || entry.status || 'Unknown',
        count: Number(entry.count) || 0,
      };
    });
  }

  function fetchStats(endpoint) {
    if (!endpoint) {
      return Promise.resolve(null);
    }
    return window
      .fetch(endpoint, {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
      })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Failed to fetch admin stats (' + response.status + ')');
        }
        return response.json();
      });
  }

  function AdminDashboardApp(props) {
    var endpoint = props.endpoint;
    var initialData = props.initialData;

    var _useState = useState(initialData);
    var stats = _useState[0];
    var setStats = _useState[1];

    var _useState2 = useState(!initialData);
    var isLoading = _useState2[0];
    var setIsLoading = _useState2[1];

    var _useState3 = useState(null);
    var error = _useState3[0];
    var setError = _useState3[1];

    useEffect(
      function () {
        var isActive = true;
        if (!initialData) {
          setIsLoading(true);
          fetchStats(endpoint)
            .then(function (payload) {
              if (isActive && payload) {
                setStats(payload);
                setError(null);
              }
            })
            .catch(function (err) {
              if (isActive) {
                setError(err);
              }
            })
            .finally(function () {
              if (isActive) {
                setIsLoading(false);
              }
            });
        }
        return function () {
          isActive = false;
        };
      },
      [endpoint, initialData],
    );

    var statusSummary = useMemo(
      function () {
        return normaliseStatusBreakdown(stats && stats.status_breakdown);
      },
      [stats],
    );
    var monthlyTrend = useMemo(
      function () {
        return buildMonthlyTrend(stats && stats.monthly_trends);
      },
      [stats],
    );
    var certificateStatuses = useMemo(
      function () {
        return buildCertificateData(stats && stats.certificate_statuses);
      },
      [stats],
    );

    if (error) {
      return createElement(
        'p',
        { className: 'text-danger', role: 'alert' },
        'Unable to load admin analytics. Please refresh the page.',
      );
    }

    var summaryNodes = [
      createElement(
        'article',
        { key: 'total', className: 'summary-card' },
        createElement('h2', null, 'Total applications'),
        createElement('p', { className: 'summary-value' }, formatNumber(stats && stats.total_applications)),
      ),
    ].concat(
      statusSummary.map(function (item) {
        return createElement(
          'article',
          { key: item.key, className: 'summary-card' },
          createElement('h3', null, item.label),
          createElement(
            'p',
            { className: 'summary-value', 'data-status': item.key },
            formatNumber(item.value),
          ),
        );
      }),
    );

    var monthlyChart = monthlyTrend.length
      ? createElement(
          Recharts.ResponsiveContainer,
          { width: '100%', height: 260 },
          createElement(
            Recharts.LineChart,
            { data: monthlyTrend, margin: { top: 16, right: 16, bottom: 0, left: 0 } },
            createElement(Recharts.CartesianGrid, { strokeDasharray: '3 3' }),
            createElement(Recharts.XAxis, { dataKey: 'month' }),
            createElement(Recharts.YAxis, { allowDecimals: false }),
            createElement(Recharts.Tooltip, null),
            createElement(Recharts.Line, {
              type: 'monotone',
              dataKey: 'total',
              stroke: '#2563eb',
              strokeWidth: 2,
              dot: { r: 3 },
            }),
          ),
        )
      : createElement('p', { className: 'text-muted' }, 'No submission data available.');

    var certificateChart = certificateStatuses.length
      ? createElement(
          Recharts.ResponsiveContainer,
          { width: '100%', height: 260 },
          createElement(
            Recharts.BarChart,
            { data: certificateStatuses, margin: { top: 16, right: 16, bottom: 0, left: 0 } },
            createElement(Recharts.CartesianGrid, { strokeDasharray: '3 3' }),
            createElement(Recharts.XAxis, { dataKey: 'label' }),
            createElement(Recharts.YAxis, { allowDecimals: false }),
            createElement(Recharts.Tooltip, null),
            createElement(Recharts.Legend, null),
            createElement.apply(null, [
              Recharts.Bar,
              { dataKey: 'count', fill: '#d97706' },
            ].concat(
              certificateStatuses.map(function (entry) {
                return createElement(Recharts.Cell, {
                  key: entry.id,
                  fill: STATUS_COLOURS[entry.status] || '#6b7280',
                });
              }),
            )),
          ),
        )
      : createElement('p', { className: 'text-muted' }, 'No certificate analytics available.');

    return createElement(
      'div',
      { className: 'admin-dashboard-react' },
      isLoading
        ? createElement('p', { className: 'text-muted', role: 'status' }, 'Loading analytics…')
        : null,
      stats
        ? [
            createElement(
              'section',
              { key: 'summary', className: 'admin-dashboard__summary', 'aria-label': 'Key metrics' },
              summaryNodes,
            ),
            createElement(
              'section',
              { key: 'charts', className: 'admin-dashboard__charts', 'aria-label': 'Analytics charts' },
              createElement(
                'article',
                { key: 'monthly', className: 'chart-card' },
                createElement('header', null, [
                  createElement('h3', { key: 'title' }, 'Monthly submissions'),
                  createElement(
                    'p',
                    { key: 'subtitle', className: 'text-muted' },
                    'Applications grouped by submission month.',
                  ),
                ]),
                monthlyChart,
              ),
              createElement(
                'article',
                { key: 'certificates', className: 'chart-card' },
                createElement('header', null, [
                  createElement('h3', { key: 'title' }, 'Certificate statuses'),
                  createElement(
                    'p',
                    { key: 'subtitle', className: 'text-muted' },
                    'Active vs revoked certificate distribution.',
                  ),
                ]),
                certificateChart,
              ),
            ),
          ]
        : null,
    );
  }

  function mount() {
    var root = document.getElementById('admin-dashboard-root');
    if (!root) {
      return;
    }
    var endpoint = root.dataset.endpoint;
    var initialData = parseInitialPayload(root);
    var appRoot = window.ReactDOM.createRoot(root);
    appRoot.render(
      createElement(AdminDashboardApp, {
        endpoint: endpoint,
        initialData: initialData,
      }),
    );
  }

  document.addEventListener('DOMContentLoaded', mount);
})(window, document);
