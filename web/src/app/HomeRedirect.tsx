import { Navigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';
import { firstAllowedPath } from '../lib/permissions';

export function HomeRedirect() {
  const { status, can, hasFeature } = useAuth();
  if (status === 'anonymous') return <Navigate to="/login" replace />;
  if (status === 'choosingCompany') return <Navigate to="/empresa" replace />;
  if (status !== 'ready') return null;
  return <Navigate to={firstAllowedPath(can, hasFeature)} replace />;
}
