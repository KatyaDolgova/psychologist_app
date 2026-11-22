import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import {
	ArrowLeft,
	Check,
	CheckCircle2,
	ChevronDown,
	ChevronUp,
	Clock,
	Copy,
	FileAudio,
	Loader2,
	RotateCcw,
	Search,
	TriangleAlert,
	Upload,
	X,
	XCircle,
} from 'lucide-react';
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from './ui/card';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Progress } from './ui/progress';
import {
	FILE_TOO_LARGE_MESSAGE,
	LESSON_EXTENSIONS,
	MAX_LESSON_UPLOAD_MB,
	UNSUPPORTED_FORMAT_MESSAGE,
	getLesson,
	getLessonModels,
	getTranscript,
	listLessons,
	retryLesson,
	uploadLesson,
	type Lesson,
	type ModelOption,
	type Transcript,
	type TranscriptStatus,
	type TranscriptionModel,
} from '../../api/lessons';

const POLL_INTERVAL_MS = 5000;
const LIST_PAGE_SIZE = 20;
const FINAL_STATUSES: TranscriptStatus[] = ['DONE', 'FAILED'];

const STATUS_VIEW: Record<
	TranscriptStatus,
	{ label: string; hint: string; icon: typeof Clock; className: string }
> = {
	PENDING: {
		label: 'В очереди',
		hint: 'Сервер распознаёт записи по одной, ваша начнётся, когда освободится место.',
		icon: Clock,
		className: 'text-amber-600 dark:text-amber-400',
	},
	PROCESSING: {
		label: 'Идёт распознавание',
		hint: 'Час записи обрабатывается примерно 30-40 минут. Страницу можно закрыть и вернуться позже по этой же ссылке.',
		icon: Loader2,
		className: 'text-blue-600 dark:text-blue-400',
	},
	DONE: {
		label: 'Готово',
		hint: 'Запись распознана.',
		icon: CheckCircle2,
		className: 'text-green-600 dark:text-green-400',
	},
	FAILED: {
		label: 'Не удалось распознать',
		hint: 'Запись можно отправить на распознавание ещё раз.',
		icon: XCircle,
		className: 'text-red-600 dark:text-red-400',
	},
};

const QUALITY_FIRST_RUN_HINT =
	'При самом первом запуске варианта «Точнее» сервер скачивает модель (около 1,6 ГБ), это добавит несколько минут.';

function extensionOf(name: string): string {
	const dot = name.lastIndexOf('.');
	return dot === -1 ? '' : name.slice(dot).toLowerCase();
}

function validateFile(file: File): string {
	if (!LESSON_EXTENSIONS.includes(extensionOf(file.name)))
		return UNSUPPORTED_FORMAT_MESSAGE;
	if (file.size > MAX_LESSON_UPLOAD_MB * 1024 * 1024) return FILE_TOO_LARGE_MESSAGE;
	if (file.size === 0) return 'Файл пустой';
	return '';
}

function formatSize(bytes: number): string {
	return bytes >= 1024 * 1024
		? `${(bytes / 1024 / 1024).toFixed(1)} МБ`
		: `${Math.max(1, Math.round(bytes / 1024))} КБ`;
}

