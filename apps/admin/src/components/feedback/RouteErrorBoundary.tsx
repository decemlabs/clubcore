import { isRouteErrorResponse, useRouteError } from 'react-router-dom';
import { ErrorPage, type ErrorCode } from './ErrorPage';

/**
 * errorElement роутера: ловит выброшенные при рендере/загрузке ошибки и показывает
 * соответствующую ErrorPage. Известные HTTP-статусы (403/404) маппятся напрямую,
 * всё остальное — 500. Скелет фазы 0; расширяется в фазе 5.
 */
export function RouteErrorBoundary() {
  const error = useRouteError();
  let code: ErrorCode = 500;
  if (
    isRouteErrorResponse(error) &&
    (error.status === 403 || error.status === 404 || error.status === 503)
  ) {
    code = error.status;
  }
  return <ErrorPage code={code} />;
}
