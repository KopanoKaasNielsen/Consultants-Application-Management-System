import { act, render, screen, waitFor } from '@testing-library/react';

import ServiceHealth, { fetchServiceMetrics } from '../ServiceHealth.jsx';

const originalFetch = global.fetch;
const ResizeObserverMock = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

const createResponse = (data) => ({
  ok: true,
  json: async () => data,
});

afterEach(() => {
  jest.useRealTimers();
  global.fetch = originalFetch;
  delete global.ResizeObserver;
});

describe('fetchServiceMetrics', () => {
  it('throws an error when the response is not ok', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 500 });

    await expect(fetchServiceMetrics()).rejects.toThrow('Failed to fetch service metrics (500)');
  });
});

describe('ServiceHealth component', () => {
  const timestamp = new Date().toISOString();
  const baseMetrics = {
    timestamp,
    request_throughput_per_minute: 120,
    average_response_time_ms: 200,
    recent_errors: 2,
    top_endpoints: [{ endpoint: '/api/foo/', count: 12 }],
    active_alerts: [
      {
        id: 1,
        action: 'Login failure',
        endpoint: '/api/auth/login/',
        timestamp,
        severity: 'critical',
        details: { count: 4 },
      },
    ],
    throttle: {
      role_rates: { admin: '60/min' },
      per_role_limits: { admin: { requests: 60, window_seconds: 60 } },
    },
    celery: { status: 'healthy', queue_length: 4 },
  };

  beforeEach(() => {
    jest.useFakeTimers();
    global.ResizeObserver = ResizeObserverMock;
  });

  it('renders metrics from the API response', async () => {
    global.fetch = jest.fn().mockResolvedValue(createResponse(baseMetrics));

    render(<ServiceHealth />);

    expect(await screen.findByText('120')).toBeInTheDocument();
    expect(screen.getByText('healthy')).toBeInTheDocument();
    expect(screen.getByText('Login failure')).toBeInTheDocument();
    expect(screen.getByText('admin')).toBeInTheDocument();
  });

  it('refreshes metrics at the configured interval', async () => {
    const updatedMetrics = {
      ...baseMetrics,
      request_throughput_per_minute: 150,
      average_response_time_ms: 180,
    };

    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(createResponse(baseMetrics))
      .mockResolvedValueOnce(createResponse(updatedMetrics));

    render(<ServiceHealth refreshInterval={500} />);

    expect(await screen.findByText('120')).toBeInTheDocument();

    await act(async () => {
      jest.advanceTimersByTime(600);
      await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    });

    expect(await screen.findByText('150')).toBeInTheDocument();
  });
});
