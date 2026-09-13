import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeftIcon, ArrowUpRightIcon, ArrowsClockwiseIcon } from '@phosphor-icons/react';
import {
  ApiError,
  createTransfer,
  getAudit,
  getConfig,
  issueIdempotencyKey,
  resetAll,
  type Transfer,
  type TransferRequest,
} from '../lib/api';
import { useSagaFeed } from '../lib/useSagaFeed';
import { MODE_LABELS, TONE_DOT, TONE_TEXT, TRANSFER_STATUS_LABELS, TRANSFER_TONE } from '../lib/saga';
import { formatMoney, shortId } from '../lib/format';
import { BrandMark, Wordmark } from '../components/brand';
import { Button, cx } from '../components/ui';
import TransferForm from '../simulator/TransferForm';
import AccountsPanel from '../simulator/AccountsPanel';
import TransferDetail from '../simulator/TransferDetail';

function Card({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-[16px] border border-white/8 bg-ink-850 hairline-top">
      <header className="flex items-center justify-between gap-3 border-b border-white/8 px-6 py-4">
        <h2 className="text-[14px] font-medium text-fog-100">{title}</h2>
        {action}
      </header>
      <div className="px-6 py-5">{children}</div>
    </section>
  );
}

export default function Simulator() {
  const feed = useSagaFeed();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [consoles, setConsoles] = useState({ prefect: '', rabbitmq: '' });

  useEffect(() => {
    getConfig()
      .then((config) => setConsoles({ prefect: config.prefect_ui_url, rabbitmq: config.rabbitmq_ui_url }))
      .catch(() => undefined);
  }, []);

  const selected = useMemo(
    () => feed.transfers.find((transfer) => transfer.transfer_id === selectedId) ?? feed.transfers[0] ?? null,
    [feed.transfers, selectedId],
  );

  // La bitácora completa solo viaja por SSE desde que uno se suscribe, así que al
  // abrir una transferencia antigua se rellena con lo que ya guardó el gateway.
  useEffect(() => {
    if (!selected || feed.audit[selected.transfer_id]) return;
    let alive = true;
    getAudit(selected.transfer_id)
      .then((entries) => alive && feed.mergeAudit(selected.transfer_id, entries))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [selected, feed]);

  const submit = useCallback(
    async (request: TransferRequest) => {
      setSubmitting(true);
      setFormError(null);
      setNotice(null);
      try {
        // El gateway emite el UUID de idempotencia; el frontend nunca lo inventa.
        const { idempotency_key } = await issueIdempotencyKey();
        const response = await createTransfer(request, idempotency_key);
        feed.upsertTransfer(response.transfer);
        setSelectedId(response.transfer.transfer_id);
      } catch (exc) {
        setFormError(exc instanceof ApiError ? exc.message : 'No se pudo crear la transferencia');
      } finally {
        setSubmitting(false);
      }
    },
    [feed],
  );

  const retry = useCallback(
    async (transfer: Transfer) => {
      setRetrying(true);
      setNotice(null);
      try {
        const response = await createTransfer(
          {
            source_account: transfer.source_account,
            destination_account: transfer.destination_account,
            amount: transfer.amount_cents / 100,
            mode: transfer.mode,
            chaos: transfer.chaos,
            delay_seconds: transfer.delay_seconds,
          },
          transfer.transfer_id,
        );
        feed.upsertTransfer(response.transfer);
        void feed.refreshAccounts();
        setNotice(
          response.duplicate
            ? 'Duplicado reconocido: se devolvió la operación original y no se ejecutó un nuevo cobro.'
            : 'El gateway trató la petición como nueva.',
        );
      } catch (exc) {
        setNotice(exc instanceof ApiError ? exc.message : 'No se pudo reenviar la operación');
      } finally {
        setRetrying(false);
      }
    },
    [feed],
  );

  const reset = useCallback(async () => {
    setResetting(true);
    setNotice(null);
    try {
      await resetAll();
      setSelectedId(null);
      await Promise.all([feed.refreshTransfers(), feed.refreshAccounts()]);
    } catch (exc) {
      setNotice(exc instanceof ApiError ? exc.message : 'No se pudo reiniciar');
    } finally {
      setResetting(false);
    }
  }, [feed]);

  return (
    <div className="min-h-[100dvh] bg-ink-900">
      <header className="sticky top-0 z-40 border-b border-white/5 bg-ink-900/80 backdrop-blur-xl">
        <div className="shell flex h-[68px] items-center justify-between gap-4">
          <div className="flex items-center gap-5">
            <Link to="/" className="flex items-center gap-2.5">
              <BrandMark className="h-6 w-6" />
              <Wordmark className="text-[16px]" />
            </Link>
            <Link
              to="/"
              className="hidden items-center gap-1.5 text-[13.5px] text-fog-500 transition-colors hover:text-fog-100 sm:inline-flex"
            >
              <ArrowLeftIcon size={13} weight="bold" />
              Inicio
            </Link>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-2 md:flex">
              <span className={cx('h-1.5 w-1.5 rounded-full', feed.connected ? 'bg-accent' : 'bg-danger')} />
              <span className="font-mono text-[11.5px] text-fog-700">
                {feed.connected ? 'en vivo' : 'sin conexión'}
              </span>
            </span>
            {consoles.prefect && (
              <a
                href={consoles.prefect}
                target="_blank"
                rel="noreferrer"
                className="hidden items-center gap-1.5 text-[13.5px] text-fog-500 transition-colors hover:text-fog-100 lg:inline-flex"
              >
                Prefect
                <ArrowUpRightIcon size={12} weight="bold" />
              </a>
            )}
            {consoles.rabbitmq && (
              <a
                href={consoles.rabbitmq}
                target="_blank"
                rel="noreferrer"
                className="hidden items-center gap-1.5 text-[13.5px] text-fog-500 transition-colors hover:text-fog-100 lg:inline-flex"
              >
                RabbitMQ
                <ArrowUpRightIcon size={12} weight="bold" />
              </a>
            )}
            <Button size="sm" variant="surface" onClick={reset} disabled={resetting}>
              <ArrowsClockwiseIcon size={14} weight="bold" />
              {resetting ? 'Reiniciando…' : 'Reiniciar'}
            </Button>
          </div>
        </div>
      </header>

      <main className="shell grid items-start gap-5 py-8 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <div className="flex flex-col gap-5">
          <Card title="Nueva transferencia">
            <TransferForm accounts={feed.accounts} submitting={submitting} error={formError} onSubmit={submit} />
          </Card>

          <Card title="Saldos">
            <AccountsPanel accounts={feed.accounts} />
          </Card>
        </div>

        <div className="flex flex-col gap-5">
          {feed.error && (
            <p className="rounded-[16px] border border-danger/35 bg-danger/[0.07] px-6 py-4 text-[13.5px] text-danger">
              {feed.error}. Compruebe que el stack esté levantado con docker compose up.
            </p>
          )}

          {selected ? (
            <TransferDetail
              transfer={selected}
              audit={feed.audit[selected.transfer_id] ?? []}
              onRetry={() => retry(selected)}
              retrying={retrying}
              notice={notice}
            />
          ) : (
            <section className="rounded-[16px] border border-white/8 bg-ink-850 px-8 py-16 text-center hairline-top">
              <h2 className="text-[19px] font-medium text-fog-100">
                {feed.loading ? 'Cargando el historial…' : 'Ninguna transferencia todavía'}
              </h2>
              <p className="mx-auto mt-3 max-w-[46ch] text-[14.5px] leading-relaxed text-fog-500">
                Elija un caso de la matriz o arme una transferencia a mano. El avance de cada paso y sus compensaciones
                aparecen aquí en vivo.
              </p>
            </section>
          )}

          {feed.transfers.length > 0 && (
            <Card title="Historial">
              <ul className="divide-y divide-white/5">
                {feed.transfers.slice(0, 12).map((transfer) => {
                  const tone = TRANSFER_TONE[transfer.status];
                  const active = selected?.transfer_id === transfer.transfer_id;
                  return (
                    <li key={transfer.transfer_id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(transfer.transfer_id)}
                        className={cx(
                          'flex w-full items-center gap-4 py-3 text-left transition-colors duration-200',
                          active ? 'text-fog-100' : 'text-fog-500 hover:text-fog-300',
                        )}
                      >
                        <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', TONE_DOT[tone])} />
                        <span className="font-mono text-[12px] text-fog-700">{shortId(transfer.transfer_id)}</span>
                        <span className="font-mono text-[13px] tabular-nums">{formatMoney(transfer.amount_cents)}</span>
                        <span className="hidden font-mono text-[12px] text-fog-700 sm:inline">
                          {transfer.source_account} → {transfer.destination_account}
                        </span>
                        <span className="ml-auto hidden font-mono text-[11.5px] text-fog-700 md:inline">
                          {MODE_LABELS[transfer.mode]}
                        </span>
                        <span className={cx('font-mono text-[11.5px] whitespace-nowrap', TONE_TEXT[tone])}>
                          {TRANSFER_STATUS_LABELS[transfer.status]}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}
