import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { Member } from '../../api/members';
import { queryKeys } from '../../api/queryKeys';
import { membersApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Select } from '../../components/ui/Field';
import { permissionGroup, permissionLabel } from './permissionLabels';

type Effect = 'inherit' | 'allow' | 'deny';
type Row = { effect: Effect; branch: string };

export function PermissionsDialog({
  open,
  member,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  member: Member;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const { company, bootstrap } = useAuth();
  const queryClient = useQueryClient();
  const catalog = bootstrap?.permission_catalog ?? [];
  const defaults = new Set(bootstrap?.role_defaults?.[member.role] ?? []);
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);

  const grantsQuery = useQuery({
    queryKey: queryKeys.memberGrants(company?.id ?? '', member.id),
    queryFn: () => membersApi.grants.list({ membership: member.id, page: 1 }),
    enabled: open,
  });

  if (grantsQuery.isLoading || !grantsQuery.data) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange} title="Permisos" wide>
        <p className="text-sm text-muted">Cargando permisos…</p>
      </Dialog>
    );
  }

  return (
    <PermissionMatrix
      key={`${member.id}:${grantsQuery.data.results.map((grant) => grant.id).join(',')}`}
      open={open}
      onOpenChange={onOpenChange}
      onSaved={onSaved}
      member={member}
      catalog={catalog}
      branches={branches}
      defaults={defaults}
      grants={grantsQuery.data.results}
      onInvalidate={() =>
        queryClient.invalidateQueries({
          queryKey: queryKeys.memberGrants(company?.id ?? '', member.id),
        })
      }
    />
  );
}

function PermissionMatrix({
  open,
  onOpenChange,
  onSaved,
  member,
  catalog,
  branches,
  defaults,
  grants,
  onInvalidate,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
  member: Member;
  catalog: string[];
  branches: { id: string; name: string }[];
  defaults: Set<string>;
  grants: { id: string; permission: string; effect: 'allow' | 'deny'; branch: string | null }[];
  onInvalidate: () => void;
}) {
  const [rows, setRows] = useState<Record<string, Row>>(() => {
    const initial: Record<string, Row> = {};
    for (const permission of catalog) {
      const grant = grants.find((item) => item.permission === permission);
      initial[permission] = grant
        ? { effect: grant.effect, branch: grant.branch ?? '' }
        : { effect: 'inherit', branch: '' };
    }
    return initial;
  });

  const mutation = useMutation({
    mutationFn: async () => {
      for (const permission of catalog) {
        const row = rows[permission] ?? { effect: 'inherit' as Effect, branch: '' };
        const current = grants.filter((grant) => grant.permission === permission);
        const signature =
          current.length === 0
            ? 'inherit'
            : current.length === 1
              ? `${current[0].effect}:${current[0].branch ?? ''}`
              : 'multi';
        const desired = row.effect === 'inherit' ? 'inherit' : `${row.effect}:${row.branch}`;
        if (signature === desired) continue;
        for (const grant of current) {
          await membersApi.grants.remove(grant.id);
        }
        if (row.effect !== 'inherit') {
          await membersApi.grants.create({
            membership: member.id,
            permission,
            effect: row.effect,
            branch: row.branch || null,
          });
        }
      }
    },
    onSuccess: () => {
      onInvalidate();
      onSaved();
      onOpenChange(false);
    },
  });

  const groups = Array.from(new Set(catalog.map(permissionGroup)));

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Permisos de ${member.first_name || member.email}`}
      description="Lo heredado usa los permisos del rol. Permitir o denegar lo reemplaza en toda la empresa o en un local."
      wide
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            loading={mutation.isPending}
            loadingLabel="Guardando…"
          >
            Guardar permisos
          </Button>
        </>
      }
    >
      {mutation.error ? <ErrorBanner message="No se pudieron guardar los permisos." /> : null}
      <div className="space-y-5">
        {groups.map((group) => (
          <section key={group}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
              {group}
            </h3>
            <div className="space-y-2">
              {catalog
                .filter((permission) => permissionGroup(permission) === group)
                .map((permission) => {
                  const row = rows[permission];
                  return (
                    <div
                      key={permission}
                      className="grid items-center gap-2 sm:grid-cols-[1fr_150px_170px]"
                    >
                      <div className="text-sm text-ink">
                        {permissionLabel(permission)}
                        <span className="ml-2 text-xs text-muted">
                          {defaults.has(permission) ? 'Rol: permitido' : 'Rol: sin acceso'}
                        </span>
                      </div>
                      <Select
                        aria-label={`Efecto para ${permissionLabel(permission)}`}
                        value={row.effect}
                        onChange={(event) =>
                          setRows((current) => ({
                            ...current,
                            [permission]: { ...row, effect: event.target.value as Effect },
                          }))
                        }
                      >
                        <option value="inherit">Heredado</option>
                        <option value="allow">Permitir</option>
                        <option value="deny">Denegar</option>
                      </Select>
                      <Select
                        aria-label={`Alcance para ${permissionLabel(permission)}`}
                        value={row.branch}
                        disabled={row.effect === 'inherit'}
                        onChange={(event) =>
                          setRows((current) => ({
                            ...current,
                            [permission]: { ...row, branch: event.target.value },
                          }))
                        }
                      >
                        <option value="">Toda la empresa</option>
                        {branches.map((branch) => (
                          <option key={branch.id} value={branch.id}>
                            {branch.name}
                          </option>
                        ))}
                      </Select>
                    </div>
                  );
                })}
            </div>
          </section>
        ))}
      </div>
    </Dialog>
  );
}
