(() => {
  'use strict';

  const root = document.getElementById('booking-app');
  const dataNode = document.getElementById('public-company-data');
  if (!root || !dataNode) return;

  let company;
  try {
    company = JSON.parse(dataNode.textContent);
  } catch (error) {
    return;
  }

  const $ = (id) => document.getElementById(id);
  const bookingView = $('booking-view');
  const confirmationView = $('confirmation-view');
  const serviceList = $('service-list');
  const branchSelect = $('branch-select');
  const workerSelect = $('worker-select');
  const dateInput = $('date-input');
  const slotList = $('slot-list');
  const slotsStatus = $('slots-status');
  const contactPanel = $('contact-panel');
  const summary = $('selection-summary');
  const form = $('booking-form');
  const submitButton = $('submit-booking');
  const formError = $('form-error');
  const loadError = $('load-error');
  const confirmationStatus = $('confirmation-status');
  const confirmationHeading = $('confirmation-heading');
  const confirmationCode = $('confirmation-code');
  const confirmationDetail = $('confirmation-detail');
  const cancelError = $('cancel-error');
  const cancelButton = $('cancel-booking');
  const newBookingButton = $('new-booking');
  const rescheduleError = $('reschedule-error');
  const rescheduleButton = $('reschedule-booking');
  const reschedulePanel = $('reschedule-panel');
  const rescheduleDate = $('reschedule-date');
  const rescheduleSlots = $('reschedule-slots');
  const rescheduleStatus = $('reschedule-status');

  const branches = Array.isArray(company.branches) ? company.branches : [];
  const services = Array.isArray(company.services) ? company.services : [];
  const workers = Array.isArray(company.workers) ? company.workers : [];
  const endpoints = {
    availability: root.dataset.availabilityUrl,
    bookings: root.dataset.bookingsUrl,
    detail: root.dataset.detailBase,
    cancel: root.dataset.cancelBase,
    reschedule: root.dataset.rescheduleBase,
  };
  const state = {
    serviceId: null, slot: null, booking: null, requestId: 0, rescheduleRequestId: 0,
  };

  const motion = () =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function showError(node, message) {
    node.textContent = message || '';
    node.hidden = !message;
  }

  function firstError(payload, fallback) {
    const messages = [];
    const visit = (value) => {
      if (value == null) return;
      if (typeof value === 'string') {
        messages.push(value);
        return;
      }
      if (Array.isArray(value)) {
        value.forEach(visit);
        return;
      }
      if (typeof value === 'object') {
        Object.keys(value).forEach((key) => visit(value[key]));
      }
    };
    visit(payload);
    return messages[0] || fallback;
  }

  function formatMoney(value) {
    const amount = Number(value);
    return Number.isFinite(amount)
      ? new Intl.NumberFormat('es-CL', {
          style: 'currency',
          currency: 'CLP',
          maximumFractionDigits: 0,
        }).format(amount)
      : String(value);
  }

  function formatStart(iso, timeZone) {
    if (!iso) return '—';
    try {
      return new Intl.DateTimeFormat('es-CL', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        hour: '2-digit',
        minute: '2-digit',
        timeZone,
      }).format(new Date(iso));
    } catch (error) {
      return new Date(iso).toLocaleString('es-CL');
    }
  }

  function formatDay(value) {
    if (!value) return '';
    const parts = value.split('-').map(Number);
    if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) return value;
    return new Intl.DateTimeFormat('es-CL', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
    }).format(new Date(parts[0], parts[1] - 1, parts[2], 12));
  }

  function todayIn(timeZone) {
    try {
      return new Intl.DateTimeFormat('en-CA', {
        timeZone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }).format(new Date());
    } catch (error) {
      const now = new Date();
      return [
        now.getFullYear(),
        String(now.getMonth() + 1).padStart(2, '0'),
        String(now.getDate()).padStart(2, '0'),
      ].join('-');
    }
  }

  function readableOn(hex) {
    const value = String(hex || '').replace('#', '');
    if (!/^[0-9a-fA-F]{6}$/.test(value)) return '#FFFFFF';
    const [red, green, blue] = [0, 2, 4]
      .map((index) => parseInt(value.slice(index, index + 2), 16) / 255)
      .map((channel) =>
        channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4),
      );
    const luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue;
    return luminance > 0.45 ? '#090909' : '#FFFFFF';
  }

  document.documentElement.style.setProperty(
    '--on-brand',
    readableOn(root.dataset.primaryColor),
  );

  function currentBranch() {
    return branches.find((branch) => branch.id === branchSelect.value) || null;
  }

  function currentWorker() {
    return workers.find((worker) => worker.id === workerSelect.value) || null;
  }

  function currentService() {
    return services.find((service) => service.id === state.serviceId) || null;
  }

  function serviceFitsBranch(service, branchId) {
    const branchIds = Array.isArray(service.branch_ids) ? service.branch_ids : [];
    return branchIds.length === 0 || branchIds.includes(branchId);
  }

  function workerFitsBranch(worker, branchId) {
    const branchIds = Array.isArray(worker.branch_ids) ? worker.branch_ids : [];
    return branchIds.includes(branchId);
  }

  function renderServices() {
    const branchId = branchSelect.value;
    clear(serviceList);
    const available = services.filter((service) => serviceFitsBranch(service, branchId));
    if (state.serviceId && !available.some((service) => service.id === state.serviceId)) {
      state.serviceId = null;
    }
    if (!available.length) {
      serviceList.append(el('p', 'muted', 'No hay servicios disponibles en esta sucursal.'));
      return;
    }
    available.forEach((service) => {
      const button = el('button', 'service-card');
      button.type = 'button';
      button.dataset.serviceId = service.id;
      if (service.id === state.serviceId) button.classList.add('is-selected');
      button.append(
        el('strong', '', service.name),
        el('span', '', `${service.duration_minutes} min · ${formatMoney(service.price)}`),
      );
      button.addEventListener('click', () => {
        state.serviceId = service.id;
        state.slot = null;
        renderServices();
        renderWorkers();
        updateSummary();
        loadAvailability();
      });
      serviceList.append(button);
    });
  }

  function renderWorkers() {
    const branchId = branchSelect.value;
    const previous = workerSelect.value;
    clear(workerSelect);
    workerSelect.append(new Option('Elige profesional', ''));
    const available = workers.filter((worker) => workerFitsBranch(worker, branchId));
    available.forEach((worker) => {
      workerSelect.append(new Option(worker.display_name, worker.id));
    });
    if (previous && available.some((worker) => worker.id === previous)) {
      workerSelect.value = previous;
    } else if (available.length === 1) {
      workerSelect.value = available[0].id;
    }
    if (!available.length) {
      workerSelect.append(new Option('Sin profesionales disponibles', ''));
    }
  }

  function updateSummary() {
    const service = currentService();
    const worker = currentWorker();
    const branch = currentBranch();
    const parts = [];
    if (service) parts.push(service.name);
    if (worker) parts.push(worker.display_name);
    if (branch) parts.push(branch.name);
    if (state.slot) parts.push(`${formatDay(dateInput.value)} · ${state.slot.label}`);
    else if (service) parts.push('Elige un horario');
    summary.textContent = parts.join(' · ');
    contactPanel.hidden = !state.slot;
  }

  function clearSlotSelection() {
    state.slot = null;
    clear(slotList);
    contactPanel.hidden = true;
  }

  async function loadAvailability() {
    const requestId = ++state.requestId;
    clearSlotSelection();
    const service = currentService();
    const worker = currentWorker();
    const branch = currentBranch();
    const date = dateInput.value;
    if (!service || !worker || !branch || !date) {
      slotsStatus.textContent = 'Elige servicio y profesional.';
      return;
    }
    slotsStatus.textContent = 'Buscando horarios…';
    try {
      const params = new URLSearchParams({
        branch: branch.id,
        service: service.id,
        worker: worker.id,
        date,
      });
      const response = await fetch(`${endpoints.availability}?${params.toString()}`, {
        headers: { Accept: 'application/json' },
      });
      const data = await response.json().catch(() => ({}));
      if (requestId !== state.requestId) return;
      if (!response.ok) throw new Error(firstError(data, 'No pudimos cargar los horarios.'));
      const slots = Array.isArray(data.slots) ? data.slots : [];
      if (!slots.length) {
        slotsStatus.textContent = 'No quedan cupos para esa fecha. Prueba otro día.';
        return;
      }
      slotsStatus.textContent = `${slots.length} horario${slots.length === 1 ? '' : 's'} disponible${slots.length === 1 ? '' : 's'}`;
      slots.forEach((slot) => {
        const button = el('button', 'slot', slot.label);
        button.type = 'button';
        button.addEventListener('click', () => {
          state.slot = slot;
          Array.from(slotList.children).forEach((node) => {
            node.classList.toggle('is-selected', node === button);
          });
          updateSummary();
          contactPanel.scrollIntoView({ behavior: motion(), block: 'start' });
        });
        slotList.append(button);
      });
    } catch (error) {
      if (requestId !== state.requestId) return;
      slotsStatus.textContent = error.message;
    }
  }

  function appendDetail(label, value) {
    const row = el('div');
    row.append(el('dt', '', label), el('dd', '', value || '—'));
    confirmationDetail.append(row);
  }

  function showConfirmation(booking) {
    state.booking = booking;
    bookingView.hidden = true;
    confirmationView.hidden = false;
    const cancelled = booking.status === 'canceled';
    confirmationStatus.textContent = booking.status_display || 'Reserva confirmada';
    confirmationStatus.classList.toggle('is-cancelled', cancelled);
    confirmationHeading.textContent = cancelled
      ? 'Esta reserva fue cancelada.'
      : 'Tu hora está reservada.';
    confirmationCode.textContent = booking.public_code || '';
    clear(confirmationDetail);
    appendDetail('Servicio', booking.service_name);
    appendDetail('Profesional', booking.worker_name);
    appendDetail('Sucursal', booking.branch_name);
    appendDetail('Fecha', formatStart(booking.start_at, booking.branch_timezone));
    appendDetail('Duración', booking.duration_minutes ? `${booking.duration_minutes} min` : '');
    appendDetail('Valor', formatMoney(booking.price));
    cancelButton.hidden = !['scheduled', 'confirmed'].includes(booking.status);
    rescheduleButton.hidden = !booking.can_reschedule;
    hideReschedulePanel();
    rescheduleError.classList.remove('is-success');
    showError(rescheduleError, '');
    cancelError.classList.remove('is-success');
    showError(cancelError, '');
    window.scrollTo({ top: 0, behavior: motion() });
  }

  function hideReschedulePanel() {
    state.rescheduleRequestId += 1;
    reschedulePanel.hidden = true;
    rescheduleButton.textContent = 'Reagendar';
    rescheduleDate.value = '';
    rescheduleStatus.textContent = 'Elige una fecha.';
    clear(rescheduleSlots);
  }

  function openReschedulePanel() {
    const booking = state.booking;
    if (!booking || !booking.can_reschedule) return;
    const today = todayIn(booking.branch_timezone);
    rescheduleDate.min = today;
    if (!rescheduleDate.value || rescheduleDate.value < today) rescheduleDate.value = today;
    reschedulePanel.hidden = false;
    rescheduleButton.textContent = 'Ocultar horarios';
    loadRescheduleSlots();
    reschedulePanel.scrollIntoView({ behavior: motion(), block: 'start' });
  }

  async function loadRescheduleSlots() {
    const booking = state.booking;
    if (!booking) return;
    const requestId = ++state.rescheduleRequestId;
    clear(rescheduleSlots);
    const date = rescheduleDate.value;
    if (!date) {
      rescheduleStatus.textContent = 'Elige una fecha.';
      return;
    }
    rescheduleStatus.textContent = 'Buscando horarios…';
    showError(rescheduleError, '');
    try {
      const params = new URLSearchParams({
        branch: booking.branch,
        service: booking.service,
        worker: booking.worker,
        date,
        exclude_booking: booking.public_code,
      });
      const response = await fetch(`${endpoints.availability}?${params.toString()}`, {
        headers: { Accept: 'application/json' },
      });
      const data = await response.json().catch(() => ({}));
      if (requestId !== state.rescheduleRequestId) return;
      if (!response.ok) throw new Error(firstError(data, 'No pudimos cargar los horarios.'));
      const currentStart = booking.start_at ? new Date(booking.start_at).getTime() : null;
      const slots = (Array.isArray(data.slots) ? data.slots : [])
        .filter((slot) => currentStart === null || new Date(slot.start_at).getTime() !== currentStart);
      if (!slots.length) {
        rescheduleStatus.textContent = 'No quedan cupos para esa fecha. Prueba otro día.';
        return;
      }
      rescheduleStatus.textContent = `${slots.length} horario${slots.length === 1 ? '' : 's'} disponible${slots.length === 1 ? '' : 's'}`;
      slots.forEach((slot) => {
        const button = el('button', 'slot', slot.label);
        button.type = 'button';
        button.addEventListener('click', () => rescheduleTo(slot, button));
        rescheduleSlots.append(button);
      });
    } catch (error) {
      if (requestId !== state.rescheduleRequestId) return;
      rescheduleStatus.textContent = error.message;
    }
  }

  async function rescheduleTo(slot, button) {
    const booking = state.booking;
    if (!booking || !booking.public_code) return;
    const buttons = Array.from(rescheduleSlots.children);
    buttons.forEach((node) => { node.disabled = true; });
    button.classList.add('is-selected');
    showError(rescheduleError, '');
    rescheduleStatus.textContent = 'Reagendando…';
    try {
      const response = await fetch(
        endpoints.reschedule.replace('CODE', encodeURIComponent(booking.public_code)),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ start_at: slot.start_at }),
        },
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(firstError(data, 'No pudimos reagendar la reserva.'));
      showConfirmation(data);
      showError(rescheduleError, 'Reserva reprogramada correctamente.');
      rescheduleError.classList.add('is-success');
    } catch (error) {
      showError(rescheduleError, error.message);
      rescheduleStatus.textContent = '';
      buttons.forEach((node) => { node.disabled = false; });
      button.classList.remove('is-selected');
    }
  }

  async function loadReservation(code, openReschedule = false) {
    try {
      const response = await fetch(
        endpoints.detail.replace('CODE', encodeURIComponent(code)),
        { headers: { Accept: 'application/json' } },
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(firstError(data, 'No encontramos esa reserva.'));
      showConfirmation(data);
      if (openReschedule && data.can_reschedule) openReschedulePanel();
    } catch (error) {
      bookingView.hidden = true;
      confirmationView.hidden = false;
      confirmationStatus.textContent = 'Reserva no encontrada';
      confirmationStatus.classList.add('is-cancelled');
      confirmationHeading.textContent = 'No pudimos cargar esa reserva.';
      confirmationCode.textContent = code;
      clear(confirmationDetail);
      cancelButton.hidden = true;
      rescheduleButton.hidden = true;
      hideReschedulePanel();
      showError(cancelError, error.message);
    }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    showError(formError, '');
    const service = currentService();
    const worker = currentWorker();
    const branch = currentBranch();
    if (!state.slot || !service || !worker || !branch) {
      showError(formError, 'Elige un horario disponible antes de confirmar.');
      return;
    }
    const data = new FormData(form);
    const payload = {
      branch: branch.id,
      service: service.id,
      worker: worker.id,
      start_at: state.slot.start_at,
      first_name: String(data.get('first_name') || '').trim(),
      last_name: String(data.get('last_name') || '').trim(),
      email: String(data.get('email') || '').trim(),
      phone: String(data.get('phone') || '').trim(),
      notes: String(data.get('notes') || '').trim(),
    };
    if (!payload.first_name || !payload.email) {
      showError(formError, 'Completa tu nombre y correo para confirmar.');
      return;
    }
    submitButton.disabled = true;
    submitButton.textContent = 'Confirmando…';
    try {
      const response = await fetch(endpoints.bookings, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(firstError(body, 'No pudimos confirmar la reserva.'));
      showConfirmation(body);
    } catch (error) {
      showError(formError, error.message);
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = 'Confirmar reserva';
    }
  });

  cancelButton.addEventListener('click', async () => {
    const booking = state.booking;
    if (!booking || !booking.public_code) return;
    cancelButton.disabled = true;
    cancelButton.textContent = 'Cancelando…';
    showError(cancelError, '');
    try {
      const response = await fetch(
        endpoints.cancel.replace('CODE', encodeURIComponent(booking.public_code)),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ reason: 'Cancelada por el cliente desde la página pública' }),
        },
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(firstError(data, 'No pudimos cancelar la reserva.'));
      showConfirmation(data);
      showError(cancelError, 'Reserva cancelada correctamente.');
      cancelError.classList.add('is-success');
    } catch (error) {
      showError(cancelError, error.message);
    } finally {
      cancelButton.disabled = false;
      cancelButton.textContent = 'Cancelar reserva';
    }
  });

  rescheduleButton.addEventListener('click', () => {
    if (reschedulePanel.hidden) openReschedulePanel();
    else hideReschedulePanel();
  });

  rescheduleDate.addEventListener('change', loadRescheduleSlots);

  newBookingButton.addEventListener('click', () => {
    state.booking = null;
    state.slot = null;
    confirmationView.hidden = true;
    bookingView.hidden = false;
    updateSummary();
    loadAvailability();
    window.scrollTo({ top: 0, behavior: motion() });
  });

  branchSelect.addEventListener('change', () => {
    state.serviceId = null;
    state.slot = null;
    const branch = currentBranch();
    const today = todayIn(branch ? branch.timezone : undefined);
    dateInput.min = today;
    if (!dateInput.value || dateInput.value < today) dateInput.value = today;
    renderServices();
    renderWorkers();
    updateSummary();
    loadAvailability();
  });

  workerSelect.addEventListener('change', () => {
    state.slot = null;
    updateSummary();
    loadAvailability();
  });

  dateInput.addEventListener('change', () => {
    state.slot = null;
    updateSummary();
    loadAvailability();
  });

  if (!branches.length) {
    showError(loadError, 'Esta empresa todavía no tiene sucursales disponibles para reservar.');
    slotsStatus.textContent = 'Sin sucursales disponibles.';
  } else {
    branchSelect.value = branches[0].id;
    dateInput.min = todayIn(branches[0].timezone);
    dateInput.value = dateInput.min;
    const available = services.filter((service) => serviceFitsBranch(service, branches[0].id));
    if (available.length === 1) state.serviceId = available[0].id;
    renderServices();
    renderWorkers();
    updateSummary();
    loadAvailability();
  }

  const initialCode = String(root.dataset.initialCode || '').trim();
  if (initialCode) {
    const wantsReschedule = new URLSearchParams(window.location.search).get('reagendar') === '1';
    loadReservation(initialCode, wantsReschedule);
  }
})();
