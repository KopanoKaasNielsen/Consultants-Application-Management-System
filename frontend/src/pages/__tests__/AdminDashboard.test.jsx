import { render, screen, waitFor } from '@testing-library/react';

import AdminDashboard, { fetchAdminStats } from '../AdminDashboard.jsx';

const originalFetch = global.fetch;
const ResizeObserverMock = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

afterEach(() => {
  global.fetch = originalFetch;
  delete global.ResizeObserver;
});

describe('fetchAdminStats', () => {
  it('throws when the response is not ok', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 500 });

    await expect(fetchAdminStats('/api/admin/stats/')).rejects.toThrow(
      'Failed to fetch admin stats (500)',
    );
  });

  it('attaches an authorization header when provided', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({}) });

    await fetchAdminStats('/api/secure/', { token: 'abc123' });

    expect(global.fetch).toHaveBeenCalledWith('/api/secure/', {
      headers: {
        Accept: 'application/json',
        Authorization: 'Bearer abc123',
      },
    });
  });
});

describe('AdminDashboard component', () => {
  const baseStats = {
    total_applications: 4,
    status_breakdown: {
      approved: 2,
      pending: 1,
      rejected: 1,
      revoked: 0,
    },
    monthly_trends: [
      { month: '2024-01-01', total: 1 },
      { month: '2024-02-01', total: 3 },
    ],
    certificate_statuses: [
      { status: 'valid', label: 'Valid', count: 3 },
      { status: 'revoked', label: 'Revoked', count: 1 },
    ],
  };

  beforeEach(() => {
    global.ResizeObserver = ResizeObserverMock;
  });

  it('renders summary metrics from initial data', () => {
    render(<AdminDashboard initialData={baseStats} />);

    expect(screen.getByText('Total applications')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  it('loads data from the API when no initial data is provided', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => baseStats });

    render(<AdminDashboard endpoint="/api/test/" />);

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(await screen.findByText('4')).toBeInTheDocument();
    expect(screen.getByText('Revoked')).toBeInTheDocument();
  });

  it('renders an error message when the request fails', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('Network down'));

    render(<AdminDashboard endpoint="/api/fail/" />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not load admin analytics',
    );
  });
});
