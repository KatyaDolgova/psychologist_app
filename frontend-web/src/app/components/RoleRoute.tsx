import { SPECIALIST_ROLE } from '../../api/contract';
import { Navigate, Outlet } from 'react-router';

function decodeToken(token: string): { type: 'CLIENT' | typeof SPECIALIST_ROLE } | null {
	try {
		const base64 = token
			.split('.')[1]
			.replace(/-/g, '+')
			.replace(/_/g, '/');
		return JSON.parse(atob(base64));
	} catch {
		return null;
	}
}

export function SpecialistRoute() {
	const token = localStorage.getItem('token');
	if (!token) return <Navigate to='/auth' replace />;
	const decoded = decodeToken(token);
	if (decoded?.type !== SPECIALIST_ROLE) return <Navigate to='/specialists' replace />;
	return <Outlet />;
}

export function ClientRoute() {
	const token = localStorage.getItem('token');
	if (!token) return <Navigate to='/auth' replace />;
	const decoded = decodeToken(token);
	if (decoded?.type === SPECIALIST_ROLE) return <Navigate to='/' replace />;
	return <Outlet />;
}