// 75.4 -> "1:15", 3725 -> "1:02:05"
function formatTimecode(seconds: number): string {
	const total = Math.floor(seconds);
	const h = Math.floor(total / 3600);
	const m = Math.floor((total % 3600) / 60);
	const s = String(total % 60).padStart(2, '0');
	return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

const formatDate = (iso: string) =>
	new Date(iso).toLocaleString('ru-RU', {
		day: 'numeric',
		month: 'long',
		hour: '2-digit',
		minute: '2-digit',
	});

function StatusLabel({ status }: { status: TranscriptStatus | null }) {
	if (!status) return <span className='text-sm text-gray-400'>Нет данных</span>;
	const view = STATUS_VIEW[status];
	const Icon = view.icon;
	return (
		<span className={`inline-flex items-center gap-1.5 text-sm font-medium ${view.className}`}>
			<Icon className={`w-4 h-4 ${status === 'PROCESSING' ? 'animate-spin' : ''}`} />
			{view.label}
		</span>
	);
}

function ModelPicker({
	models,
	value,
	onChange,
	disabled,
}: {
	models: ModelOption[];
	value: TranscriptionModel;
	onChange: (model: TranscriptionModel) => void;
	disabled?: boolean;
}) {
	return (
		<div className='grid gap-3 sm:grid-cols-2' role='radiogroup'>
			{models.map((m) => {
				const selected = m.id === value;
				return (
					<button
						key={m.id}
						type='button'
						role='radio'
						aria-checked={selected}
						disabled={disabled}
						onClick={() => onChange(m.id)}
						className={`text-left p-4 rounded-lg border transition-all cursor-pointer disabled:cursor-not-allowed disabled:opacity-60 ${
							selected
								? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 dark:border-blue-500'
								: 'border-gray-200 bg-white hover:border-blue-300 dark:bg-gray-700 dark:border-gray-600'
						}`}
					>
						<p className='font-semibold text-gray-900 dark:text-gray-100'>
							{m.title}
						</p>
						<p className='text-sm text-gray-500 dark:text-gray-400 mt-1'>
							{m.description}
						</p>
					</button>
				);
			})}
		</div>
	);
}

export default function Lessons() {
	const token = localStorage.getItem('token') ?? '';
	const [searchParams, setSearchParams] = useSearchParams();
	// id урока хранится в адресе: после перезагрузки страницы опрос продолжается.
	const lessonId = searchParams.get('lesson');

	const [models, setModels] = useState<ModelOption[]>([]);
	const [modelsLoading, setModelsLoading] = useState(true);
	const [modelsError, setModelsError] = useState('');

	const [file, setFile] = useState<File | null>(null);
	const [title, setTitle] = useState('');
	const [topic, setTopic] = useState('');
	const [model, setModel] = useState<TranscriptionModel>('fast');
	const [formError, setFormError] = useState('');
	const [uploading, setUploading] = useState(false);
	const [progress, setProgress] = useState(0);

	const [myLessons, setMyLessons] = useState<Lesson[]>([]);
	const [listLoading, setListLoading] = useState(false);
	const [listError, setListError] = useState('');
	const [hasMore, setHasMore] = useState(false);

	const [lesson, setLesson] = useState<Lesson | null>(null);
	const [transcript, setTranscript] = useState<Transcript | null>(null);
	const [pollError, setPollError] = useState('');
	// Меняется при повторном запуске, чтобы заново начать опрос того же урока.
	const [pollRun, setPollRun] = useState(0);

	const [retryModel, setRetryModel] = useState<TranscriptionModel>('fast');
	const [retrying, setRetrying] = useState(false);
	const [retryError, setRetryError] = useState('');

	const fetchModels = async () => {
		setModelsLoading(true);
		setModelsError('');
		try {
			const options = await getLessonModels(token);
			setModels(options);
			if (options.length > 0 && !options.some((o) => o.id === model))
				setModel(options[0].id);
		} catch (e: any) {
			setModelsError(e.message || 'Не удалось загрузить варианты распознавания');
		} finally {
			setModelsLoading(false);
		}
	};

	const fetchLessons = async (offset: number) => {
		setListLoading(true);
		setListError('');
		try {
			const page = await listLessons(token, LIST_PAGE_SIZE, offset);
			setMyLessons((prev) => (offset === 0 ? page : [...prev, ...page]));
			setHasMore(page.length === LIST_PAGE_SIZE);
		} catch (e: any) {
			setListError(e.message || 'Не удалось загрузить список записей');
		} finally {
			setListLoading(false);
		}
	};

	useEffect(() => {
		fetchModels();
	}, []);

	// Список обновляется при каждом возврате со страницы урока: статусы могли измениться.
	useEffect(() => {
		if (!lessonId) fetchLessons(0);
	}, [lessonId]);

	useEffect(() => {
		if (!lessonId) return;
		let cancelled = false;
		let timer: ReturnType<typeof setTimeout> | undefined;
		setPollError('');

		const poll = async () => {
			try {
				const current = await getLesson(token, lessonId);
				if (cancelled) return;
				setLesson(current);
				const status = current.transcript_status;
				if (status && FINAL_STATUSES.includes(status)) {
					// Текст, ошибка и предупреждение есть только в транскрипте.
					const result = await getTranscript(token, lessonId).catch(() => null);
					if (!cancelled) setTranscript(result);
					return;
				}
				timer = setTimeout(poll, POLL_INTERVAL_MS);
			} catch (e: any) {
				if (!cancelled) setPollError(e.message || 'Не удалось получить статус');
			}
		};
		poll();

		return () => {
			cancelled = true;
			clearTimeout(timer);
		};
	}, [lessonId, pollRun]);

	useEffect(() => {
		if (lesson) setRetryModel(lesson.transcription_model);
	}, [lesson?.id]);

	// Уход со страницы прерывает отправку файла, поэтому предупреждаем.
	useEffect(() => {
		if (!uploading) return;
		const warn = (e: BeforeUnloadEvent) => e.preventDefault();
		window.addEventListener('beforeunload', warn);
		return () => window.removeEventListener('beforeunload', warn);
	}, [uploading]);

	const chooseFile = (picked: File | null) => {
		setFormError('');
		setFile(picked);
		if (!picked) return;
		const fileError = validateFile(picked);
		if (fileError) {
			setFormError(fileError);
			return;
		}
		if (!title.trim()) setTitle(picked.name.replace(/\.[^.]+$/, ''));
	};

	const openLesson = (target: Lesson) => {
		setLesson(target);
		setTranscript(null);
		setRetryError('');
		setSearchParams({ lesson: target.id });
	};

	const backToList = () => {
		setSearchParams({});
		setLesson(null);
		setTranscript(null);
		setPollError('');
		setRetryError('');
	};

	const handleUpload = async (e: React.FormEvent) => {
		e.preventDefault();
		setFormError('');
		if (!file) {
			setFormError('Выберите файл записи');
			return;
		}
		const fileError = validateFile(file);
		if (fileError) {
			setFormError(fileError);
			return;
		}
		if (!title.trim()) {
			setFormError('Введите название урока');
			return;
		}

		setUploading(true);
		setProgress(0);
		try {
			const created = await uploadLesson(token, { file, title, topic, model }, setProgress);
			setFile(null);
			setTitle('');
			setTopic('');
			openLesson(created);
		} catch (err: any) {
			setFormError(err.message || 'Не удалось загрузить запись');
		} finally {
			setUploading(false);
		}
	};

	const handleRetry = async () => {
		if (!lesson) return;
		setRetrying(true);
		setRetryError('');
		try {
			const updated = await retryLesson(token, lesson.id, retryModel);
			setLesson(updated);
			setTranscript(null);
			setPollRun((n) => n + 1);
		} catch (e: any) {
			setRetryError(e.message || 'Не удалось запустить распознавание');
		} finally {
			setRetrying(false);
		}
	};

	const modelTitle = (id: TranscriptionModel) =>
		models.find((m) => m.id === id)?.title ?? id;

	if (lessonId) {
		return (
			<div className='p-8 bg-gray-50 dark:bg-gray-900 min-h-screen'>
				<Button
					variant='ghost'
					onClick={backToList}
					className='mb-4 -ml-3 cursor-pointer text-gray-600 dark:text-gray-300'
				>
					<ArrowLeft className='w-4 h-4 mr-2' />
					Все записи
				</Button>
				<LessonStatusCard
					lesson={lesson}
					transcript={transcript}
					pollError={pollError}
					onRefresh={() => setPollRun((n) => n + 1)}
					modelTitle={modelTitle}
					models={models}
					retryModel={retryModel}
					onRetryModelChange={setRetryModel}
					onRetry={handleRetry}
					retrying={retrying}
					retryError={retryError}
				/>
			</div>
		);
	}

	return (
		<div className='p-8 bg-gray-50 dark:bg-gray-900 min-h-screen'>
			<div className='mb-8'>
				<h1 className='text-3xl font-bold text-gray-900 dark:text-white'>
					Записи уроков
				</h1>
				<p className='text-gray-500 dark:text-gray-400 mt-1'>
					Загрузите запись урока, и сервер превратит речь в текст
				</p>
			</div>

			<Card className='max-w-3xl mb-8 dark:bg-gray-800 dark:border-gray-700'>
				<CardHeader>
					<CardTitle className='dark:text-white'>Новая запись</CardTitle>
					<CardDescription className='dark:text-gray-400'>
						Аудио или видео до {MAX_LESSON_UPLOAD_MB} МБ:{' '}
						{LESSON_EXTENSIONS.map((ext) => ext.slice(1)).join(', ')}
					</CardDescription>
				</CardHeader>
				<CardContent>
					<form className='space-y-6' onSubmit={handleUpload} noValidate>
						<div className='space-y-2'>
							<Label htmlFor='lesson-file' className='dark:text-gray-300'>
								Файл записи
							</Label>
							<Input
								id='lesson-file'
								type='file'
								accept={LESSON_EXTENSIONS.join(',')}
								disabled={uploading}
								onChange={(e) => chooseFile(e.target.files?.[0] ?? null)}
								className='cursor-pointer dark:bg-gray-800 dark:border-gray-600 dark:text-white'
							/>
							{file && (
								<p className='text-sm text-gray-500 dark:text-gray-400 flex items-center gap-2'>
									<FileAudio className='w-4 h-4' />
									{file.name} · {formatSize(file.size)}
								</p>
							)}
						</div>

						<div className='space-y-2'>
							<Label htmlFor='lesson-title' className='dark:text-gray-300'>
								Название
							</Label>
							<Input
								id='lesson-title'
								value={title}
								maxLength={255}
								disabled={uploading}
								onChange={(e) => setTitle(e.target.value)}
								placeholder='Например, Английский: Present Perfect'
								className='dark:bg-gray-800 dark:border-gray-600 dark:text-white'
							/>
						</div>

						<div className='space-y-2'>
							<Label htmlFor='lesson-topic' className='dark:text-gray-300'>
								Тема или ключевые слова{' '}
								<span className='text-gray-400 font-normal'>(необязательно)</span>
							</Label>
							<Input
								id='lesson-topic'
								value={topic}
								maxLength={500}
								disabled={uploading}
								onChange={(e) => setTopic(e.target.value)}
								placeholder='Например, признаки государства, федерализм'
								className='dark:bg-gray-800 dark:border-gray-600 dark:text-white'
							/>
							<p className='text-sm text-gray-500 dark:text-gray-400'>
								Помогает правильно распознать термины и имена.
							</p>
						</div>

						<div className='space-y-2'>
							<Label className='dark:text-gray-300'>Вариант распознавания</Label>
							{modelsLoading ? (
								<Loader2 className='w-5 h-5 animate-spin text-blue-500' />
							) : modelsError ? (
								<div className='flex items-center gap-3'>
									<p className='text-sm text-red-500'>{modelsError}</p>
									<Button type='button' variant='outline' size='sm' onClick={fetchModels}>
										Повторить
									</Button>
								</div>
							) : (
								<ModelPicker
									models={models}
									value={model}
									onChange={setModel}
									disabled={uploading}
								/>
							)}
							<p className='text-sm text-gray-500 dark:text-gray-400'>
								Длинная запись обрабатывается несколько минут и дольше.{' '}
								{model === 'quality' && QUALITY_FIRST_RUN_HINT}
							</p>
						</div>

						{uploading && (
							<div className='space-y-2'>
								<Progress value={Math.round(progress * 100)} />
								<p className='text-sm text-gray-500 dark:text-gray-400'>
									{progress < 1
										? `Отправляем файл: ${Math.round(progress * 100)}%. Не закрывайте страницу.`
										: 'Файл отправлен, сервер сохраняет запись…'}
								</p>
							</div>
						)}

						{formError && (
							<p className='text-sm text-red-500' role='alert'>
								{formError}
							</p>
						)}

						<Button
							type='submit'
							disabled={uploading || modelsLoading || !!modelsError}
							className='bg-blue-600 hover:bg-blue-700 text-white cursor-pointer'
						>
							{uploading ? (
								<Loader2 className='w-4 h-4 mr-2 animate-spin' />
							) : (
								<Upload className='w-4 h-4 mr-2' />
							)}
							Загрузить и распознать
						</Button>
					</form>
				</CardContent>
			</Card>

			<Card className='max-w-3xl dark:bg-gray-800 dark:border-gray-700'>
				<CardHeader>
					<CardTitle className='dark:text-white'>Мои записи</CardTitle>
					<CardDescription className='dark:text-gray-400'>
						Записи и их текст видите только вы
					</CardDescription>
				</CardHeader>
				<CardContent>
					{listError ? (
						<div className='flex items-center gap-3'>
							<p className='text-sm text-red-500'>{listError}</p>
							<Button variant='outline' size='sm' onClick={() => fetchLessons(0)}>
								Повторить
							</Button>
						</div>
					) : myLessons.length === 0 ? (
						listLoading ? (
							<Loader2 className='w-5 h-5 animate-spin text-blue-500' />
						) : (
							<p className='text-sm text-gray-500 dark:text-gray-400'>
								Записей пока нет. Загрузите первую с помощью формы выше.
							</p>
						)
					) : (
						<div className='space-y-2'>
							{myLessons.map((item) => (
								<button
									key={item.id}
									type='button'
									onClick={() => openLesson(item)}
									className='w-full text-left p-4 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50/40 dark:border-gray-600 dark:hover:bg-blue-900/20 transition-all cursor-pointer flex flex-wrap items-center justify-between gap-3'
								>
									<div className='min-w-0'>
										<p className='font-medium text-gray-900 dark:text-gray-100 truncate'>
											{item.title}
										</p>
										<p className='text-sm text-gray-500 dark:text-gray-400'>
											{formatDate(item.created_at)} · «{modelTitle(item.transcription_model)}»
										</p>
									</div>
									<StatusLabel status={item.transcript_status} />
								</button>
							))}
							{hasMore && (
								<Button
									variant='outline'
									disabled={listLoading}
									onClick={() => fetchLessons(myLessons.length)}
									className='w-full cursor-pointer'
								>
									{listLoading && <Loader2 className='w-4 h-4 mr-2 animate-spin' />}
									Показать ещё
								</Button>
							)}
						</div>
					)}
				</CardContent>
			</Card>
		</div>
	);
}

// Для поиска: без регистра и без различия «е» и «ё» (длина строки при этом не меняется).
const normalizeForSearch = (text: string) => text.toLowerCase().replace(/ё/g, 'е');

function Highlighted({ text, needle }: { text: string; needle: string }) {
	if (!needle) return <>{text}</>;
	const normalized = normalizeForSearch(text);
	// Подсветка опирается на совпадающие позиции в двух строках.
	if (normalized.length !== text.length) return <>{text}</>;
	const parts: React.ReactNode[] = [];
	let from = 0;
	for (let at = normalized.indexOf(needle); at !== -1; at = normalized.indexOf(needle, from)) {
		if (at > from) parts.push(text.slice(from, at));
		parts.push(
			<mark
				key={at}
				className='bg-yellow-200 text-gray-900 dark:bg-yellow-500/40 dark:text-white rounded-sm'
			>
				{text.slice(at, at + needle.length)}
			</mark>,
		);
		from = at + needle.length;
	}
	if (from < text.length) parts.push(text.slice(from));
	return <>{parts}</>;
}

function TranscriptView({ transcript }: { transcript: Transcript }) {
	const [copied, setCopied] = useState<'plain' | 'timed' | 'error' | null>(null);
	const [query, setQuery] = useState('');
	// Номер текущего совпадения среди найденных.
	const [current, setCurrent] = useState(0);
	const listRef = useRef<HTMLDivElement>(null);
	const segments = transcript.segments;

	const needle = normalizeForSearch(query.trim());
	const matches = useMemo(
		() =>
			needle
				? segments.reduce<number[]>((found, s, i) => {
						if (normalizeForSearch(s.text).includes(needle)) found.push(i);
						return found;
					}, [])
				: [],
		[segments, needle],
	);
	const activeSegment = matches.length > 0 ? matches[current] : -1;

	useEffect(() => {
		if (!copied) return;
		const timer = setTimeout(() => setCopied(null), 2000);
		return () => clearTimeout(timer);
	}, [copied]);

	useEffect(() => {
		setCurrent(0);
	}, [needle]);

	// Прокручиваем только сам список: страница при этом остаётся на месте.
	useEffect(() => {
		if (activeSegment < 0 || !listRef.current) return;
		const row = listRef.current.querySelector<HTMLElement>(`#segment-${activeSegment}`);
		if (!row) return;
		const list = listRef.current;
		const rowTop = row.offsetTop; // список имеет position: relative, отсчёт от него
		list.scrollTo({
			top: rowTop - (list.clientHeight - row.clientHeight) / 2,
			behavior: 'smooth',
		});
	}, [activeSegment]);

	if (segments.length === 0) {
		return (
			<p className='text-sm text-gray-500 dark:text-gray-400'>
				В записи не найдено речи.
			</p>
		);
	}

	const copy = async (kind: 'plain' | 'timed') => {
		const text = segments
			.map((s) => (kind === 'timed' ? `[${formatTimecode(s.start)}] ${s.text}` : s.text))
			.join('\n');
		try {
			await navigator.clipboard.writeText(text);
			setCopied(kind);
		} catch {
			setCopied('error');
		}
	};

	const step = (delta: number) => {
		if (matches.length === 0) return;
		setCurrent((n) => (n + delta + matches.length) % matches.length);
	};

	const copyLabel = (kind: 'plain' | 'timed', idle: string) =>
		copied === kind ? 'Скопировано' : copied === 'error' ? 'Не удалось скопировать' : idle;

	return (
		<div className='space-y-3'>
			<div className='flex flex-wrap items-center justify-between gap-3'>
				<p className='font-semibold text-gray-900 dark:text-white'>Текст урока</p>
				<div className='flex flex-wrap gap-2'>
					<Button
						variant='outline'
						size='sm'
						onClick={() => copy('plain')}
						className='cursor-pointer'
					>
						{copied === 'plain' ? (
							<Check className='w-4 h-4 mr-2' />
						) : (
							<Copy className='w-4 h-4 mr-2' />
						)}
						{copyLabel('plain', 'Скопировать текст')}
					</Button>
					<Button
						variant='outline'
						size='sm'
						onClick={() => copy('timed')}
						className='cursor-pointer'
					>
						{copied === 'timed' ? (
							<Check className='w-4 h-4 mr-2' />
						) : (
							<Copy className='w-4 h-4 mr-2' />
						)}
						{copyLabel('timed', 'Скопировать с таймкодами')}
					</Button>
				</div>
			</div>

			<div className='flex flex-wrap items-center gap-2'>
				<div className='relative flex-1 min-w-[200px]'>
					<Search className='w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400' />
					<Input
						id='transcript-search'
						value={query}
						onChange={(e) => setQuery(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === 'Enter') {
								e.preventDefault();
								step(e.shiftKey ? -1 : 1);
							}
						}}
						placeholder='Найти в тексте'
						aria-label='Поиск по тексту урока'
						className='pl-9 pr-9 dark:bg-gray-800 dark:border-gray-600 dark:text-white'
					/>
					{query && (
						<button
							type='button'
							onClick={() => setQuery('')}
							aria-label='Очистить поиск'
							className='absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 cursor-pointer'
						>
							<X className='w-4 h-4' />
						</button>
					)}
				</div>
				{needle && (
					<div className='flex items-center gap-1' aria-live='polite'>
						<span className='text-sm text-gray-500 dark:text-gray-400 tabular-nums mr-1'>
							{matches.length > 0
								? `${current + 1} из ${matches.length}`
								: 'Ничего не найдено'}
						</span>
						<Button
							variant='outline'
							size='sm'
							onClick={() => step(-1)}
							disabled={matches.length === 0}
							aria-label='Предыдущее совпадение'
							className='cursor-pointer'
						>
							<ChevronUp className='w-4 h-4' />
						</Button>
						<Button
							variant='outline'
							size='sm'
							onClick={() => step(1)}
							disabled={matches.length === 0}
							aria-label='Следующее совпадение'
							className='cursor-pointer'
						>
							<ChevronDown className='w-4 h-4' />
						</Button>
					</div>
				)}
			</div>

			<div
				ref={listRef}
				className='relative max-h-[60vh] overflow-y-auto rounded-lg border border-gray-200 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-700'
			>
				{segments.map((s, i) => (
					<div
						key={i}
						id={`segment-${i}`}
						className={`flex gap-4 p-3 ${
							i === activeSegment ? 'bg-yellow-50 dark:bg-yellow-900/20' : ''
						}`}
					>
						<span className='w-16 flex-shrink-0 text-sm tabular-nums text-gray-400'>
							{formatTimecode(s.start)}
						</span>
						<p className='text-gray-800 dark:text-gray-200 leading-relaxed'>
							<Highlighted text={s.text} needle={needle} />
						</p>
					</div>
				))}
			</div>
		</div>
	);
}

