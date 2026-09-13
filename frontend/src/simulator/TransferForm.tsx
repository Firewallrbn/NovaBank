import { useId, useState } from 'react';
import { LightningIcon, ShieldWarningIcon, WifiSlashIcon } from '@phosphor-icons/react';
import type { Account, SagaMode, TransferRequest } from '../lib/api';
import { MODE_LABELS } from '../lib/saga';
import { Button, cx } from '../components/ui';

export type FormState = {
  source_account: string;
  destination_account: string;
  amount: string;
  mode: SagaMode;
  force_fraud: boolean;
  clearing_timeout: boolean;
  delay_seconds: number;
};

export const INITIAL_FORM: FormState = {
  source_account: 'ACC-001',
  destination_account: 'ACC-002',
  amount: '100000',
  mode: 'orchestration',
  force_fraud: false,
  clearing_timeout: false,
  delay_seconds: 2.5,
};

/** Presets de la matriz de casos. CP-05 no es un preset: se dispara reenviando
 *  una transferencia ya creada con su misma clave de idempotencia. */
const PRESETS: { code: string; hint: string; patch: Partial<FormState> }[] = [
  {
    code: 'CP-01',
    hint: 'Camino feliz',
    patch: { source_account: 'ACC-001', destination_account: 'ACC-002', amount: '100000', force_fraud: false, clearing_timeout: false },
  },
  {
    code: 'CP-02',
    hint: 'Fondos insuficientes',
    patch: { source_account: 'ACC-003', destination_account: 'ACC-001', amount: '80000', force_fraud: false, clearing_timeout: false },
  },
  {
    code: 'CP-03',
    hint: 'Fraude',
    patch: { source_account: 'ACC-001', destination_account: 'ACC-002', amount: '100000', force_fraud: true, clearing_timeout: false },
  },
  {
    code: 'CP-04',
    hint: 'Caída de red',
    patch: { source_account: 'ACC-001', destination_account: 'ACC-002', amount: '100000', force_fraud: false, clearing_timeout: true },
  },
];

