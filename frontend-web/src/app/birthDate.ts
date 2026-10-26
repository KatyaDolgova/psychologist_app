// Проверка даты рождения. Те же правила стоят на бэкенде (schemas/user.py).
const MAX_AGE_YEARS = 120;

const pad = (n: number) => String(n).padStart(2, '0');

const toInputValue = (d: Date) =>
	`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

// Границы для <input type="date" min max>: календарь не даст выбрать дату вне них.
export const birthDateMax = () => toInputValue(new Date());
export const birthDateMin = () =>
	`${new Date().getFullYear() - MAX_AGE_YEARS}-01-01`;

// Возвращает текст ошибки или null, если дата корректна.
export const validateBirthDate = (value: string): string | null => {
	const [y, m, d] = value.split('-').map(Number);
	const date = new Date(y, m - 1, d);
	if (
		!y ||
		Number.isNaN(date.getTime()) ||
		date.getFullYear() !== y ||
		date.getMonth() !== m - 1 ||
		date.getDate() !== d
	) {
		return 'Некорректная дата рождения';
	}
	const today = new Date();
	today.setHours(0, 0, 0, 0);
	if (date > today) return 'Дата рождения не может быть в будущем';
	if (y < today.getFullYear() - MAX_AGE_YEARS) {
		return `Дата рождения не может быть раньше ${MAX_AGE_YEARS} лет назад`;
	}
	return null;
};
