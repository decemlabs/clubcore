/**
 * Shared CSV blob-download helper (Phase 104-01 RPT-02/RPT-03).
 *
 * GET /api/v1/…csv endpoints are CSRF-exempt (GET is safe per RFC-7231).
 * Auth is handled by the HttpOnly cc_access cookie (credentials:'include').
 * Russian-toast error handling lives in the CALLER (Wave 2 pages) — this
 * helper only throws an Error with the server's message.
 */
import { appendQuery, parseErrorBody } from '@/api/client';

/**
 * Fetch a CSV endpoint with cookie credentials and trigger a browser download.
 *
 * @param endpoint - Absolute path, e.g. `/api/v1/reports/revenue.csv`
 * @param filename  - The suggested filename for the browser save dialog.
 * @param query     - Optional query params appended to the URL.
 *
 * @throws Error with a human-readable message on non-2xx responses.
 */
export async function downloadCsv(
  endpoint: string,
  filename: string,
  query?: Record<string, string | number | boolean>,
): Promise<void> {
  const url = appendQuery(endpoint, query);
  const res = await fetch(url, { credentials: 'include' });
  if (!res.ok) {
    const body = await parseErrorBody(res);
    throw new Error(body.message || 'Download failed');
  }
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = href;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(href);
}
