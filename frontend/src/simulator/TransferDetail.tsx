import { ArrowRightIcon, ArrowUpRightIcon, CopySimpleIcon } from '@phosphor-icons/react';
import type { AuditEntry, Transfer } from '../lib/api';
import { MODE_LABELS, TONE_BORDER, TONE_DOT, TONE_TEXT, TRANSFER_STATUS_LABELS, TRANSFER_TONE, isTerminal } from '../lib/saga';
import { formatMoney, shortId } from '../lib/format';
import { Button, cx } from '../components/ui';
import SagaTimeline from './SagaTimeline';
import AuditLog from './AuditLog';

export default function TransferDetail({
  transfer,
  audit,
  onRetry,
  retrying,
  notice,
}: {
  transfer: Transfer;
  audit: AuditEntry[];
  onRetry: () => void;
  retrying: boolean;
  notice: string | null;
}) {
  const tone = TRANSFER_TONE[transfer.status];
  const finished = isTerminal(transfer.status);

  return (
    <div className="flex flex-col gap-4">
      <section className={cx('rounded-[16px] border bg-ink-850 hairline-top', TONE_BORDER[tone])}>
        <header className="flex flex-wrap items-start justify-between gap-5 border-b border-white/8 p-6">
          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <span className={cx('h-2 w-2 shrink-0 rounded-full', TONE_DOT[tone])} />
              <span className={cx('text-[15px] font-medium', TONE_TEXT[tone])}>
                {TRANSFER_STATUS_LABELS[transfer.status]}
              </span>
              <span className="rounded-full border border-white/10 px-2.5 py-0.5 font-mono text-[11px] text-fog-500">
                {MODE_LABELS[transfer.mode]}
              </span>
            </div>

            <div className="mt-4 flex flex-wrap items-baseline gap-3">
              <span className="font-mono text-[26px] tracking-[-0.02em] text-fog-100 tabular-nums">
                {formatMoney(transfer.amount_cents)}
              </span>
              <span className="flex items-center gap-2 font-mono text-[13px] text-fog-500">
                {transfer.source_account}
                <ArrowRightIcon size={12} weight="bold" className="text-fog-700" />
                {transfer.destination_account}
              </span>
            </div>

            {transfer.detail && <p className="mt-3 max-w-[62ch] text-[13.5px] leading-relaxed text-fog-500">{transfer.detail}</p>}
          </div>

          <div className="flex shrink-0 flex-col items-end gap-3">
            <span className="flex items-center gap-1.5 font-mono text-[11.5px] text-fog-700">
              <CopySimpleIcon size={12} />
              {shortId(transfer.transfer_id)}
            </span>
            {transfer.prefect.flow_run_url && (
              <a
                href={transfer.prefect.flow_run_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-[13px] text-fog-300 transition-colors hover:text-accent"
              >
                Ver en Prefect
                <ArrowUpRightIcon size={12} weight="bold" />
              </a>
            )}
          </div>
        </header>

        <div className="p-6">
          <SagaTimeline transfer={transfer} />
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-white/8 px-6 py-4">
          <p className="max-w-[46ch] text-[12.5px] leading-relaxed text-fog-700">
            CP-05: reenvía esta misma operación con su clave de idempotencia original. No debe cobrar dos veces.
          </p>
          <div className="flex items-center gap-3">
            {transfer.duplicate_requests > 0 && (
              <span className="font-mono text-[11.5px] text-warn">
                {transfer.duplicate_requests} reintento{transfer.duplicate_requests === 1 ? '' : 's'}
              </span>
            )}
            <Button size="sm" variant="surface" onClick={onRetry} disabled={retrying || !finished}>
              {retrying ? 'Reenviando…' : 'Reintentar con la misma clave'}
            </Button>
          </div>
        </footer>
      </section>

      {notice && (
        <p className="rounded-[10px] border border-warn/35 bg-warn/[0.07] px-4 py-3 text-[13.5px] text-warn">{notice}</p>
      )}

      <section className="rounded-[16px] border border-white/8 bg-ink-850 hairline-top">
        <header className="flex items-center justify-between border-b border-white/8 px-6 py-4">
          <h3 className="text-[14px] font-medium text-fog-100">Bitácora de auditoría</h3>
          <span className="font-mono text-[11.5px] text-fog-700">{audit.length} registros</span>
        </header>
        <AuditLog entries={audit} />
      </section>
    </div>
  );
}