function LessonStatusCard({
	lesson,
	transcript,
	pollError,
	onRefresh,
	modelTitle,
	models,
	retryModel,
	onRetryModelChange,
	onRetry,
	retrying,
	retryError,
}: {
	lesson: Lesson | null;
	transcript: Transcript | null;
	pollError: string;
	onRefresh: () => void;
	modelTitle: (id: TranscriptionModel) => string;
	models: ModelOption[];
	retryModel: TranscriptionModel;
	onRetryModelChange: (model: TranscriptionModel) => void;
	onRetry: () => void;
	retrying: boolean;
	retryError: string;
}) {
	const status = lesson?.transcript_status ?? null;
	const view = status ? STATUS_VIEW[status] : null;
	const StatusIcon = view?.icon;
	const isActive = status === 'PENDING' || status === 'PROCESSING';

	return (
		<Card className='max-w-4xl dark:bg-gray-800 dark:border-gray-700'>
			<CardHeader>
				<CardTitle className='dark:text-white'>
					{lesson?.title ?? 'Запись урока'}
				</CardTitle>
				{lesson && (
					<CardDescription className='dark:text-gray-400'>
						Вариант «{modelTitle(lesson.transcription_model)}»
						{lesson.topic ? ` · Тема: ${lesson.topic}` : ''} · загружено{' '}
						{formatDate(lesson.created_at)}
					</CardDescription>
				)}
			</CardHeader>
			<CardContent className='space-y-5'>
				{pollError ? (
					<div className='flex flex-wrap items-center gap-3'>
						<p className='text-sm text-red-500' role='alert'>
							{pollError}
						</p>
						<Button variant='outline' size='sm' onClick={onRefresh}>
							Проверить снова
						</Button>
					</div>
				) : !view || !StatusIcon ? (
					<Loader2 className='w-6 h-6 animate-spin text-blue-500' />
				) : (
					<div className='flex items-start gap-3' aria-live='polite'>
						<StatusIcon
							className={`w-6 h-6 flex-shrink-0 ${view.className} ${
								status === 'PROCESSING' ? 'animate-spin' : ''
							}`}
						/>
						<div>
							<p className={`font-semibold ${view.className}`}>{view.label}</p>
							<p className='text-sm text-gray-500 dark:text-gray-400 mt-1'>
								{view.hint}
								{isActive && lesson?.transcription_model === 'quality'
									? ` ${QUALITY_FIRST_RUN_HINT}`
									: ''}
							</p>
							{isActive && (
								<p className='text-xs text-gray-400 mt-1'>
									Статус обновляется автоматически.
								</p>
							)}
						</div>
					</div>
				)}

				{status === 'DONE' && transcript?.note && (
					<div className='flex gap-2 p-3 rounded-md bg-amber-50 text-amber-800 dark:bg-amber-900/20 dark:text-amber-300 text-sm'>
						<TriangleAlert className='w-4 h-4 mt-0.5 flex-shrink-0' />
						<p>{transcript.note}</p>
					</div>
				)}

				{status === 'DONE' && transcript && <TranscriptView transcript={transcript} />}

				{status === 'FAILED' && (
					<div className='space-y-4'>
						<div className='p-3 rounded-md bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-300 text-sm'>
							<p className='font-medium'>Причина</p>
							<p className='mt-1 break-words'>
								{transcript?.error || 'Сервер не сообщил причину ошибки.'}
							</p>
						</div>
						{models.length > 0 && (
							<div className='space-y-2'>
								<Label className='dark:text-gray-300'>
									Каким вариантом распознать ещё раз
								</Label>
								<ModelPicker
									models={models}
									value={retryModel}
									onChange={onRetryModelChange}
									disabled={retrying}
								/>
							</div>
						)}
						{retryError && (
							<p className='text-sm text-red-500' role='alert'>
								{retryError}
							</p>
						)}
						<Button
							onClick={onRetry}
							disabled={retrying}
							className='bg-blue-600 hover:bg-blue-700 text-white cursor-pointer'
						>
							{retrying ? (
								<Loader2 className='w-4 h-4 mr-2 animate-spin' />
							) : (
								<RotateCcw className='w-4 h-4 mr-2' />
							)}
							Распознать ещё раз
						</Button>
					</div>
				)}
			</CardContent>
		</Card>
	);
}
