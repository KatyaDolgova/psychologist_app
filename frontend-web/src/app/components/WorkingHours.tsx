import { useEffect, useState } from 'react';
import {
	Clock,
	CheckCircle2,
	XCircle,
	Loader2,
	Save,
	Zap,
	Trash2,
	Plus,
	CalendarDays,
} from 'lucide-react';
import {
	Card,
	CardContent,
	CardHeader,
	CardTitle,
	CardDescription,
} from './ui/card';
import { Switch } from './ui/switch';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
	getWorkingHours,
	updateWorkingHours,
	getMySlots,
	generateSlots,
	createManualSlot,
	deleteSlot,
	cancelSlot,
	getPsyshologistProfile,
	updatePsyshologistProfile,
} from '../../api/psychologist';

const DAY_ORDER = [
	'MONDAY',
	'TUESDAY',
	'WEDNESDAY',
	'THURSDAY',
	'FRIDAY',
	'SATURDAY',
	'SUNDAY',
] as const;

const DAY_NAMES: Record<string, string> = {
	MONDAY: 'Понедельник',
	TUESDAY: 'Вторник',
	WEDNESDAY: 'Среда',
	THURSDAY: 'Четверг',
	FRIDAY: 'Пятница',
	SATURDAY: 'Суббота',
	SUNDAY: 'Воскресенье',
};

const DAY_SHORT: Record<string, string> = {
	MONDAY: 'ПН',
	TUESDAY: 'ВТ',
	WEDNESDAY: 'СР',
	THURSDAY: 'ЧТ',
	FRIDAY: 'ПТ',
	SATURDAY: 'СБ',
	SUNDAY: 'ВС',
};

const toInput = (t: string | null) => (t ? t.slice(0, 5) : '');

const toApi = (t: string) => (t ? `${t}:00` : null);

const calcHours = (start: string | null, end: string | null): number => {
	if (!start || !end) return 0;
	const [sh, sm] = start.split(':').map(Number);
	const [eh, em] = end.split(':').map(Number);
	const diff = (eh * 60 + em - sh * 60 - sm) / 60;
	return diff > 0 ? diff : 0;
};

// 7.666… → «7,7»; целые часы выводятся без дробной части.
const formatHours = (hours: number) =>
	hours.toLocaleString('ru-RU', { maximumFractionDigits: 1 });

const DURATION_OPTIONS = [30, 45, 50, 60, 90, 120];
const DEFAULT_DURATION = 60;
const DEFAULT_BREAK = { start: '13:00:00', end: '14:00:00' };

const toMinutes = (t: string) => {
	const [h, m] = t.split(':').map(Number);
	return h * 60 + m;
};

interface Slot {
	id: string;
	starts_at: string;
	ends_at: string;
	status: 'FREE' | 'BOOKED' | 'CANCELLED';
	source: 'TEMPLATE' | 'MANUAL';
}

// Диапазон шаблона в том виде, в каком его хранит бэкенд.
interface TemplateRange {
	day_of_week: string;
	start_time: string;
	end_time: string;
	is_active: boolean;
}

// День в интерфейсе: рабочее время и необязательный перерыв.
// На бэкенд день с перерывом уходит двумя диапазонами: до и после перерыва.
interface DaySchedule {
	day_of_week: string;
	start_time: string | null;
	end_time: string | null;
	is_active: boolean;
	has_break: boolean;
	break_start: string | null;
	break_end: string | null;
}

const emptyDay = (day: string): DaySchedule => ({
	day_of_week: day,
	start_time: null,
	end_time: null,
	is_active: false,
	has_break: false,
	break_start: null,
	break_end: null,
});

// Диапазоны с бэкенда → дни интерфейса. Два диапазона в один день = день с перерывом.
const fromRanges = (ranges: TemplateRange[]): DaySchedule[] =>
	DAY_ORDER.map((day) => {
		const own = ranges
			.filter((r) => r.day_of_week === day)
			.sort((a, b) => a.start_time.localeCompare(b.start_time));
		if (own.length === 0) return emptyDay(day);
		const hasBreak = own.length > 1;
		return {
			day_of_week: day,
			start_time: own[0].start_time,
			end_time: own[own.length - 1].end_time,
			is_active: own.some((r) => r.is_active),
			has_break: hasBreak,
			break_start: hasBreak ? own[0].end_time : null,
			break_end: hasBreak ? own[1].start_time : null,
		};
	});

