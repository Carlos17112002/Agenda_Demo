import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import type { Booking } from '../../api/agenda';
import { agendaApi, customersApi, servicesApi, teamApi } from '../../api/runtime';
import { ApiError } from '../../api/client';
import { queryKeys } from '../../api/queryKeys';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input, Select, Textarea } from '../../components/ui/Field';
import { Skeleton } from '../../components/ui/Skeleton';
import { isoToDateTimeLocal } from '../../lib/dates';
import { useDebouncedValue } from '../../lib/useDebouncedValue';
import type { CalendarSlot } from './agendaLayout';

const schema = z
  .object({
    branch: z.string().min(1, 'Selecciona una sucursal.'),
    service: z.string().min(1, 'Selecciona un servicio.'),
    worker: z.string().min(1, 'Selecciona un trabajador.'),
    date: z.string().min(1, 'Selecciona un día.'),
    notes: z.string().max(2000, 'Máximo 2000 caracteres.'),
    customerMode: z.enum(['existing', 'new']),
    customerId: z.string(),
    first_name: z.string(),
    last_name: z.string(),
    email: z.union([z.literal(''), z.string().email('Ingresa un correo válido.')]),
    phone: z.string(),
  })
  .superRefine((values, context) => {
    if (values.customerMode === 'existing' && !values.customerId) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['customerId'],
        message: 'Selecciona un cliente.',
      });
    }
    if (values.customerMode === 'new' && !values.first_name.trim()) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['first_name'],
        message: 'Ingresa el nombre del cliente.',
      });
    }
  });

type FormValues = z.infer<typeof schema>;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultBranchId: string;
  defaultDate: string;
  initialSlot?: CalendarSlot | null;
  onCreated: (booking: Booking) => void;
};

