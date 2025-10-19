import { useEffect, useMemo, useState } from 'react';

const DEFAULT_PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'incomplete', label: 'Incomplete' },
  { value: 'vetted', label: 'Vetted' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
];

const SORT_OPTIONS = [
  { value: '-date', label: 'Newest submissions' },
  { value: 'date', label: 'Oldest submissions' },
  { value: 'name', label: 'Name (A–Z)' },
  { value: '-name', label: 'Name (Z–A)' },
  { value: 'email', label: 'Email (A–Z)' },
  { value: '-email', label: 'Email (Z–A)' },
  { value: 'status', label: 'Status (A–Z)' },
  { value: '-status', label: 'Status (Z–A)' },
  { value: 'updated', label: 'Last updated (oldest first)' },
  { value: '-updated', label: 'Last updated (newest first)' },
];

function formatDate(value) {
  if (!value) {
    return '—';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString();
}

function buildStatusParam(status) {
  if (!status) {
    return '';
  }
  if (Array.isArray(status)) {
    return status.filter(Boolean).join(',');
  }
  return status;
}

export function createDashboardQueryParams(
  {
    page = 1,
    pageSize = DEFAULT_PAGE_SIZE,
    status = '',
    dateFrom,
    dateTo,
    search = '',
    sort = '-date',
    category = '',
  } = {},
  { includePagination = true } = {},
) {
  const params = new URLSearchParams();

  if (includePagination) {
    params.set('page', String(page));
    params.set('page_size', String(pageSize));
  }

  const statusParam = buildStatusParam(status);
  if (statusParam) {
    params.set('status', statusParam);
  }

  if (dateFrom) {
    params.set('date_from', dateFrom);
  }
  if (dateTo) {
    params.set('date_to', dateTo);
  }
  if (search) {
    params.set('search', search);
  }
  if (sort) {
    params.set('sort', sort);
  }
  if (category) {
    params.set('category', category);
  }

  return params;
}

export async function fetchConsultantDashboard(options = {}) {
  const params = createDashboardQueryParams(options);
  const url = `/api/staff/consultants/?${params.toString()}`;
  const response = await fetch(url);

  if (!response.ok) {
    const error = new Error('Failed to fetch consultant dashboard.');
    error.status = response.status;
    throw error;
  }

  return response.json();
}

export default function Dashboard() {
  const [filters, setFilters] = useState({
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    status: '',
    dateFrom: '',
    dateTo: '',
    search: '',
    sort: '-date',
    category: '',
  });
  const [dashboardData, setDashboardData] = useState({
    results: [],
    pagination: {
      page: 1,
      page_size: DEFAULT_PAGE_SIZE,
      total_pages: 1,
      total_results: 0,
      has_next: false,
      has_previous: false,
    },
  });
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadData() {
      setIsLoading(true);
      try {
        const data = await fetchConsultantDashboard({
          page: filters.page,
          pageSize: filters.pageSize,
          status: filters.status,
          dateFrom: filters.dateFrom || undefined,
          dateTo: filters.dateTo || undefined,
          search: filters.search || undefined,
          sort: filters.sort,
          category: filters.category || undefined,
        });

        if (isCancelled) {
          return;
        }

        setDashboardData(data);
        setError(null);

        setFilters((previous) => {
          if (previous.page !== data.pagination.page) {
            return { ...previous, page: data.pagination.page };
          }
          return previous;
        });
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError);
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isCancelled = true;
    };
  }, [filters]);

  const handleInputChange = (event) => {
    const { name, value } = event.target;
    setFilters((previous) => ({
      ...previous,
      [name]: value,
      page: 1,
    }));
  };

  const handlePageChange = (nextPage) => {
    setFilters((previous) => ({
      ...previous,
      page: nextPage,
    }));
  };

  const handleExport = (format) => {
    const params = createDashboardQueryParams(
      {
        status: filters.status,
        category: filters.category || undefined,
        dateFrom: filters.dateFrom || undefined,
        dateTo: filters.dateTo || undefined,
        search: filters.search || undefined,
        sort: filters.sort,
      },
      { includePagination: false },
    );

    const endpoint =
      format === 'pdf'
        ? '/api/staff/consultants/export/pdf/'
        : '/api/staff/consultants/export/csv/';
    const exportUrl = `${endpoint}?${params.toString()}`;
    window.open(exportUrl, '_blank', 'noopener');
  };

  const documentSummaries = useMemo(() => {
    return dashboardData.results.map((result) => {
      if (result.documents?.is_complete) {
        return 'Complete';
      }
      const missing = result.documents?.missing || [];
      if (missing.length === 0) {
        return 'Unknown';
      }
      return `Missing: ${missing.join(', ')}`;
    });
  }, [dashboardData.results]);

  const activePage = dashboardData.pagination.page;
  const totalResults = dashboardData.pagination.total_results;

  return (
    <div>
      <h1>Consultant applications dashboard</h1>

      <form className="filters" onSubmit={(event) => event.preventDefault()}>
        <div>
          <label htmlFor="search">Search</label>
          <input
            id="search"
            name="search"
            type="search"
            value={filters.search}
            onChange={handleInputChange}
            placeholder="Search by name or email"
          />
        </div>

        <div>
          <label htmlFor="status">Status</label>
          <select
            id="status"
            name="status"
            value={filters.status}
            onChange={handleInputChange}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value || 'all'} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="dateFrom">Submitted from</label>
          <input
            id="dateFrom"
            name="dateFrom"
            type="date"
            value={filters.dateFrom}
            onChange={handleInputChange}
          />
        </div>

        <div>
          <label htmlFor="dateTo">Submitted to</label>
          <input
            id="dateTo"
            name="dateTo"
            type="date"
            value={filters.dateTo}
            onChange={handleInputChange}
          />
        </div>

        <div>
          <label htmlFor="category">Consultant type</label>
          <input
            id="category"
            name="category"
            type="search"
            value={filters.category}
            onChange={handleInputChange}
            placeholder="e.g. Financial or Legal"
          />
        </div>

        <div>
          <label htmlFor="sort">Sort by</label>
          <select
            id="sort"
            name="sort"
            value={filters.sort}
            onChange={handleInputChange}
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </form>

      <div className="export-actions" aria-label="Export options">
        <button
          type="button"
          onClick={() =>
            handleExport('pdf')
          }
        >
          Export as PDF
        </button>
        <button
          type="button"
          onClick={() =>
            handleExport('csv')
          }
        >
          Export as CSV
        </button>
      </div>

      {error && (
        <div role="alert">
          Unable to load consultant data. Please try again later.
        </div>
      )}

      <table aria-label="Consultant applications">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Email</th>
            <th scope="col">Status</th>
            <th scope="col">Submitted</th>
            <th scope="col">Document validity</th>
          </tr>
        </thead>
        <tbody>
          {isLoading && (
            <tr>
              <td colSpan={5}>Loading consultant applications…</td>
            </tr>
          )}
          {!isLoading && dashboardData.results.length === 0 && (
            <tr>
              <td colSpan={5}>No consultant applications found.</td>
            </tr>
          )}
          {!isLoading &&
            dashboardData.results.map((result, index) => (
              <tr key={result.id}>
                <td>{result.name}</td>
                <td>{result.email}</td>
                <td>{result.status_display || result.status}</td>
                <td>{formatDate(result.submitted_at)}</td>
                <td>{documentSummaries[index]}</td>
              </tr>
            ))}
        </tbody>
      </table>

      <div className="pagination">
        <button
          type="button"
          onClick={() => handlePageChange(Math.max(1, activePage - 1))}
          disabled={isLoading || !dashboardData.pagination.has_previous}
        >
          Previous
        </button>
        <span>
          Page {activePage} of {dashboardData.pagination.total_pages}
        </span>
        <button
          type="button"
          onClick={() => handlePageChange(activePage + 1)}
          disabled={isLoading || !dashboardData.pagination.has_next}
        >
          Next
        </button>
      </div>

      <p>{totalResults} consultant(s) found.</p>
    </div>
  );
}
