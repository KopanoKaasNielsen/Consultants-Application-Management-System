import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import Dashboard, {
  createDashboardQueryParams,
  fetchConsultantDashboard,
} from '../Dashboard.jsx';

const originalFetch = global.fetch;
const originalOpen = window.open;

const createMockResponse = (data) => ({
  ok: true,
  json: async () => data,
});

afterEach(() => {
  global.fetch = originalFetch;
  jest.clearAllMocks();
  window.open = originalOpen;
});

describe('fetchConsultantDashboard', () => {
  it('builds the expected query parameters', async () => {
    const mock = jest.fn().mockResolvedValue(createMockResponse({}));
    global.fetch = mock;

    await fetchConsultantDashboard({
      page: 2,
      pageSize: 50,
      status: ['approved', 'submitted'],
      dateFrom: '2024-01-01',
      dateTo: '2024-01-31',
      search: 'alice',
      sort: 'name',
      category: 'Legal',
    });

    expect(mock).toHaveBeenCalledTimes(1);
    const requestUrl = mock.mock.calls[0][0];
    const url = new URL(requestUrl, 'http://example.com');
    expect(url.pathname).toBe('/api/staff/consultants/');
    expect(url.searchParams.get('page')).toBe('2');
    expect(url.searchParams.get('page_size')).toBe('50');
    expect(url.searchParams.get('status')).toBe('approved,submitted');
    expect(url.searchParams.get('date_from')).toBe('2024-01-01');
    expect(url.searchParams.get('date_to')).toBe('2024-01-31');
    expect(url.searchParams.get('search')).toBe('alice');
    expect(url.searchParams.get('sort')).toBe('name');
    expect(url.searchParams.get('category')).toBe('Legal');
  });

  it('throws an error when the response is not ok', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 500 });

    await expect(fetchConsultantDashboard()).rejects.toThrow(
      'Failed to fetch consultant dashboard.',
    );
  });
});

describe('createDashboardQueryParams', () => {
  it('omits pagination values when disabled', () => {
    const params = createDashboardQueryParams(
      {
        page: 3,
        pageSize: 100,
        status: ['approved'],
        category: 'Financial',
      },
      { includePagination: false },
    );

    expect(params.has('page')).toBe(false);
    expect(params.has('page_size')).toBe(false);
    expect(params.get('status')).toBe('approved');
    expect(params.get('category')).toBe('Financial');
  });
});

describe('Dashboard component', () => {
  const completeResponse = {
    results: [
      {
        id: 1,
        name: 'Alice Johnson',
        email: 'alice@example.com',
        status: 'approved',
        status_display: 'Approved',
        submitted_at: '2024-01-01T10:00:00Z',
        documents: { is_complete: true, missing: [] },
      },
    ],
    pagination: {
      page: 1,
      page_size: 20,
      total_pages: 1,
      total_results: 1,
      has_next: false,
      has_previous: false,
    },
  };

  const missingResponse = {
    results: [
      {
        id: 2,
        name: 'Bob Example',
        email: 'bob@example.com',
        status: 'submitted',
        status_display: 'Submitted',
        submitted_at: '2024-02-10T15:30:00Z',
        documents: { is_complete: false, missing: ['ID document'] },
      },
    ],
    pagination: {
      page: 1,
      page_size: 20,
      total_pages: 1,
      total_results: 1,
      has_next: false,
      has_previous: false,
    },
  };

  it('renders consultant data from the API', async () => {
    global.fetch = jest.fn().mockResolvedValue(createMockResponse(completeResponse));

    render(<Dashboard />);

    expect(await screen.findByText('Alice Johnson')).toBeInTheDocument();
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Approved' })).toBeInTheDocument();
    expect(screen.getByText('Complete')).toBeInTheDocument();
    expect(screen.getByText('1 consultant(s) found.')).toBeInTheDocument();
  });

  it('refetches data when filters change', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(createMockResponse(completeResponse))
      .mockResolvedValueOnce(createMockResponse(missingResponse));

    render(<Dashboard />);

    expect(await screen.findByText('Alice Johnson')).toBeInTheDocument();

    const statusSelect = screen.getByLabelText('Status');
    fireEvent.change(statusSelect, { target: { value: 'submitted' } });

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));

    const secondUrl = global.fetch.mock.calls[1][0];
    const parsedUrl = new URL(secondUrl, 'http://example.com');
    expect(parsedUrl.searchParams.get('status')).toBe('submitted');
    expect(parsedUrl.searchParams.get('page')).toBe('1');

    expect(await screen.findByText('Bob Example')).toBeInTheDocument();
    expect(screen.getByText('Missing: ID document')).toBeInTheDocument();
  });

  it('opens export links with active filters', async () => {
    global.fetch = jest.fn().mockResolvedValue(createMockResponse(completeResponse));
    window.open = jest.fn();

    render(<Dashboard />);

    expect(await screen.findByText('Alice Johnson')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Status'), {
      target: { value: 'approved' },
    });
    fireEvent.change(screen.getByLabelText('Consultant type'), {
      target: { value: 'Legal' },
    });
    fireEvent.change(screen.getByLabelText('Submitted from'), {
      target: { value: '2024-01-01' },
    });
    fireEvent.change(screen.getByLabelText('Submitted to'), {
      target: { value: '2024-01-31' },
    });
    fireEvent.change(screen.getByLabelText('Search'), {
      target: { value: 'alice' },
    });
    fireEvent.change(screen.getByLabelText('Sort by'), {
      target: { value: 'name' },
    });

    const csvButton = screen.getByRole('button', { name: 'Export as CSV' });
    fireEvent.click(csvButton);

    expect(window.open).toHaveBeenCalledTimes(1);
    const [exportUrl, target, features] = window.open.mock.calls[0];
    expect(target).toBe('_blank');
    expect(features).toBe('noopener');

    const parsed = new URL(exportUrl, 'http://example.com');
    expect(parsed.pathname).toBe('/api/staff/consultants/export/csv/');
    expect(parsed.searchParams.get('status')).toBe('approved');
    expect(parsed.searchParams.get('category')).toBe('Legal');
    expect(parsed.searchParams.get('date_from')).toBe('2024-01-01');
    expect(parsed.searchParams.get('date_to')).toBe('2024-01-31');
    expect(parsed.searchParams.get('search')).toBe('alice');
    expect(parsed.searchParams.get('sort')).toBe('name');
    expect(parsed.searchParams.has('page')).toBe(false);
    expect(parsed.searchParams.has('page_size')).toBe(false);
  });
});
