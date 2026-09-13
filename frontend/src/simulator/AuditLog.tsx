import { useEffect, useRef } from 'react';
import type { AuditEntry } from '../lib/api';
import { formatTime } from '../lib/format';
import { cx } from '../components/ui';

const CATEGORY_LABELS: Record<AuditEntry['category'], string> = {
  SOLICITUD: 'solicitud',
  DUPLICADO: 'duplicado',
  DESPACHO: 'despacho',
  PASO: 'paso',
  ESTADO: 'estado',
  EVENTO: 'evento',
};

const CATEGORY_TONE: Record<AuditEntry['category'], string> = {
  SOLICITUD: 'text-fog-500',
  DUPLICADO: 'text-warn',
  DESPACHO: 'text-fog-500',
  PASO: 'text-fog-500',
  ESTADO: 'text-accent',
  EVENTO: 'text-fog-300',
};

export default function AuditLog({ entries }: { entries: AuditEntry[] }) {
  const scroller = useRef<HTMLDivElement>(null);

  // La bitácora crece hacia abajo mientras la saga avanza: se sigue el último registro.
  useEffect(() => {
    const node = scroller.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [entries.length]);

  if (entries.length === 0) {
    return (
      <p className="px-6 py-8 text-[13.5px] text-fog-700">
        Aún no hay registros para esta transferencia.
      </p>
    );
  }

  return (
    <div ref={scroller} className="max-h-[320px] overflow-y-auto px-6 py-4">
      <ul className="space-y-2.5">
        {entries.map((entry) => (
          <li key={entry.id} className="grid grid-cols-[auto_auto_1fr] items-baseline gap-x-3 text-[13px]">
            <span className="font-mono text-[11.5px] text-fog-700">{formatTime(entry.at)}</span>
            <span className={cx('font-mono text-[11px]', CATEGORY_TONE[entry.category])}>
              {entry.event_type ?? CATEGORY_LABELS[entry.category]}
            </span>
            <span className="leading-relaxed text-fog-500">
              {entry.detail ?? entry.status ?? ''}
              <span className="ml-2 text-fog-700">{entry.source}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
