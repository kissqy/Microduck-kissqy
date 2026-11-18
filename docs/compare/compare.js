'use strict';
const filterButtons = Array.from(document.querySelectorAll('[data-filter]'));
const projectRows = Array.from(document.querySelectorAll('[data-project]'));
const filterStatus = document.querySelector('[data-filter-status]');
for (const button of filterButtons) {
  button.addEventListener('click', () => {
    const route = button.dataset.filter;
    for (const candidate of filterButtons) candidate.setAttribute('aria-pressed', String(candidate === button));
    let visible = 0;
    for (const row of projectRows) {
      row.hidden = route !== 'all' && row.dataset.route !== route;
      if (!row.hidden) visible += 1;
    }
    if (filterStatus) filterStatus.textContent = filterStatus.dataset.prefix + visible + filterStatus.dataset.suffix;
  });
}
