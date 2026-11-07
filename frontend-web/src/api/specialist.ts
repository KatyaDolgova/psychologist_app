import { apiFetch, getErrorMessage } from './client';
import { SPECIALISTS_API, USER_SPECIALISTS_API } from './contract';

export const getSpecialistProfile = async (token: string) => {
	const url = `${SPECIALISTS_API}/profile/`;
	try {
		const res = await apiFetch(url, {
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
		});

		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
		return res.json();
	} catch (error: any) {
		console.log('Ошибка во время получения профиля специалиста: ', error);
		throw error;
	}
};

export const updateSpecialistProfile = async (token: string, form: any) => {
	const url = `${SPECIALISTS_API}/profile/`;
	try {
		const res = await apiFetch(url, {
			method: 'PATCH',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
			body: JSON.stringify(form),
		});

		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
		return res.json();
	} catch (error: any) {
		console.log('Ошибка во время обновления профиля специалиста: ', error);
		throw error;
	}
};

export const updateSpecialistPhoto = async (token: string, file: File) => {
	const url = `${SPECIALISTS_API}/profile/upload_photo/`;

	try {
		const formData = new FormData();
		formData.append('image', file);

		const res = await apiFetch(url, {
			method: 'POST',
			headers: {
				Authorization: `Bearer ${token}`,
			},
			body: formData,
		});

		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}

		return res.json();
	} catch (error: any) {
		console.log('Ошибка во время обновления аватара специалиста: ', error);
		throw error;
	}
};

export const getSpecialistAppointments = async (
	token: string,
	isUpcoming?: boolean,
) => {
	const params = new URLSearchParams({ limit: '100', offset: '0' });
	if (isUpcoming !== undefined) params.set('is_upcoming', String(isUpcoming));
	const url = `${SPECIALISTS_API}/appointments/?${params}`;
	try {
		const res = await apiFetch(url, {
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
		});

		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
		return res.json();
	} catch (error: any) {
		console.log('Ошибка во время получения записей специалиста: ', error);
		throw error;
	}
};

export const getSpecialistsForClient = async (token: string) => {
	const url = `${USER_SPECIALISTS_API}/`;
	try {
		const res = await apiFetch(url, {
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
		});
		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
		return res.json();
	} catch (error: any) {
		console.log('Ошибка во время получения специалистов: ', error);
		throw error;
	}
};

export const getAllAppointments = async (
	token: string,
	isUpcoming?: boolean,
) => {
	const params = new URLSearchParams({ limit: '100', offset: '0' });
	if (isUpcoming !== undefined) params.set('is_upcoming', String(isUpcoming));
	const url = `/user/appointments/?${params}`;
	try {
		const res = await apiFetch(url, {
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
		});

		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
		return res.json();
	} catch (error: any) {
		console.log('Ошибка во время получения всех записей: ', error);
		throw error;
	}
};

export const addToFavorite = async (token: string, id: number) => {
	const url = `${USER_SPECIALISTS_API}/favorites/`;
	try {
		const res = await apiFetch(url, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
			body: JSON.stringify({ id }),
		});

		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
	} catch (error: any) {
		console.log(
			'Ошибка во время добавления специалистов в избранное: ',
			error,
		);
		throw error;
	}
};

export const getAllFavorites = async (token: string) => {
	const url = `${USER_SPECIALISTS_API}/favorites/`;
	try {
		const res = await apiFetch(url, {
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
		});

		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}

		return res.json();
	} catch (error: any) {
		console.log('Ошибка во время получения избранных специалистов: ', error);
		throw error;
	}
};

export const deleteFavoriteSpecialist = async (token: string, id: number) => {
	const url = `${USER_SPECIALISTS_API}/favorites/${id}/`;
	try {
		const res = await apiFetch(url, {
			method: 'DELETE',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
		});

		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
	} catch (error: any) {
		console.log(
			'Ошибка во время получения удаления специалиста из избранного: ',
			error,
		);
		throw error;
	}
};

