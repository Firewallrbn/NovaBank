import { motion, useReducedMotion } from 'motion/react';
import { ArrowLeftIcon, ArrowRightIcon } from '@phosphor-icons/react';
import { cx } from '../components/ui';

const STEPS = [
  {
    step: 'Débito',
    service: 'Account & Ledger',
    detail: 'Descuenta el importe de la cuenta origen en una sola sentencia atómica.',
    undo: 'Reintegrar débito',
  },
  {
    step: 'Riesgo',
    service: 'Antifraude',
    detail: 'Aplica el límite por transacción y reserva cupo del límite diario.',
    undo: 'Anular aprobación',
  },
  {
    step: 'Liquidación',
    service: 'Pasarela interbancaria',
    detail: 'Contacta la red externa. Es la transacción pivote de la saga.',
    undo: 'Anular liquidación',
  },
  {
    step: 'Crédito',
    service: 'Account & Ledger',
    detail: 'Acredita la cuenta destino. Pasado el pivote solo se reintenta.',
    undo: null,
  },
];

export default function SagaFlow() {
  const reduce = useReducedMotion();

  return (
    <section id="arquitectura" className="scroll-mt-[68px] border-t border-white/5 py-24 md:py-32">
      <div className="shell">
        <h2 className="max-w-[20ch] text-[clamp(2rem,4vw,3rem)] leading-[1.08] font-medium tracking-[-0.03em]">
          Cuatro pasos hacia adelante, tres de vuelta
        </h2>
        <p className="mt-5 max-w-[58ch] text-[17px] leading-relaxed text-fog-500">
          Cada paso es una transacción local que confirma en su propia base de datos. Si uno falla, los anteriores se
          deshacen en orden inverso estricto.
        </p>

        <ol className="mt-16 grid gap-px overflow-hidden rounded-[16px] border border-white/8 bg-white/5 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <motion.li
              key={step.step}
              initial={reduce ? false : { opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.5, delay: index * 0.07, ease: [0.16, 1, 0.3, 1] }}
              className="flex flex-col gap-3 bg-ink-850 p-7"
            >
              <div className="flex items-center gap-2.5">
                <span className="font-mono text-[13px] text-accent">{String(index + 1).padStart(2, '0')}</span>
                <ArrowRightIcon size={12} weight="bold" className="text-fog-700" />
                <span className="text-[13px] text-fog-700">{step.service}</span>
              </div>
              <h3 className="text-[19px] font-medium tracking-[-0.01em] text-fog-100">{step.step}</h3>
              <p className="text-[14px] leading-relaxed text-fog-500">{step.detail}</p>
            </motion.li>
          ))}
        </ol>

        {/* La marcha atrás: mismos pasos, recorridos al revés. */}
        <div className="mt-6 flex flex-col gap-4 rounded-[16px] border border-warn/25 bg-warn/[0.04] p-7 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <ArrowLeftIcon size={16} weight="bold" className="shrink-0 text-warn" />
            <p className="text-[15px] text-fog-300">
              Ante un fallo, la compensación recorre la cadena al revés y se detiene donde empezó la saga.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {STEPS.filter((step) => step.undo)
              .reverse()
              .map((step, index) => (
                <span key={step.step} className="flex items-center gap-2">
                  {index > 0 && <ArrowLeftIcon size={11} weight="bold" className="text-fog-700" />}
                  <span
                    className={cx(
                      'rounded-full border border-warn/25 bg-ink-850 px-3 py-1.5',
                      'font-mono text-[11.5px] whitespace-nowrap text-warn',
                    )}
                  >
                    {step.undo}
                  </span>
                </span>
              ))}
          </div>
        </div>
      </div>
    </section>
  );
}
