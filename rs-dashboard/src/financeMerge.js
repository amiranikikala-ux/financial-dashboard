/** იგივე ლოგიკა, რაც მომწოდებლების ცხრილში — სიზუსტისთვის ერთი წყარო */
export const STORAGE_KEY = 'rs_dashboard_local_payments';

export function extractTaxId(org) {
  const m = String(org || '').match(/\((\d+)/);
  return m ? m[1] : null;
}

export function mergeSupplier(sup, localPayments, livePending = 0) {
  const tid = extractTaxId(sup['ორგანიზაცია']);
  const browserExtra = tid ? Number(localPayments[tid]) || 0 : 0;
  const extra = browserExtra + livePending;
  const te = Number(sup.total_effective) || 0;
  const tp0 = Number(sup.total_paid) || 0;
  const paid = tp0 + extra;
  const debtFile = Number(sup.total_debt) || 0;
  const debt = debtFile - extra;
  const bank = Number(sup.bank_paid) || 0;
  const manual = Number(sup.manual_paid) || 0;
  /** CSV (manual_payments) + ბრაუზერში ჩაწერილი — სვეტი „ნაღდით გადახდა“ */
  const manualTotal = manual + extra;
  return {
    id: tid || String(sup['ორგანიზაცია']).slice(0, 40),
    org: sup['ორგანიზაცია'],
    waybills: Number(sup.waybills_count) || 0,
    effective: te,
    paid,
    paidBase: tp0,
    debt,
    debtFile,
    bank,
    manual,
    manualTotal,
    extra,
    browserExtra,
  };
}

export function shortLabel(org, maxLen = 26) {
  const s = String(org || '');
  const rest = s.replace(/^\([^)]+\)\s*/, '').trim() || s;
  return rest.length > maxLen ? `${rest.slice(0, maxLen - 1)}…` : rest;
}
