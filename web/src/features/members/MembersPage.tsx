import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { Member } from '../../api/members';
import { queryKeys } from '../../api/queryKeys';
import { membersApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/Dialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { PageHeader } from '../../components/ui/PageHeader';
import { Pagination } from '../../components/ui/Pagination';
import { Input } from '../../components/ui/Field';
import { CredentialsDialog } from './CredentialsDialog';
import { MemberFormDialog } from './MemberFormDialog';
import { PermissionsDialog } from './PermissionsDialog';
import { roleLabel } from './memberRoles';

export function MembersPage() {
  const { company, bootstrap, user } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Member | null>(null);
  const [removing, setRemoving] = useState<Member | null>(null);
  const [permissionsFor, setPermissionsFor] = useState<Member | null>(null);
  const [credentials, setCredentials] = useState<{ email: string; password: string } | null>(null);

  const params = { search: search.trim() || undefined, page };
  const membersQuery = useQuery({
    queryKey: queryKeys.members(company?.id ?? '', params),
    queryFn: () => membersApi.list(params),
    enabled: Boolean(company),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['members'] });
  };

  const deactivate = useMutation({
    mutationFn: (member: Member) => membersApi.remove(member.id),
    onSuccess: () => {
      invalidate();
      setRemoving(null);
    },
  });

  const activate = useMutation({
    mutationFn: (member: Member) => membersApi.update(member.id, { active: true }),
    onSuccess: invalidate,
  });

  const isOwner = bootstrap?.membership.role === 'owner';
  const canManage = (member: Member) =>
    isOwner || (member.role !== 'owner' && member.role !== 'admin');
  const rows = membersQuery.data?.results ?? [];

  return (
    <section>
      <PageHeader
        title="Usuarios"
        description="Crea accesos, asigna un local predeterminado y ajusta permisos."
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            Nuevo usuario
          </Button>
        }
      />

      <div className="mb-4 max-w-sm">
        <Input
          aria-label="Buscar"
          placeholder="Buscar por correo o nombre"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
        />
      </div>

      {membersQuery.error ? (
        <ErrorBanner message="No se pudieron cargar los usuarios." />
      ) : null}

      {!membersQuery.isLoading && rows.length === 0 ? (
        <EmptyState
          title="Todavía no hay usuarios."
          description="Crea el primero y entrega la clave temporal una sola vez."
        />
      ) : null}

      {rows.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-line bg-panel">
          <table className="min-w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3">Usuario</th>
                <th className="px-4 py-3">Rol</th>
                <th className="px-4 py-3">Local</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((member) => (
                <tr key={member.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-medium text-ink">
                      {[member.first_name, member.last_name].filter(Boolean).join(' ') || member.email}
                    </div>
                    <div className="text-xs text-muted">{member.email}</div>
                  </td>
                  <td className="px-4 py-3">{roleLabel(member.role)}</td>
                  <td className="px-4 py-3">{member.default_branch?.name ?? '—'}</td>
                  <td className="px-4 py-3">
                    <Badge tone={member.active ? 'active' : 'inactive'}>
                      {member.active ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      {canManage(member) ? (
                        <>
                          <Button
                            variant="secondary"
                            onClick={() => {
                              setEditing(member);
                              setFormOpen(true);
                            }}
                          >
                            Editar
                          </Button>
                          <Button variant="secondary" onClick={() => setPermissionsFor(member)}>
                            Permisos
                          </Button>
                          {member.active ? (
                            <Button
                              variant="danger"
                              disabled={member.user_id === user?.id}
                              onClick={() => setRemoving(member)}
                            >
                              Desactivar
                            </Button>
                          ) : (
                            <Button variant="secondary" onClick={() => activate.mutate(member)}>
                              Reactivar
                            </Button>
                          )}
                        </>
                      ) : (
                        <span className="text-xs text-muted">Solo el propietario</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <Pagination page={page} count={membersQuery.data?.count ?? 0} onPage={setPage} />

      <MemberFormDialog
        open={formOpen}
        member={editing}
        onOpenChange={(next) => {
          setFormOpen(next);
          if (!next) setEditing(null);
        }}
        onSaved={invalidate}
        onCreated={(email, password) => setCredentials({ email, password })}
      />

      <CredentialsDialog
        open={Boolean(credentials)}
        onOpenChange={(next) => {
          if (!next) setCredentials(null);
        }}
        email={credentials?.email ?? ''}
        password={credentials?.password ?? ''}
      />

      {permissionsFor ? (
        <PermissionsDialog
          open={Boolean(permissionsFor)}
          member={permissionsFor}
          onOpenChange={(next) => {
            if (!next) setPermissionsFor(null);
          }}
          onSaved={invalidate}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(removing)}
        onOpenChange={(next) => {
          if (!next) setRemoving(null);
        }}
        title="Desactivar usuario"
        description="El usuario perderá acceso a esta empresa, pero conservará sus datos."
        confirmLabel="Desactivar"
        danger
        loading={deactivate.isPending}
        onConfirm={() => {
          if (removing) deactivate.mutate(removing);
        }}
      />
    </section>
  );
}
