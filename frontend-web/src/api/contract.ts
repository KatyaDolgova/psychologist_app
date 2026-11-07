// Значения, общие с бэкендом. Пока T-10 не влита, бэкенд использует старые имена.
// При T-10 меняется только этот файл (и старый адрес в vite.config.ts).
export const SPECIALIST_ROLE = 'PSYCHOLOGIST' as const;
export const SPECIALIST_USER_TYPE = 'psychologist';
export const SPECIALISTS_API = '/psychologists';
export const USER_SPECIALISTS_API = '/user/psychologists';