const isBreakInside = (d: DaySchedule) => {
	if (!d.has_break || !d.start_time || !d.end_time) return false;
	if (!d.break_start || !d.break_end) return false;
	const start = toMinutes(d.start_time);
	const breakStart = toMinutes(d.break_start);
	const breakEnd = toMinutes(d.break_end);
	return (
		start < breakStart &&
		breakStart < breakEnd &&
		breakEnd < toMinutes(d.end_time)
	);
};

// Рабочие отрезки дня: один без перерыва, два с перерывом.
const dayIntervals = (d: DaySchedule): [string, string][] => {
	if (!d.start_time || !d.end_time) return [];
	if (isBreakInside(d)) {
		return [
			[d.start_time, d.break_start!],
			[d.break_end!, d.end_time],
		];
	}
	return [[d.start_time, d.end_time]];
};

// Дни интерфейса → диапазоны для бэкенда.
const toRanges = (schedule: DaySchedule[]) =>
	schedule.flatMap((d) =>
		dayIntervals(d).map(([start, end]) => ({
			day_of_week: d.day_of_week,
			start_time: toApi(toInput(start)),
			end_time: toApi(toInput(end)),
			is_active: d.is_active,
		})),
	);

const dayHours = (d: DaySchedule) =>
	dayIntervals(d).reduce((sum, [start, end]) => sum + calcHours(start, end), 0);

// Сколько слотов даст день: каждый отрезок режется встык, остаток отбрасывается
// (так же считает генерация на бэкенде).
const daySlots = (d: DaySchedule, duration: number) =>
	dayIntervals(d).reduce(
		(sum, [start, end]) => {
			const minutes = toMinutes(end) - toMinutes(start);
			return sum + Math.max(0, Math.floor(minutes / duration));
		},
		0,
	);

const validateDay = (d: DaySchedule): string | null => {
	if (!d.is_active) return null;
	if (!d.start_time || !d.end_time) return 'укажите начало и окончание работы';
	if (toMinutes(d.end_time) <= toMinutes(d.start_time)) {
		return 'окончание работы должно быть позже начала';
	}
	if (d.has_break) {
		if (!d.break_start || !d.break_end) return 'укажите начало и конец перерыва';
		if (!isBreakInside(d)) return 'перерыв должен быть внутри рабочего времени';
	}
	return null;
};

