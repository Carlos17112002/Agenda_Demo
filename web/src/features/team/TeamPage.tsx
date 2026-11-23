import { useState } from 'react';

import { PageHeader } from '../../components/ui/PageHeader';
import { BlockedSlotsSection, TimeOffSection } from './ExceptionsSection';
import { ScheduleSection } from './ScheduleSection';
import { WorkersSection } from './WorkersSection';

type TeamTab = 'workers' | 'schedule' | 'timeoff' | 'blocked';

const TABS: { id: TeamTab; label: string }[] = [
  { id: 'workers', label: 'Trabajadores' },
  { id: 'schedule', label: 'Horario' },
  { id: 'timeoff', label: 'Ausencias' },
  { id: 'blocked', label: 'Bloqueos' },
];

export function TeamPage() {
  const [tab, setTab] = useState<TeamTab>('workers');
  const [workerId, setWorkerId] = useState('');

  return (
    <section>
      <PageHeader
        title="Equipo"
        description="Trabajadores, sucursales, turnos semanales y pausas."
      />

      <div role="tablist" aria-label="Secciones de equipo" className="mb-4 flex gap-1 border-b border-line">
        {TABS.map((item) => (
          <button
            key={item.id}
            role="tab"
            type="button"
            id={`team-tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls={`team-panel-${item.id}`}
            onClick={() => setTab(item.id)}
            className={`px-4 py-2 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
              tab === item.id
                ? 'border-b-2 border-brand text-ink'
                : 'text-muted hover:text-ink'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id="team-panel-workers" aria-labelledby="team-tab-workers" hidden={tab !== 'workers'}>
        <WorkersSection
          onManageSchedule={(worker) => {
            setWorkerId(worker.id);
            setTab('schedule');
          }}
        />
      </div>
      <div role="tabpanel" id="team-panel-schedule" aria-labelledby="team-tab-schedule" hidden={tab !== 'schedule'}>
        {tab === 'schedule' ? (
          <ScheduleSection workerId={workerId} onWorkerChange={setWorkerId} />
        ) : null}
      </div>
      <div role="tabpanel" id="team-panel-timeoff" aria-labelledby="team-tab-timeoff" hidden={tab !== 'timeoff'}>
        {tab === 'timeoff' ? (
          <TimeOffSection workerId={workerId} onWorkerChange={setWorkerId} />
        ) : null}
      </div>
      <div role="tabpanel" id="team-panel-blocked" aria-labelledby="team-tab-blocked" hidden={tab !== 'blocked'}>
        {tab === 'blocked' ? (
          <BlockedSlotsSection workerId={workerId} onWorkerChange={setWorkerId} />
        ) : null}
      </div>
    </section>
  );
}
