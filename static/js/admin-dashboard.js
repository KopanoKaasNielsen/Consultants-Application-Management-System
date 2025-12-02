(function () {
  'use strict';

  var table = document.querySelector('[data-dashboard-table]');
  var filterSelect = document.querySelector('[data-status-filter]');

  function filterRows(status) {
    if (!table) return;
    var rows = table.querySelectorAll('tbody tr');
    rows.forEach(function (row) {
      var rowStatus = row.getAttribute('data-status');
      if (!status || status === 'all' || rowStatus === status) {
        row.style.display = '';
      } else {
        row.style.display = 'none';
      }
    });
  }

  if (filterSelect && table) {
    filterSelect.addEventListener('change', function (event) {
      filterRows(event.target.value);
    });
    filterRows(filterSelect.value);
  }
})();