export const getWorkingHours = async (token: string) => {
	const res = await apiFetch(`${SPECIALISTS_API}/template/`, {
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`,
		},
	});
	if (!res.ok) throw new Error(getErrorMessage(await res.json()));
	return res.json();
};

export const updateWorkingHours = async (token: string, ranges: any[]) => {
	const res = await apiFetch(`${SPECIALISTS_API}/template/`, {
		method: 'PUT',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({ ranges }),
	});
	if (!res.ok) throw new Error(getErrorMessage(await res.json()));
	return res.json();
};

export const getClientsForSpecialist = async (token: string) => {
	const url = `${SPECIALISTS_API}/clients/`;
	try {
		const res = await apiFetch(url, {
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
		});
		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
		return res.json();
	} catch (error: any) {
		console.log('Ошибка во время получения учеников: ', error);
		throw error;
	}
};

export const getSpecialistAppointmentsForClient = async (
	token: string,
	client_id: number,
	isUpcoming?: boolean,
) => {
	const params = new URLSearchParams({
		client_id: String(client_id),
		limit: '100',
		offset: '0',
	});
	if (isUpcoming !== undefined) params.set('is_upcoming', String(isUpcoming));
	const url = `${SPECIALISTS_API}/appointments/?${params}`;
	try {
		const res = await apiFetch(url, {
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
		});
		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
		return res.json();
	} catch (error: any) {
		console.log('Ошибка при получении занятий ученика:', error);
		throw error;
	}
};

export const getClientForSpecialistByID = async (
	token: string,
	user_id: number,
) => {
	const url = `${SPECIALISTS_API}/clients/${user_id}`;
	try {
		const res = await apiFetch(url, {
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
		});
		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
		return res.json();
	} catch (error: any) {
		console.log('Ошибка во время получения ученика по ID: ', error);
		throw error;
	}
};

export const getMySlots = async (
	token: string,
	fromDt: string,
	toDt: string,
	status?: string,
) => {
	const params = new URLSearchParams({ from_dt: fromDt, to_dt: toDt });
	if (status) params.set('status', status);
	const res = await apiFetch(`${SPECIALISTS_API}/slots/?${params}`, {
		headers: { Authorization: `Bearer ${token}` },
	});
	if (!res.ok) throw new Error(getErrorMessage(await res.json()));
	return res.json();
};

export const generateSlots = async (
	token: string,
	fromDate: string,
	toDate: string,
) => {
	const params = new URLSearchParams({
		from_date: fromDate,
		to_date: toDate,
	});
	const res = await apiFetch(`${SPECIALISTS_API}/slots/generate?${params}`, {
		method: 'POST',
		headers: { Authorization: `Bearer ${token}` },
	});
	if (!res.ok) throw new Error(getErrorMessage(await res.json()));
	return res.json();
};

export const createManualSlot = async (token: string, startsAt: string) => {
	const res = await apiFetch(`${SPECIALISTS_API}/slots/`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({ starts_at: startsAt }),
	});
	if (!res.ok) throw new Error(getErrorMessage(await res.json()));
	return res.json();
};

export const deleteSlot = async (token: string, slotId: string) => {
	const res = await apiFetch(`${SPECIALISTS_API}/slots/${slotId}`, {
		method: 'DELETE',
		headers: { Authorization: `Bearer ${token}` },
	});
	if (!res.ok && res.status !== 204)
		throw new Error(getErrorMessage(await res.json()));
};

export const cancelSlot = async (
	token: string,
	slotId: string,
	reason?: string,
) => {
	const res = await apiFetch(`${SPECIALISTS_API}/slots/${slotId}/cancel`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({ reason: reason ?? null }),
	});
	if (!res.ok && res.status !== 204)
		throw new Error(getErrorMessage(await res.json()));
};

export const getFreeSlots = async (
	token: string,
	specialistId: number,
	fromDt: string,
	toDt: string,
) => {
	const params = new URLSearchParams({ from_dt: fromDt, to_dt: toDt });
	const res = await apiFetch(
		`${SPECIALISTS_API}/${specialistId}/free-slots/?${params}`,
		{ headers: { Authorization: `Bearer ${token}` } },
	);
	if (!res.ok) throw new Error(getErrorMessage(await res.json()));
	return res.json();
};

export const bookSlot = async (token: string, slotId: string) => {
	const res = await apiFetch('/user/appointments/', {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({ slot_id: slotId }),
	});
	if (!res.ok) throw new Error(getErrorMessage(await res.json()));
	return res.json();
};

export const cancelAppointment = async (
	token: string,
	appointmentId: string,
) => {
	const res = await apiFetch(`/user/appointments/${appointmentId}`, {
		method: 'DELETE',
		headers: { Authorization: `Bearer ${token}` },
	});
	if (!res.ok && res.status !== 204)
		throw new Error(getErrorMessage(await res.json()));
};

export const getClientNotes = async (token: string, client_id: number) => {
	const url = `${SPECIALISTS_API}/clients/${client_id}/notes`;
	try {
		const res = await apiFetch(url, {
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
		});
		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
		return res.json();
	} catch (error: any) {
		console.log('Ошибка во время получения записей о ученике: ', error);
		throw error;
	}
};

export const createClientNote = async (
	token: string,
	client_id: number,
	text: string,
) => {
	const url = `${SPECIALISTS_API}/clients/${client_id}/notes`;
	try {
		const res = await apiFetch(url, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
			body: JSON.stringify({ text }),
		});
		if (!res.ok) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
		return res.json();
	} catch (error: any) {
		console.log('Ошибка во время получения записей о ученике: ', error);
		throw error;
	}
};

export const deleteClientNote = async (
	token: string,
	client_id: number,
	note_id: number,
) => {
	const url = `${SPECIALISTS_API}/clients/${client_id}/notes/${note_id}`;
	try {
		const res = await apiFetch(url, {
			method: 'DELETE',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
			},
		});
		if (!res.ok && res.status !== 204) {
			const error = await res.json();
			throw new Error(getErrorMessage(error));
		}
	} catch (error: any) {
		console.log('Ошибка при удалении заметки:', error);
		throw error;
	}
};
