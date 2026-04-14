let _xlsxPromise = null;

export function loadXlsxModule() {
  if (!_xlsxPromise) {
    _xlsxPromise = import('xlsx').then((m) => m.default || m);
  }
  return _xlsxPromise;
}

/**
 * Export one or more sheets to an .xlsx file.
 *
 * @param {string} filename - Output filename (e.g. "report.xlsx")
 * @param {Array<{name: string, rows: Array<object>}>} sheets
 *   Each sheet has a `name` and `rows` (array of flat objects — keys become headers).
 *   Alternatively, provide `aoa` (array-of-arrays) instead of `rows`.
 */
export async function exportToXlsx(filename, sheets) {
  const XLSX = await loadXlsxModule();
  const wb = XLSX.utils.book_new();
  for (const sheet of sheets) {
    const ws = sheet.aoa
      ? XLSX.utils.aoa_to_sheet(sheet.aoa)
      : XLSX.utils.json_to_sheet(sheet.rows || []);
    XLSX.utils.book_append_sheet(wb, ws, sheet.name.slice(0, 31));
  }
  XLSX.writeFile(wb, filename);
}
