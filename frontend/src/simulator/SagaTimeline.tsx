import { motion, useReducedMotion } from 'motion/react';
import { ArrowUUpLeftIcon, CheckIcon, MinusIcon, XIcon } from '@phosphor-icons/react';
import type { StepStatus, Transfer } from '../lib/api';
import { COMPENSATION_LABELS, STEP_LABELS, STEP_SERVICE, STEP_STATUS_LABELS, STEP_TONE, TONE_TEXT } from '../lib/saga';
import { formatTime } from '../lib/format';
import { cx } from '../components/ui';

function StepIcon({ status }: { status: StepStatus }) {
  const reduce = useReducedMotion();
  const tone = STEP_TONE[status];

  if (status === 'RUNNING' || status === 'COMPENSATING') {
    const color = status === 'RUNNING' ? 'border-accent' : 'border-warn';
    return (
      <span className="relative flex h-6 w-6 items-center justify-center">
        {/* Anillo pulsante: señala el paso que está ocurriendo ahora mismo. */}
        {!reduce && (
          <motion.span
            className={cx('absolute inset-0 rounded-full border', color)}
            animate={{ scale: [1, 1.45], opacity: [0.65, 0] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }}
          />
        )}
        <span className={cx('h-2.5 w-2.5 rounded-full', status === 'RUNNING' ? 'bg-accent' : 'bg-warn')} />
      </span>
    );
  }

  const icon =
    status === 'SUCCEEDED' ? (
      <CheckIcon size={13} weight="bold" />
    ) : status === 'FAILED' ? (
      <XIcon size={13} weight="bold" />
    ) : status === 'COMPENSATED' ? (
      <ArrowUUpLeftIcon size={13} weight="bold" />
    ) : (
      <MinusIcon size={13} weight="bold" />
    );

  const ring =
    tone === 'ok'
      ? 'border-accent/50 text-accent'
      : tone === 'fail'
        ? 'border-danger/50 text-danger'
        : tone === 'undo'
          ? 'border-warn/50 text-warn'
          : 'border-white/10 text-fog-700';

  return <span className={cx('flex h-6 w-6 items-center justify-center rounded-full border', ring)}>{icon}</span>;
}

export default function SagaTimeline({ transfer }: { transfer: Transfer }) {
  // Los pasos se listan en su orden de ida, pero las compensaciones ocurren al
  // revés: se numeran por hora para que ese orden inverso quede a la vista.
  const compensationOrder = new Map(
    transfer.steps
      .filter((step) => step.status === 'COMPENSATED' || step.status === 'COMPENSATING')
      .sort((a, b) => a.updated_at.localeCompare(b.updated_at))
      .map((step, index) => [step.step, index + 1]),
  );

  return (
    <ol className="relative">
      {transfer.steps.map((step, index) => {
        const compensated = step.status === 'COMPENSATED' || step.status === 'COMPENSATING';
        const tone = STEP_TONE[step.status];
        const last = index === transfer.steps.length - 1;

        return (
          <li key={step.step} className="relative flex gap-4 pb-6 last:pb-0">
            {!last && (
              <span
                aria-hidden="true"
                className={cx(
                  'absolute top-7 bottom-1 left-[11.5px] w-px',
                  tone === 'idle' ? 'bg-white/8' : 'bg-white/15',
                )}
              />
            )}
            <span className="relative z-10 mt-0.5 shrink-0">
              <StepIcon status={step.status} />
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h4
                  className={cx(
                    'text-[15px] font-medium',
                    step.status === 'PENDING' || step.status === 'SKIPPED' ? 'text-fog-700' : 'text-fog-100',
                  )}
                >
                  {compensated ? (COMPENSATION_LABELS[step.step] ?? STEP_LABELS[step.step]) : STEP_LABELS[step.step]}
                </h4>
                <span className={cx('font-mono text-[11.5px]', TONE_TEXT[tone])}>
                  {STEP_STATUS_LABELS[step.status]}
                </span>
                {compensationOrder.has(step.step) && (
                  <span className="rounded-full border border-warn/35 px-2 py-0.5 font-mono text-[10.5px] text-warn">
                    {compensationOrder.get(step.step)}.ª compensación
                  </span>
                )}
                {step.status !== 'PENDING' && (
                  <span className="ml-auto font-mono text-[11.5px] text-fog-700">{formatTime(step.updated_at)}</span>
                )}
              </div>
              <p className="mt-1 text-[13px] text-fog-700">{STEP_SERVICE[step.step]}</p>
              {step.detail && <p className="mt-1.5 text-[13.5px] leading-relaxed text-fog-500">{step.detail}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
