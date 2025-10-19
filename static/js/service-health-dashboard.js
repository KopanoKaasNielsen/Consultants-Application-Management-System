(function (global) {
  const HISTORY_LIMIT = 30;

  function formatNumber(value, options = {}) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return '—';
    }
    return Number(value).toLocaleString(undefined, options);
  }

  function formatTimestamp(isoString) {
    if (!isoString) {
      return { text: '—', machine: '' };
    }
    try {
      const date = new Date(isoString);
      return {
        text: date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        machine: date.toISOString(),
      };
    } catch (error) {
      return { text: isoString, machine: isoString };
    }
  }

  function buildLineChart(context) {
    return new Chart(context, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Requests per minute',
            data: [],
            borderColor: '#2563eb',
            backgroundColor: 'rgba(37, 99, 235, 0.2)',
            tension: 0.3,
            fill: true,
          },
          {
            label: 'Avg response (ms)',
            data: [],
            borderColor: '#f97316',
            backgroundColor: 'rgba(249, 115, 22, 0.2)',
            tension: 0.3,
            fill: true,
            yAxisID: 'y1',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'Requests' } },
          y1: {
            beginAtZero: true,
            position: 'right',
            grid: { drawOnChartArea: false },
            title: { display: true, text: 'Milliseconds' },
          },
        },
      },
    });
  }

  function buildBarChart(context) {
    return new Chart(context, {
      type: 'bar',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Requests',
            data: [],
            backgroundColor: '#0891b2',
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { beginAtZero: true },
        },
      },
    });
  }

  function updateLineChart(chart, history) {
    chart.data.labels = history.map((entry) => entry.label);
    chart.data.datasets[0].data = history.map((entry) => entry.throughput);
    chart.data.datasets[1].data = history.map((entry) => entry.responseTime);
    chart.update('none');
  }

  function updateBarChart(chart, endpoints) {
    chart.data.labels = endpoints.map((item) => item.endpoint || '—');
    chart.data.datasets[0].data = endpoints.map((item) => item.count || 0);
    chart.update('none');
  }

  function updateAlerts(container, emptyState, alerts) {
    container.innerHTML = '';
    if (!alerts || alerts.length === 0) {
      emptyState.hidden = false;
      container.hidden = true;
      return;
    }

    emptyState.hidden = true;
    container.hidden = false;

    alerts.forEach((alert) => {
      const item = document.createElement('li');
      item.className = `alert alert-${(alert.severity || 'info').toLowerCase()}`;
      const title = document.createElement('strong');
      title.textContent = alert.action || 'Unknown alert';
      item.appendChild(title);

      const meta = document.createElement('div');
      meta.className = 'alert-meta';
      const time = formatTimestamp(alert.timestamp);
      meta.textContent = `${time.text} • ${alert.endpoint || '—'}`;
      item.appendChild(meta);

      if (alert.details) {
        const details = document.createElement('pre');
        details.className = 'metadata';
        details.textContent = JSON.stringify(alert.details, null, 2);
        item.appendChild(details);
      }

      container.appendChild(item);
    });
  }

  function updateThrottleTable(tbody, throttle) {
    tbody.innerHTML = '';
    if (!throttle || !throttle.per_role_limits) {
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 3;
      cell.className = 'text-muted';
      cell.textContent = 'No throttle configuration available.';
      row.appendChild(cell);
      tbody.appendChild(row);
      return;
    }

    Object.entries(throttle.per_role_limits).forEach(([role, stats]) => {
      const row = document.createElement('tr');

      const roleCell = document.createElement('td');
      roleCell.textContent = role;
      row.appendChild(roleCell);

      const rateCell = document.createElement('td');
      rateCell.textContent = throttle.role_rates?.[role] || '—';
      row.appendChild(rateCell);

      const windowCell = document.createElement('td');
      windowCell.textContent = stats?.window_seconds ? formatNumber(stats.window_seconds) : '—';
      row.appendChild(windowCell);

      tbody.appendChild(row);
    });
  }

  function updateStatusIndicator(element, status) {
    if (!element) {
      return;
    }

    element.textContent = status || 'unknown';
    element.classList.remove('is-ok', 'is-warning', 'is-error');

    const normalised = String(status || '').toLowerCase();
    if (normalised === 'healthy') {
      element.classList.add('is-ok');
    } else if (normalised === 'idle') {
      element.classList.add('is-warning');
    } else {
      element.classList.add('is-error');
    }
  }

  function updateSummary(metrics) {
    document.getElementById('metric-throughput').textContent = formatNumber(
      metrics.request_throughput_per_minute,
    );
    document.getElementById('metric-response').textContent = formatNumber(
      metrics.average_response_time_ms,
      { maximumFractionDigits: 1 },
    );
    document.getElementById('metric-errors').textContent = formatNumber(metrics.recent_errors);
    document.getElementById('metric-queue').textContent = formatNumber(
      metrics.celery?.queue_length,
    );
  }

  function updateTimestamp(timestamp) {
    const element = document.getElementById('service-health-updated');
    const formatted = formatTimestamp(timestamp);
    element.textContent = formatted.text;
    element.setAttribute('datetime', formatted.machine);
  }

  function showError(message) {
    const element = document.getElementById('service-health-error');
    if (!element) {
      return;
    }
    element.hidden = false;
    element.textContent = message;
  }

  function clearError() {
    const element = document.getElementById('service-health-error');
    if (!element) {
      return;
    }
    element.hidden = true;
    element.textContent = '';
  }

  function createHistoryEntry(metrics) {
    const time = formatTimestamp(metrics.timestamp);
    return {
      label: time.text,
      timestamp: time.machine,
      throughput: Number(metrics.request_throughput_per_minute) || 0,
      responseTime: Number(metrics.average_response_time_ms) || 0,
    };
  }

  function init(config = {}) {
    const settings = {
      endpoint: config.endpoint || '/api/metrics/',
      refreshInterval: Number(config.refreshInterval) || 60000,
    };

    const lineChart = buildLineChart(document.getElementById('throughput-chart'));
    const barChart = buildBarChart(document.getElementById('endpoint-chart'));
    const alertsContainer = document.getElementById('alert-list');
    const alertsEmpty = document.getElementById('alert-empty');
    const throttleTableBody = document.getElementById('throttle-table-body');
    const statusBadge = document.getElementById('service-health-status');

    const state = { history: [] };

    async function fetchMetrics() {
      try {
        const response = await fetch(settings.endpoint, { headers: { 'Accept': 'application/json' } });
        if (!response.ok) {
          throw new Error(`Failed to load metrics (${response.status})`);
        }

        const metrics = await response.json();
        clearError();
        updateSummary(metrics);
        updateTimestamp(metrics.timestamp);
        updateStatusIndicator(statusBadge, metrics.celery?.status);
        updateAlerts(alertsContainer, alertsEmpty, metrics.active_alerts);
        updateThrottleTable(throttleTableBody, metrics.throttle);

        state.history.push(createHistoryEntry(metrics));
        if (state.history.length > HISTORY_LIMIT) {
          state.history.splice(0, state.history.length - HISTORY_LIMIT);
        }

        updateLineChart(lineChart, state.history);
        updateBarChart(barChart, metrics.top_endpoints || []);
      } catch (error) {
        showError(error.message || 'Unable to refresh service metrics.');
        updateStatusIndicator(statusBadge, 'unavailable');
      }
    }

    fetchMetrics();
    const timer = setInterval(fetchMetrics, settings.refreshInterval);

    if (global.addEventListener) {
      global.addEventListener('beforeunload', () => clearInterval(timer));
    }
  }

  global.SERVICE_HEALTH_DASHBOARD = Object.assign(global.SERVICE_HEALTH_DASHBOARD || {}, {
    init,
  });
})(window);