export default function WorkingHours() {
	const token = localStorage.getItem('token') ?? '';
	const [schedule, setSchedule] = useState<DaySchedule[]>([]);
	const [original, setOriginal] = useState<DaySchedule[]>([]);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState('');
	const [saveError, setSaveError] = useState('');
	const [saved, setSaved] = useState(false);
	const [duration, setDuration] = useState(DEFAULT_DURATION);
	const [originalDuration, setOriginalDuration] = useState(DEFAULT_DURATION);

	const [slots, setSlots] = useState<Slot[]>([]);
	const [slotsLoading, setSlotsLoading] = useState(false);
	const [slotFromDate, setSlotFromDate] = useState(() =>
		new Date().toISOString().slice(0, 10),
	);
	const [slotToDate, setSlotToDate] = useState(() => {
		const d = new Date();
		d.setDate(d.getDate() + 30);
		return d.toISOString().slice(0, 10);
	});
	const [generating, setGenerating] = useState(false);
	const [generateMsg, setGenerateMsg] = useState('');
	const [manualDate, setManualDate] = useState('');
	const [manualTime, setManualTime] = useState('');
	const [addingManual, setAddingManual] = useState(false);
	const [slotError, setSlotError] = useState('');

	const fetchSlots = async () => {
		setSlotsLoading(true);
		setSlotError('');
		try {
			const from = new Date(slotFromDate + 'T00:00:00').toISOString();
			const to = new Date(slotToDate + 'T23:59:59').toISOString();
			const data: Slot[] = await getMySlots(token, from, to);
			setSlots(
				data.sort(
					(a, b) =>
						new Date(a.starts_at).getTime() -
						new Date(b.starts_at).getTime(),
				),
			);
		} catch (e: any) {
			setSlotError(e.message || 'Ошибка загрузки слотов');
		} finally {
			setSlotsLoading(false);
		}
	};

	const handleGenerate = async () => {
		setGenerating(true);
		setGenerateMsg('');
		setSlotError('');
		try {
			const res = await generateSlots(token, slotFromDate, slotToDate);
			setGenerateMsg(
				`Создано: ${res.created}, пропущено: ${res.skipped}`,
			);
			await fetchSlots();
		} catch (e: any) {
			setSlotError(e.message || 'Ошибка генерации');
		} finally {
			setGenerating(false);
		}
	};

	const handleAddManual = async () => {
		if (!manualDate || !manualTime) return;
		setAddingManual(true);
		setSlotError('');
		try {
			const d = new Date(`${manualDate}T${manualTime}:00`);
			await createManualSlot(token, d.toISOString());
			setManualDate('');
			setManualTime('');
			await fetchSlots();
		} catch (e: any) {
			setSlotError(e.message || 'Ошибка создания слота');
		} finally {
			setAddingManual(false);
		}
	};

	const handleDeleteSlot = async (slotId: string) => {
		try {
			await deleteSlot(token, slotId);
			setSlots((prev) => prev.filter((s) => s.id !== slotId));
		} catch (e: any) {
			setSlotError(e.message || 'Ошибка удаления');
		}
	};

	const handleCancelSlot = async (slotId: string) => {
		try {
			await cancelSlot(token, slotId);
			setSlots((prev) =>
				prev.map((s) =>
					s.id === slotId ? { ...s, status: 'CANCELLED' } : s,
				),
			);
		} catch (e: any) {
			setSlotError(e.message || 'Ошибка отмены');
		}
	};

	const fetchSchedule = async () => {
		setLoading(true);
		setError('');
		try {
			const [data, profile] = await Promise.all([
				getWorkingHours(token),
				getPsyshologistProfile(token),
			]);
			const days = fromRanges(data as TemplateRange[]);
			setSchedule(days);
			setOriginal(days);
			const minutes = profile?.session_duration_minutes ?? DEFAULT_DURATION;
			setDuration(minutes);
			setOriginalDuration(minutes);
		} catch (e: any) {
			setError(e.message || 'Ошибка при загрузке расписания');
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		fetchSchedule();
		fetchSlots();
	}, []);

	const updateDay = (index: number, patch: Partial<DaySchedule>) => {
		setSaved(false);
		setSaveError('');
		setSchedule((prev) =>
			prev.map((d, i) => (i === index ? { ...d, ...patch } : d)),
		);
	};

	const handleSave = async () => {
		setSaveError('');
		setSaved(false);

		for (const d of schedule) {
			const dayError = validateDay(d);
			if (dayError) {
				setSaveError(`${DAY_NAMES[d.day_of_week]}: ${dayError}`);
				return;
			}
		}

		setSaving(true);
		try {
			const resp = await updateWorkingHours(token, toRanges(schedule));
			const updatedList: TemplateRange[] = Array.isArray(resp)
				? resp
				: (resp.ranges ?? []);
			const days = fromRanges(updatedList);
			setSchedule(days);
			setOriginal(days);
			if (duration !== originalDuration) {
				await updatePsyshologistProfile(token, {
					session_duration_minutes: duration,
				});
				setOriginalDuration(duration);
			}
			setSaved(true);
		} catch (e: any) {
			setSaveError(e.message || 'Ошибка при сохранении');
		} finally {
			setSaving(false);
		}
	};

	const handleCancel = () => {
		setSchedule(original);
		setDuration(originalDuration);
		setSaveError('');
		setSaved(false);
	};

	const toggleBreak = (index: number, enabled: boolean) => {
		const day = schedule[index];
		// По умолчанию предлагаем 13:00–14:00, если это внутри рабочего дня.
		const defaultBreak = {
			break_start: DEFAULT_BREAK.start,
			break_end: DEFAULT_BREAK.end,
		};
		const useDefault =
			enabled &&
			!day.break_start &&
			isBreakInside({ ...day, has_break: true, ...defaultBreak });
		updateDay(index, {
			has_break: enabled,
			...(useDefault ? defaultBreak : {}),
		});
	};

	const changeDuration = (minutes: number) => {
		setSaved(false);
		setSaveError('');
		setDuration(minutes);
	};

	const durationOptions = DURATION_OPTIONS.includes(duration)
		? DURATION_OPTIONS
		: [...DURATION_OPTIONS, duration].sort((a, b) => a - b);

	const activeDays = schedule.filter((d) => d.is_active).length;
	const totalHours = schedule
		.filter((d) => d.is_active)
		.reduce((sum, d) => sum + dayHours(d), 0);

	if (loading) {
		return (
			<div className='flex items-center justify-center min-h-screen'>
				<Loader2 className='w-8 h-8 animate-spin text-blue-500' />
			</div>
		);
	}

	if (error) {
		return (
			<div className='p-8 text-center'>
				<p className='text-red-500 mb-4'>{error}</p>
				<Button variant='outline' onClick={fetchSchedule}>
					Повторить
				</Button>
			</div>
		);
	}

	return (
		<div className='p-8 bg-gray-50 dark:bg-gray-900 min-h-screen'>
			<div className='mb-8'>
				<h1 className='text-3xl font-bold text-gray-900 dark:text-white'>
					Рабочее расписание
				</h1>
				<p className='text-gray-500 dark:text-gray-400 mt-1'>
					Настройте дни и часы работы
				</p>
			</div>

			<div className='grid grid-cols-2 gap-4 mb-8'>
				<Card className='dark:bg-gray-800 dark:border-gray-700'>
					<CardContent className='p-5 flex items-center gap-4'>
						<div className='w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center'>
							<CheckCircle2 className='w-5 h-5 text-blue-600 dark:text-blue-400' />
						</div>
						<div>
							<p className='text-sm text-gray-500 dark:text-gray-400'>
								Рабочих дней
							</p>
							<p className='text-2xl font-bold text-gray-900 dark:text-white'>
								{activeDays}
							</p>
						</div>
					</CardContent>
				</Card>
				<Card className='dark:bg-gray-800 dark:border-gray-700'>
					<CardContent className='p-5 flex items-center gap-4'>
						<div className='w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/40 flex items-center justify-center'>
							<Clock className='w-5 h-5 text-green-600 dark:text-green-400' />
						</div>
						<div>
							<p className='text-sm text-gray-500 dark:text-gray-400'>
								Часов в неделю
							</p>
							<p className='text-2xl font-bold text-gray-900 dark:text-white'>
								{formatHours(totalHours)}
							</p>
						</div>
					</CardContent>
				</Card>
			</div>

			<Card className='mb-8 dark:bg-gray-800 dark:border-gray-700'>
				<CardHeader>
					<CardTitle className='dark:text-white'>
						Недельный обзор
					</CardTitle>
					<CardDescription className='dark:text-gray-400'>
						Быстрый просмотр рабочих дней
					</CardDescription>
				</CardHeader>
				<CardContent>
					<div className='grid grid-cols-7 gap-2'>
						{schedule.map((day) => (
							<div
								key={day.day_of_week}
								className={`p-3 rounded-lg border-2 text-center transition-all ${
									day.is_active
										? 'bg-blue-50 border-blue-300 dark:bg-gray-700 dark:border-blue-500'
										: 'bg-gray-50 border-gray-200 dark:bg-gray-700/50 dark:border-gray-600'
								}`}
							>
								<div className='font-semibold text-sm text-gray-900 dark:text-white mb-2'>
									{DAY_SHORT[day.day_of_week]}
								</div>
								{day.is_active ? (
									<>
										<CheckCircle2 className='w-5 h-5 text-green-600 mx-auto mb-1' />
										<div className='text-xs text-gray-600 dark:text-gray-300'>
											{toInput(day.start_time) || '—'}
										</div>
										<div className='text-xs text-gray-600 dark:text-gray-300'>
											{toInput(day.end_time) || '—'}
										</div>
										{isBreakInside(day) && (
											<div className='text-xs text-amber-600 dark:text-amber-400 mt-1'>
												обед {toInput(day.break_start)}–
												{toInput(day.break_end)}
											</div>
										)}
										{day.start_time && day.end_time && (
											<div className='text-xs font-medium text-blue-600 dark:text-blue-400 mt-1'>
												{formatHours(dayHours(day))}ч
											</div>
										)}
									</>
								) : (
									<>
										<XCircle className='w-5 h-5 text-gray-400 mx-auto mb-1' />
										<div className='text-xs text-gray-400'>
											Выходной
										</div>
									</>
								)}
							</div>
						))}
					</div>
				</CardContent>
			</Card>

			<Card className='dark:bg-gray-800 dark:border-gray-700'>
				<CardHeader>
					<CardTitle className='dark:text-white'>
						Детальное расписание
					</CardTitle>
					<CardDescription className='dark:text-gray-400'>
						Настройте время работы для каждого дня недели
					</CardDescription>
				</CardHeader>
				<CardContent>
					<div className='mb-6 p-4 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/40 flex flex-wrap items-end gap-4'>
						<div className='space-y-1'>
							<Label
								htmlFor='session-duration'
								className='text-sm text-gray-600 dark:text-gray-400'
							>
								Длительность сессии
							</Label>
							<select
								id='session-duration'
								value={duration}
								onChange={(e) => changeDuration(Number(e.target.value))}
								className='h-9 w-40 rounded-md border border-gray-300 bg-white px-3 text-sm dark:bg-gray-800 dark:border-gray-600 dark:text-white'
							>
								{durationOptions.map((m) => (
									<option key={m} value={m}>
										{m} мин
									</option>
								))}
							</select>
						</div>
						<p className='text-sm text-gray-500 dark:text-gray-400 max-w-xl'>
							Рабочее время нарезается на слоты этой длительности.
							Изменение действует для новых слотов: уже созданные
							свободные слоты останутся прежними — удалите их и
							сгенерируйте заново.
						</p>
					</div>
					<div className='space-y-4'>
						{schedule.map((day, index) => (
							<div
								key={day.day_of_week}
								className={`p-5 rounded-lg border transition-all ${
									day.is_active
										? 'border-blue-200 bg-white dark:bg-gray-700 dark:border-blue-800'
										: 'border-gray-200 bg-gray-50 dark:bg-gray-700/40 dark:border-gray-600'
								}`}
							>
								<div className='flex items-center justify-between'>
									<div className='flex items-center gap-3'>
										<h3 className='font-semibold text-gray-900 dark:text-gray-100'>
											{DAY_NAMES[day.day_of_week]}
										</h3>
										{day.is_active && (
											<Badge className='bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'>
												Рабочий день
											</Badge>
										)}
									</div>
									<div className='flex items-center gap-3'>
										<Label
											htmlFor={`switch-${day.day_of_week}`}
											className='text-sm text-gray-600 dark:text-gray-300 cursor-pointer'
										>
											Рабочий день
										</Label>
										<Switch
											id={`switch-${day.day_of_week}`}
											checked={day.is_active}
											onCheckedChange={(v) =>
												updateDay(index, {
													is_active: v,
												})
											}
										/>
									</div>
								</div>

								{day.is_active && (
									<div className='mt-4 flex flex-wrap gap-6'>
										<div className='space-y-1'>
											<Label className='text-sm text-gray-600 dark:text-gray-400'>
												Начало работы
											</Label>
											<div className='flex items-center gap-2'>
												<Clock className='w-4 h-4 text-gray-400' />
												<Input
													type='time'
													value={toInput(
														day.start_time,
													)}
													onChange={(e) =>
														updateDay(index, {
															start_time: e.target
																.value
																? `${e.target.value}:00`
																: null,
														})
													}
													className='w-36 cursor-pointer dark:bg-gray-800 dark:border-gray-600 dark:text-white'
												/>
											</div>
										</div>
										<div className='space-y-1'>
											<Label className='text-sm text-gray-600 dark:text-gray-400'>
												Окончание работы
											</Label>
											<div className='flex items-center gap-2'>
												<Clock className='w-4 h-4 text-gray-400' />
												<Input
													type='time'
													value={toInput(
														day.end_time,
													)}
													onChange={(e) =>
														updateDay(index, {
															end_time: e.target
																.value
																? `${e.target.value}:00`
																: null,
														})
													}
													className='w-36 cursor-pointer dark:bg-gray-800 dark:border-gray-600 dark:text-white'
												/>
											</div>
										</div>
										{day.start_time && day.end_time && (
											<div className='flex items-end'>
												<span className='text-sm text-gray-500 dark:text-gray-400'>
													{formatHours(dayHours(day))} ч
													рабочих · {daySlots(day, duration)}{' '}
													слотов по {duration} мин
												</span>
											</div>
										)}
									</div>
								)}

								{day.is_active && (
									<div className='mt-4 flex flex-wrap items-end gap-6'>
										<div className='flex items-center gap-3 h-9'>
											<Switch
												id={`break-${day.day_of_week}`}
												checked={day.has_break}
												onCheckedChange={(v) =>
													toggleBreak(index, v)
												}
											/>
											<Label
												htmlFor={`break-${day.day_of_week}`}
												className='text-sm text-gray-600 dark:text-gray-300 cursor-pointer'
											>
												Перерыв
											</Label>
										</div>
										{day.has_break && (
											<>
												<div className='space-y-1'>
													<Label className='text-sm text-gray-600 dark:text-gray-400'>
														Начало перерыва
													</Label>
													<Input
														type='time'
														value={toInput(day.break_start)}
														onChange={(e) =>
															updateDay(index, {
																break_start: e.target.value
																	? `${e.target.value}:00`
																	: null,
															})
														}
														className='w-36 cursor-pointer dark:bg-gray-800 dark:border-gray-600 dark:text-white'
													/>
												</div>
												<div className='space-y-1'>
													<Label className='text-sm text-gray-600 dark:text-gray-400'>
														Конец перерыва
													</Label>
													<Input
														type='time'
														value={toInput(day.break_end)}
														onChange={(e) =>
															updateDay(index, {
																break_end: e.target.value
																	? `${e.target.value}:00`
																	: null,
															})
														}
														className='w-36 cursor-pointer dark:bg-gray-800 dark:border-gray-600 dark:text-white'
													/>
												</div>
											</>
										)}
									</div>
								)}
							</div>
						))}
					</div>

					<div className='mt-6 pt-6 border-t dark:border-gray-700 flex items-center justify-between'>
						<div>
							{saveError && (
								<p className='text-sm text-red-500'>
									{saveError}
								</p>
							)}
							{saved && (
								<p className='text-sm text-green-600 dark:text-green-400'>
									Расписание сохранено
								</p>
							)}
						</div>
						<div className='flex gap-3'>
							<Button
								variant='outline'
								onClick={handleCancel}
								disabled={saving}
								className='dark:border-gray-600 dark:text-gray-300'
							>
								Отменить
							</Button>
							<Button
								onClick={handleSave}
								disabled={saving}
								className='bg-blue-600 hover:bg-blue-700 dark:text-white'
							>
								{saving ? (
									<Loader2 className='w-4 h-4 mr-2 animate-spin' />
								) : (
									<Save className='w-4 h-4 mr-2' />
								)}
								Сохранить расписание
							</Button>
						</div>
					</div>
				</CardContent>
			</Card>

			<Card className='mt-8 dark:bg-gray-800 dark:border-gray-700'>
				<CardHeader>
					<CardTitle className='dark:text-white flex items-center gap-2'>
						<CalendarDays className='w-5 h-5' />
						Слоты для записи
					</CardTitle>
					<CardDescription className='dark:text-gray-400'>
						Управление временными слотами для записи клиентов
					</CardDescription>
				</CardHeader>
				<CardContent className='space-y-6'>
					<div className='flex flex-wrap gap-4 items-end p-4 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/40'>
						<div className='space-y-1'>
							<Label className='text-sm dark:text-gray-300'>
								С
							</Label>
							<input
								type='date'
								value={slotFromDate}
								onChange={(e) =>
									setSlotFromDate(e.target.value)
								}
								className='px-3 py-2 border rounded-md text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white cursor-pointer'
							/>
						</div>
						<div className='space-y-1'>
							<Label className='text-sm dark:text-gray-300'>
								По
							</Label>
							<input
								type='date'
								value={slotToDate}
								min={slotFromDate}
								onChange={(e) => setSlotToDate(e.target.value)}
								className='px-3 py-2 border rounded-md text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white cursor-pointer'
							/>
						</div>
						<Button
							onClick={() => fetchSlots()}
							variant='outline'
							className='dark:border-gray-600 dark:text-gray-300'
						>
							Показать
						</Button>
						<Button
							onClick={handleGenerate}
							disabled={generating}
							className='bg-blue-600 hover:bg-blue-700 dark:text-white'
						>
							{generating ? (
								<Loader2 className='w-4 h-4 mr-2 animate-spin' />
							) : (
								<Zap className='w-4 h-4 mr-2' />
							)}
							Сгенерировать из шаблона
						</Button>
						{generateMsg && (
							<span className='text-sm text-green-600 dark:text-green-400'>
								{generateMsg}
							</span>
						)}
					</div>

					<div className='flex flex-wrap gap-4 items-end p-4 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/40'>
						<div className='space-y-1'>
							<Label className='text-sm dark:text-gray-300'>
								Дата
							</Label>
							<input
								type='date'
								value={manualDate}
								min={new Date().toISOString().slice(0, 10)}
								onChange={(e) => setManualDate(e.target.value)}
								className='px-3 py-2 border rounded-md text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white cursor-pointer'
							/>
						</div>
						<div className='space-y-1'>
							<Label className='text-sm dark:text-gray-300'>
								Время
							</Label>
							<input
								type='time'
								value={manualTime}
								onChange={(e) => setManualTime(e.target.value)}
								className='px-3 py-2 border rounded-md text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white cursor-pointer'
							/>
						</div>
						<Button
							onClick={handleAddManual}
							disabled={
								addingManual || !manualDate || !manualTime
							}
							className='bg-purple-600 hover:bg-purple-700 dark:text-white'
						>
							{addingManual ? (
								<Loader2 className='w-4 h-4 mr-2 animate-spin' />
							) : (
								<Plus className='w-4 h-4 mr-2' />
							)}
							Добавить вручную
						</Button>
					</div>

					{slotError && (
						<p className='text-sm text-red-500'>{slotError}</p>
					)}

					{slotsLoading ? (
						<div className='flex justify-center py-8'>
							<Loader2 className='w-6 h-6 animate-spin text-blue-500' />
						</div>
					) : slots.length === 0 ? (
						<p className='text-sm text-center text-gray-500 dark:text-gray-400 py-8'>
							Нет слотов в выбранном периоде
						</p>
					) : (
						<div className='space-y-2'>
							{slots.map((slot) => {
								const start = new Date(slot.starts_at);
								const end = new Date(slot.ends_at);
								const statusColor =
									slot.status === 'FREE'
										? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
										: slot.status === 'BOOKED'
											? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
											: 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400';
								const statusLabel =
									slot.status === 'FREE'
										? 'Свободен'
										: slot.status === 'BOOKED'
											? 'Занят'
											: 'Отменён';
								return (
									<div
										key={slot.id}
										className='flex items-center justify-between p-3 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700'
									>
										<div className='flex items-center gap-3'>
											<div>
												<p className='text-sm font-medium text-gray-900 dark:text-white'>
													{start.toLocaleDateString(
														'ru-RU',
														{
															day: 'numeric',
															month: 'long',
															weekday: 'short',
														},
													)}
												</p>
												<p className='text-xs text-gray-500 dark:text-gray-400'>
													{start.toLocaleTimeString(
														'ru-RU',
														{
															hour: '2-digit',
															minute: '2-digit',
														},
													)}
													{' — '}
													{end.toLocaleTimeString(
														'ru-RU',
														{
															hour: '2-digit',
															minute: '2-digit',
														},
													)}
													{slot.source ===
														'MANUAL' && (
														<span className='ml-2 text-purple-500'>
															вручную
														</span>
													)}
												</p>
											</div>
										</div>
										<div className='flex items-center gap-2'>
											<Badge className={statusColor}>
												{statusLabel}
											</Badge>
											{slot.status === 'FREE' && (
												<button
													onClick={() =>
														handleDeleteSlot(
															slot.id,
														)
													}
													className='cursor-pointer p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-red-500 transition-colors'
													title='Удалить'
												>
													<Trash2 className='w-4 h-4' />
												</button>
											)}
											{slot.status === 'BOOKED' && (
												<button
													onClick={() =>
														handleCancelSlot(
															slot.id,
														)
													}
													className='cursor-pointer px-2 py-1 rounded text-xs bg-red-100 text-red-600 hover:bg-red-200 dark:bg-red-900/20 dark:text-red-400 transition-colors'
												>
													Отменить
												</button>
											)}
										</div>
									</div>
								);
							})}
						</div>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