function Switch({
  checked,
  onChange,
  label,
  description,
  icon,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <label
      className={cx(
        'flex cursor-pointer items-start gap-3 rounded-[10px] border p-3.5 transition-colors duration-200',
        checked ? 'border-warn/45 bg-warn/[0.06]' : 'border-white/8 bg-ink-800 hover:border-white/15',
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="peer sr-only"
      />
      <span className={cx('mt-0.5 shrink-0 transition-colors', checked ? 'text-warn' : 'text-fog-700')}>{icon}</span>
      <span className="min-w-0 flex-1">
        <span className={cx('block text-[14px] font-medium', checked ? 'text-fog-100' : 'text-fog-300')}>{label}</span>
        <span className="mt-0.5 block text-[12.5px] leading-snug text-fog-500">{description}</span>
      </span>
      <span
        aria-hidden="true"
        className={cx(
          'mt-0.5 h-[18px] w-8 shrink-0 rounded-full p-[2px] transition-colors duration-200',
          checked ? 'bg-warn' : 'bg-ink-500',
        )}
      >
        <span
          className={cx(
            'block h-[14px] w-[14px] rounded-full bg-ink-900 transition-transform duration-200',
            checked && 'translate-x-[14px]',
          )}
        />
      </span>
    </label>
  );
}

const FIELD =
  'h-11 w-full rounded-[10px] border border-white/10 bg-ink-800 px-3 text-[14.5px] text-fog-100 ' +
  'transition-colors duration-200 hover:border-white/20 focus:border-accent/60 focus:outline-none';

export default function TransferForm({
  accounts,
  submitting,
  error,
  onSubmit,
}: {
  accounts: Account[];
  submitting: boolean;
  error: string | null;
  onSubmit: (request: TransferRequest) => void;
}) {
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const amountId = useId();
  const sourceId = useId();
  const destinationId = useId();

  const patch = (values: Partial<FormState>) => setForm((current) => ({ ...current, ...values }));

  const amount = Number(form.amount);
  const sameAccount = form.source_account === form.destination_account;
  const amountInvalid = !Number.isFinite(amount) || amount <= 0;
  const localError = sameAccount
    ? 'La cuenta origen y la destino deben ser distintas.'
    : amountInvalid
      ? 'Escriba un importe mayor que cero.'
      : null;

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (localError) return;
    onSubmit({
      source_account: form.source_account,
      destination_account: form.destination_account,
      amount,
      mode: form.mode,
      chaos: { force_fraud: form.force_fraud, clearing_timeout: form.clearing_timeout },
      delay_seconds: form.delay_seconds,
    });
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-6">
      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((preset) => (
          <button
            key={preset.code}
            type="button"
            onClick={() => patch(preset.patch)}
            title={preset.hint}
            className="rounded-full border border-white/10 bg-ink-800 px-3 py-1.5 font-mono text-[11.5px] text-fog-300 transition-colors duration-200 hover:border-accent/40 hover:text-accent"
          >
            {preset.code}
          </button>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-2">
          <label htmlFor={sourceId} className="text-[13px] font-medium text-fog-300">
            Cuenta origen
          </label>
          <select
            id={sourceId}
            className={FIELD}
            value={form.source_account}
            onChange={(event) => patch({ source_account: event.target.value })}
          >
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.id} · {account.owner}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-2">
          <label htmlFor={destinationId} className="text-[13px] font-medium text-fog-300">
            Cuenta destino
          </label>
          <select
            id={destinationId}
            className={FIELD}
            value={form.destination_account}
            onChange={(event) => patch({ destination_account: event.target.value })}
          >
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.id} · {account.owner}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid gap-2">
        <label htmlFor={amountId} className="text-[13px] font-medium text-fog-300">
          Importe
        </label>
        <div className="relative">
          <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 font-mono text-[14px] text-fog-700">
            $
          </span>
          <input
            id={amountId}
            inputMode="decimal"
            className={cx(FIELD, 'pl-7 font-mono')}
            value={form.amount}
            onChange={(event) => patch({ amount: event.target.value.replace(/[^\d.]/g, '') })}
          />
        </div>
      </div>

      <div className="grid gap-2">
        <span className="text-[13px] font-medium text-fog-300">Modalidad de la saga</span>
        <div className="grid grid-cols-2 gap-1 rounded-[10px] border border-white/10 bg-ink-800 p-1">
          {(['orchestration', 'choreography'] as SagaMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => patch({ mode })}
              className={cx(
                'h-9 rounded-[7px] text-[13.5px] font-medium transition-colors duration-200',
                form.mode === mode ? 'bg-accent text-ink-900' : 'text-fog-500 hover:text-fog-100',
              )}
            >
              {MODE_LABELS[mode]}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-2.5">
        <span className="text-[13px] font-medium text-fog-300">Simulador de caos</span>
        <Switch
          checked={form.force_fraud}
          onChange={(value) => patch({ force_fraud: value })}
          label="Forzar alerta de fraude"
          description="El servicio de riesgo rechaza la operación en el paso 2."
          icon={<ShieldWarningIcon size={17} weight="bold" />}
        />
        <Switch
          checked={form.clearing_timeout}
          onChange={(value) => patch({ clearing_timeout: value })}
          label="Timeout de la red interbancaria"
          description="La pasarela no responde en el paso 3, el pivote de la saga."
          icon={<WifiSlashIcon size={17} weight="bold" />}
        />
      </div>

      <div className="grid gap-2">
        <div className="flex items-baseline justify-between">
          <label htmlFor="delay" className="text-[13px] font-medium text-fog-300">
            Pausa por paso
          </label>
          <span className="font-mono text-[13px] text-accent">{form.delay_seconds.toFixed(1)} s</span>
        </div>
        <input
          id="delay"
          type="range"
          min={2}
          max={4}
          step={0.5}
          value={form.delay_seconds}
          onChange={(event) => patch({ delay_seconds: Number(event.target.value) })}
          className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-ink-600 accent-[var(--color-accent)]"
        />
      </div>

      {(localError || error) && (
        <p role="alert" className="rounded-[10px] border border-danger/35 bg-danger/[0.07] px-3.5 py-2.5 text-[13.5px] text-danger">
          {localError ?? error}
        </p>
      )}

      <Button type="submit" variant="accent" disabled={submitting || Boolean(localError)}>
        <LightningIcon size={16} weight="fill" />
        {submitting ? 'Enviando…' : 'Ejecutar transferencia'}
      </Button>
    </form>
  );
}
