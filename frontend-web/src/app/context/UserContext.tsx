import { SPECIALIST_ROLE } from '../../api/contract';
import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useState,
	type ReactNode,
} from 'react';
import { getUser } from '../../api/profile';
import { getSpecialistProfile } from '../../api/specialist';

export type UserRole = 'CLIENT' | typeof SPECIALIST_ROLE;

export interface UserProfile {
	role: UserRole;
	displayName: string;
	initials: string;
	avatar: string | null;
	data: any;
}

interface UserContextValue {
	profile: UserProfile | null;
	loading: boolean;
	refreshProfile: () => Promise<void>;
}

const UserContext = createContext<UserContextValue>({
	profile: null,
	loading: true,
	refreshProfile: async () => {},
});

function decodeToken(token: string): { sub: string; type: UserRole } | null {
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

function fixAvatarUrl(url: string | null): string | null {
	if (!url) return null;
	return url.replace('http://0.0.0.0:', 'http://localhost:');
}

function buildProfile(role: UserRole, data: any): UserProfile {
	const avatar = fixAvatarUrl(data.avatar ?? null);
	if (role === SPECIALIST_ROLE) {
		const first = data.first_name || '';
		const last = data.last_name || '';
		const displayName = last ? `Др. ${last}` : first || 'Специалист';
		const initials =
			[first[0], last[0]].filter(Boolean).join('').toUpperCase() || 'П';
		return { role, displayName, initials, avatar, data };
	} else {
		const name: string = data.name || '';
		const displayName = name || 'Пользователь';
		const initials =
			name
				.split(' ')
				.map((n: string) => n[0])
				.join('')
				.slice(0, 2)
				.toUpperCase() || 'П';
		return { role, displayName, initials, avatar, data };
	}
}

export function UserProvider({ children }: { children: ReactNode }) {
	const [profile, setProfile] = useState<UserProfile | null>(null);
	const [loading, setLoading] = useState(true);

	const fetchProfile = useCallback(async () => {
		const token = localStorage.getItem('token');
		if (!token) {
			setLoading(false);
			return;
		}
		const decoded = decodeToken(token);
		if (!decoded) {
			setLoading(false);
			return;
		}
		try {
			if (decoded.type === SPECIALIST_ROLE) {
				const data = await getSpecialistProfile(token);
				setProfile(buildProfile(SPECIALIST_ROLE, data));
			} else {
				const data = await getUser(token);
				setProfile(buildProfile('CLIENT', data));
			}
		} catch {
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchProfile();
	}, [fetchProfile]);

	return (
		<UserContext.Provider
			value={{ profile, loading, refreshProfile: fetchProfile }}
		>
			{children}
		</UserContext.Provider>
	);
}

export const useUser = () => useContext(UserContext);
