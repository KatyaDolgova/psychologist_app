// Название и знак Meetor: Meet + Mentor. Цветом выделено «or», чтобы читалось «Meet».
export const BRAND_NAME = 'Meetor';
export const BRAND_TAGLINE = 'Специалист для каждого';
export const BRAND_ORIGIN = 'Meet + Mentor';

// Два сцепленных кольца в скруглённом квадрате: встреча ученика и наставника.
// Квадрат, а не круг, чтобы знак не путали с аватаркой пользователя.
export function BrandMark({ className = 'w-9 h-9' }: { className?: string }) {
	return (
		<svg
			viewBox='0 0 64 64'
			aria-hidden='true'
			className={`${className} flex-shrink-0`}
		>
			<rect width='64' height='64' rx='16' className='fill-blue-600 dark:fill-blue-500' />
			<circle cx='25' cy='32' r='12' fill='none' stroke='white' strokeWidth='5' />
			<circle cx='39' cy='32' r='12' fill='none' stroke='white' strokeWidth='5' />
		</svg>
	);
}

export function BrandName({ className = '' }: { className?: string }) {
	return (
		<span title={BRAND_ORIGIN} className={className}>
			Meet<span className='text-blue-600 dark:text-blue-400'>or</span>
		</span>
	);
}
