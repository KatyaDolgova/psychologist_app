import { apiFetch, getErrorMessage } from './client';

export type TranscriptionModel = 'fast' | 'quality';
export type TranscriptStatus = 'PENDING' | 'PROCESSING' | 'DONE' | 'FAILED';

export type ModelOption = {
	id: TranscriptionModel;
	title: string;
	description: string;
};

export type Lesson = {
	id: string;
	title: string;
	topic: string | null;
	transcription_model: TranscriptionModel;
	created_at: string;
	transcript_status: TranscriptStatus | null;
};

export type Transcript = {
	lesson_id: string;
	status: TranscriptStatus;
	language: string | null;
	segments: { start: number; end: number; text: string; speaker: string | null }[];
	error: string | null;
	note: string | null;
	updated_at: string;
};

// Должно совпадать с ALLOWED_EXTENSIONS и MAX_LESSON_UPLOAD_MB на бэкенде.
export const LESSON_EXTENSIONS = ['.mp3', '.m4a', '.aac', '.wav', '.ogg', '.flac', '.webm', '.mp4'];
export const MAX_LESSON_UPLOAD_MB = 500;

export const FILE_TOO_LARGE_MESSAGE = `Файл больше ${MAX_LESSON_UPLOAD_MB} МБ. Сожмите запись или разделите её на части.`;
export const UNSUPPORTED_FORMAT_MESSAGE = `Этот формат не поддерживается. Подойдут: ${LESSON_EXTENSIONS.map((e) => e.slice(1)).join(', ')}.`;

const STATUS_MESSAGES: Record<number, string> = {
	413: FILE_TOO_LARGE_MESSAGE,
	415: UNSUPPORTED_FORMAT_MESSAGE,
};

const authHeaders = (token: string) => ({
	'Content-Type': 'application/json',
	Authorization: `Bearer ${token}`,
});

async function readError(res: Response): Promise<string> {
	if (STATUS_MESSAGES[res.status]) return STATUS_MESSAGES[res.status];
	try {
		return getErrorMessage(await res.json());
	} catch {
		return getErrorMessage(null);
	}
}

export const getLessonModels = async (token: string): Promise<ModelOption[]> => {
	const res = await apiFetch('/lessons/models', { headers: authHeaders(token) });
	if (!res.ok) throw new Error(await readError(res));
	return res.json();
};

export const listLessons = async (
	token: string,
	limit: number,
	offset: number,
): Promise<Lesson[]> => {
	const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
	const res = await apiFetch(`/lessons/?${params}`, { headers: authHeaders(token) });
	if (!res.ok) throw new Error(await readError(res));
	return res.json();
};

export const getLesson = async (token: string, lessonId: string): Promise<Lesson> => {
	const res = await apiFetch(`/lessons/${lessonId}`, { headers: authHeaders(token) });
	if (!res.ok) throw new Error(await readError(res));
	return res.json();
};

export const getTranscript = async (token: string, lessonId: string): Promise<Transcript> => {
	const res = await apiFetch(`/lessons/${lessonId}/transcript`, {
		headers: authHeaders(token),
	});
	if (!res.ok) throw new Error(await readError(res));
	return res.json();
};

export const retryLesson = async (
	token: string,
	lessonId: string,
	model?: TranscriptionModel,
): Promise<Lesson> => {
	const res = await apiFetch(`/lessons/${lessonId}/retry`, {
		method: 'POST',
		headers: authHeaders(token),
		body: JSON.stringify(model ? { model } : {}),
	});
	if (!res.ok) throw new Error(await readError(res));
	return res.json();
};

export type UploadLessonForm = {
	file: File;
	title: string;
	topic: string;
	model: TranscriptionModel;
};

// fetch не сообщает прогресс отправки, а запись может весить сотни мегабайт,
// поэтому загрузка идёт через XMLHttpRequest. onProgress получает долю от 0 до 1.
export const uploadLesson = (
	token: string,
	form: UploadLessonForm,
	onProgress: (fraction: number) => void,
): Promise<Lesson> => {
	const data = new FormData();
	data.append('title', form.title.trim());
	// Пустую тему не отправляем совсем: иначе она уйдёт в распознавание подсказкой.
	const topic = form.topic.trim();
	if (topic) data.append('topic', topic);
	data.append('model', form.model);
	data.append('file', form.file);

	return new Promise((resolve, reject) => {
		const xhr = new XMLHttpRequest();
		xhr.open('POST', '/lessons/');
		xhr.setRequestHeader('Authorization', `Bearer ${token}`);
		xhr.upload.onprogress = (e) => {
			if (e.lengthComputable) onProgress(e.loaded / e.total);
		};
		xhr.onload = () => {
			if (xhr.status === 401) {
				localStorage.removeItem('token');
				window.location.replace('/auth');
				reject(new Error('Unauthorized'));
				return;
			}
			let body: any = null;
			try {
				body = JSON.parse(xhr.responseText);
			} catch {
				// Ответ не JSON, например страница ошибки прокси.
			}
			if (xhr.status >= 200 && xhr.status < 300) resolve(body);
			else reject(new Error(STATUS_MESSAGES[xhr.status] ?? getErrorMessage(body)));
		};
		xhr.onerror = () =>
			reject(new Error('Не удалось отправить файл. Проверьте подключение к интернету'));
		xhr.send(data);
	});
};
