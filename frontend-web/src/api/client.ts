const FALLBACK_ERROR = 'Не удалось выполнить запрос. Попробуйте ещё раз';

// Достаёт понятный текст ошибки из ответа бэкенда. Бэкенд отвечает в трёх форматах:
//   {"detail": "Слот более недоступен"}                      — доменные ошибки
//   {"detail": {"detail": "...", "message": "..."}}           — ошибки авторизации и БД
//   {"detail": [{"msg": "Value error, Дата рождения ..."}]}   — 422 от Pydantic
export function getErrorMessage(body: any, fallback = FALLBACK_ERROR): string {
	const detail = body?.detail ?? body;
	if (typeof detail === 'string' && detail) return detail;
	if (Array.isArray(detail) && detail.length > 0) {
		const msg = detail[0]?.msg;
		if (typeof msg === 'string' && msg) return msg.replace(/^Value error, /, '');
	}
	if (detail && typeof detail === 'object') {
		const msg = detail.message ?? detail.detail;
		if (typeof msg === 'string' && msg) return msg;
	}
	if (typeof body?.message === 'string' && body.message) return body.message;
	return fallback;
}

export async function apiFetch(
	url: string,
	options: RequestInit = {},
): Promise<Response> {
	const res = await fetch(url, options);
	if (res.status === 401) {
		localStorage.removeItem('token');
		window.location.replace('/auth');
		throw new Error('Unauthorized');
	}
	return res;
}