export function BookingCreateDialog({
  open,
  onOpenChange,
  defaultBranchId,
  defaultDate,
  initialSlot = null,
  onCreated,
}: Props) {
  const { company, bootstrap } = useAuth();
  const queryClient = useQueryClient();
  const companyId = company?.id ?? '';
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const [slot, setSlot] = useState<string | null>(null);
  const [customerSearch, setCustomerSearch] = useState('');
  const [banner, setBanner] = useState<string | null>(null);
  const [creatingCustomer, setCreatingCustomer] = useState(false);
  const search = useDebouncedValue(customerSearch, 300);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    setError,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      branch: defaultBranchId,
      service: '',
      worker: '',
      date: defaultDate,
      notes: '',
      customerMode: 'existing',
      customerId: '',
      first_name: '',
      last_name: '',
      email: '',
      phone: '',
    },
  });

  const branch = watch('branch');
  const service = watch('service');
  const worker = watch('worker');
  const date = watch('date');
  const customerMode = watch('customerMode');
  const timezone =
    branches.find((item) => item.id === branch)?.timezone ?? 'America/Santiago';

  useEffect(() => {
    if (!open) return;
    reset({
      branch: defaultBranchId,
      service: '',
      worker: initialSlot?.workerId ?? '',
      date: initialSlot?.date ?? defaultDate,
      notes: '',
      customerMode: 'existing',
      customerId: '',
      first_name: '',
      last_name: '',
      email: '',
      phone: '',
    });
    setSlot(null);
    setCustomerSearch('');
    setBanner(null);
  }, [defaultBranchId, defaultDate, initialSlot, open, reset]);

  useEffect(() => {
    setSlot(null);
  }, [branch, date, service, worker]);

  const servicesQuery = useQuery({
    queryKey: queryKeys.services(companyId, { active: true }),
    queryFn: () => servicesApi.list({ active: true, page: 1 }),
    enabled: open && Boolean(companyId && branch),
  });
  const workersQuery = useQuery({
    queryKey: queryKeys.workers(companyId, { branch, active: true }),
    queryFn: () => teamApi.workers.list({ branch, active: true, page: 1 }),
    enabled: open && Boolean(companyId && branch),
  });
  const customersQuery = useQuery({
    queryKey: queryKeys.customers(companyId, { search, active: true, page: 1 }),
    queryFn: () => customersApi.list({ search, active: true, page: 1 }),
    enabled: open && customerMode === 'existing' && Boolean(companyId),
  });
  const availabilityQuery = useQuery({
    queryKey: queryKeys.availability(companyId, { branch, service, worker, date }),
    queryFn: () => agendaApi.availability({ branch, service, worker, date }),
    enabled: open && Boolean(companyId && branch && service && worker && date),
  });

  useEffect(() => {
    if (!open || !initialSlot || !availabilityQuery.data) return;
    if (slot) return;
    if (date !== initialSlot.date) return;
    if (initialSlot.workerId && worker !== initialSlot.workerId) return;
    const wanted = `${initialSlot.date}T${initialSlot.time}`;
    const match = availabilityQuery.data.slots.find(
      (item) => isoToDateTimeLocal(item.start_at, timezone) === wanted,
    );
    setSlot(match ? match.start_at : null);
  }, [availabilityQuery.data, date, initialSlot, open, slot, timezone, worker]);

  // El select se registra antes de que lleguen las opciones; se reaplica al cargarlas.
  useEffect(() => {
    if (!open || !initialSlot?.workerId) return;
    if (worker !== initialSlot.workerId) return;
    if (!(workersQuery.data?.results ?? []).some((item) => item.id === initialSlot.workerId)) {
      return;
    }
    setValue('worker', initialSlot.workerId);
  }, [initialSlot, open, setValue, worker, workersQuery.data]);

  async function submit(values: FormValues) {
    setBanner(null);
    if (!slot) {
      setBanner('Selecciona un horario disponible.');
      return;
    }
    let customerId = values.customerId;
    try {
      if (values.customerMode === 'new') {
        setCreatingCustomer(true);
        const customer = await customersApi.create({
          first_name: values.first_name.trim(),
          last_name: values.last_name.trim(),
          email: values.email.trim(),
          phone: values.phone.trim(),
        });
        customerId = customer.id;
        setValue('customerMode', 'existing');
        setValue('customerId', customer.id);
      }
      const booking = await agendaApi.createBooking({
        branch: values.branch,
        customer: customerId,
        service: values.service,
        worker: values.worker,
        start_at: slot,
        notes: values.notes.trim(),
      });
      await queryClient.invalidateQueries({ queryKey: ['bookings', companyId] });
      await queryClient.invalidateQueries({ queryKey: ['availability', companyId] });
      onCreated(booking);
      onOpenChange(false);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setSlot(null);
        setBanner(error.message);
        void availabilityQuery.refetch();
        return;
      }
      if (error instanceof ApiError) {
        Object.entries(error.fields ?? {}).forEach(([field, messages]) => {
          if (field in values) {
            setError(field as keyof FormValues, { message: messages[0] });
          }
        });
        setBanner(error.message);
      } else {
        setBanner('No se pudo crear la reserva.');
      }
    } finally {
      setCreatingCustomer(false);
    }
  }

  const busy = isSubmitting || creatingCustomer;

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Nueva reserva"
      description="Solo se ofrecen cupos libres según horarios, pausas, ausencias y buffers."
      wide
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" form="booking-create-form" loading={busy} loadingLabel="Creando…">
            Crear reserva
          </Button>
        </>
      }
    >
      <form id="booking-create-form" className="space-y-4" onSubmit={handleSubmit(submit)} noValidate>
        {banner ? <ErrorBanner message={banner} /> : null}
        {servicesQuery.isError || workersQuery.isError ? (
          <ErrorBanner
            message="No se pudieron cargar los servicios o trabajadores."
            onRetry={() => {
              void servicesQuery.refetch();
              void workersQuery.refetch();
            }}
          />
        ) : null}
        {customersQuery.isError ? (
          <ErrorBanner
            message="No se pudieron cargar los clientes."
            onRetry={() => void customersQuery.refetch()}
          />
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Sucursal" htmlFor="booking-branch" error={errors.branch?.message}>
            <Select id="booking-branch" {...register('branch')}>
              {branches.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Día" htmlFor="booking-date" error={errors.date?.message}>
            <Input id="booking-date" type="date" {...register('date')} />
          </Field>

          <Field label="Servicio" htmlFor="booking-service" error={errors.service?.message}>
            <Select id="booking-service" {...register('service')}>
              <option value="">Selecciona un servicio</option>
              {(servicesQuery.data?.results ?? [])
                .filter(
                  (item) => item.branches.length === 0 || item.branches.includes(branch),
                )
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.duration_minutes} min
                  </option>
                ))}
            </Select>
          </Field>

          <Field label="Trabajador" htmlFor="booking-worker" error={errors.worker?.message}>
            <Select id="booking-worker" {...register('worker')}>
              <option value="">Selecciona un trabajador</option>
              {(workersQuery.data?.results ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.display_name}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-ink">Horario disponible</legend>
          {initialSlot ? (
            <p className="mb-2 text-xs text-muted">
              Horario solicitado desde la agenda: {initialSlot.date} a las {initialSlot.time}.
              Se marca automáticamente si sigue disponible para el servicio elegido.
            </p>
          ) : null}
          {!branch || !service || !worker || !date ? (
            <p className="text-sm text-muted">Elige sucursal, servicio, trabajador y día.</p>
          ) : availabilityQuery.isLoading ? (
            <Skeleton rows={2} />
          ) : availabilityQuery.isError ? (
            <ErrorBanner
              message={
                availabilityQuery.error instanceof Error
                  ? availabilityQuery.error.message
                  : 'No se pudo consultar la disponibilidad.'
              }
              onRetry={() => void availabilityQuery.refetch()}
            />
          ) : (availabilityQuery.data?.slots.length ?? 0) === 0 ? (
            <p className="text-sm text-muted">No hay cupos disponibles para ese día.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {availabilityQuery.data?.slots.map((item) => (
                <button
                  key={item.start_at}
                  type="button"
                  aria-pressed={slot === item.start_at}
                  onClick={() => setSlot(item.start_at)}
                  className={`rounded-md border px-3 py-1.5 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand ${
                    slot === item.start_at
                      ? 'border-brand bg-brand-soft text-brand'
                      : 'border-line bg-panel text-ink hover:bg-surface'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="mb-2 text-sm font-medium text-ink">Cliente</legend>
          <div className="flex gap-2">
            <Button
              type="button"
              variant={customerMode === 'existing' ? 'primary' : 'secondary'}
              onClick={() => setValue('customerMode', 'existing')}
            >
              Cliente existente
            </Button>
            <Button
              type="button"
              variant={customerMode === 'new' ? 'primary' : 'secondary'}
              onClick={() => setValue('customerMode', 'new')}
            >
              Nuevo cliente
            </Button>
          </div>

          {customerMode === 'existing' ? (
            <div key="existing" className="space-y-3">
              <Field label="Buscar cliente" htmlFor="booking-customer-search">
                <Input
                  id="booking-customer-search"
                  value={customerSearch}
                  onChange={(event) => setCustomerSearch(event.target.value)}
                  placeholder="Nombre, correo, teléfono o documento"
                />
              </Field>
              <Field label="Cliente" htmlFor="booking-customer" error={errors.customerId?.message}>
                <Select id="booking-customer" {...register('customerId')}>
                  <option value="">Selecciona un cliente</option>
                  {(customersQuery.data?.results ?? []).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.display_name}
                      {item.email ? ` · ${item.email}` : ''}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
          ) : (
            <div key="new" className="grid gap-4 sm:grid-cols-2">
              <Field label="Nombre" htmlFor="booking-first-name" error={errors.first_name?.message}>
                <Input id="booking-first-name" {...register('first_name')} />
              </Field>
              <Field label="Apellido" htmlFor="booking-last-name">
                <Input id="booking-last-name" {...register('last_name')} />
              </Field>
              <Field label="Correo del cliente" htmlFor="booking-email" error={errors.email?.message}>
                <Input id="booking-email" type="email" {...register('email')} />
              </Field>
              <Field label="Teléfono" htmlFor="booking-phone">
                <Input id="booking-phone" {...register('phone')} />
              </Field>
            </div>
          )}
        </fieldset>

        <Field label="Notas" htmlFor="booking-notes" error={errors.notes?.message}>
          <Textarea id="booking-notes" rows={2} {...register('notes')} />
        </Field>
      </form>
    </Dialog>
  );
}
