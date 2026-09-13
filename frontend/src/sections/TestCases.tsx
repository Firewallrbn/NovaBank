import { motion, useReducedMotion } from 'motion/react';
import { cx } from '../components/ui';

type Case = {
  code: string;
  title: string;
  trigger: string;
  compensation: string;
  status: string;
  tone: 'ok' | 'fail' | 'undo';
  className: string;
};

const CASES: Case[] = [
  {
    code: 'CP-01',
    title: 'Camino feliz',
    trigger: 'Transferencia normal, sin interruptores de caos.',
    compensation: 'Ninguna: los cuatro pasos confirman.',
    status: 'CONFIRMADO',
    tone: 'ok',
    className: 'lg:col-span-2 bg-[radial-gradient(120%_140%_at_85%_0%,rgba(53,208,127,0.14),transparent_62%)]',
  },
  {
    code: 'CP-02',
    title: 'Fondos insuficientes',
    trigger: 'Importe mayor al saldo disponible.',
    compensation: 'Rechazo inmediato, sin reversas.',
    status: 'RECHAZADO_FONDOS',
    tone: 'fail',
    className: '',
  },
  {
    code: 'CP-03',
    title: 'Fraude detectado',
    trigger: 'Interruptor de fraude en el simulador.',
    compensation: 'Se reintegra el débito contable.',
    status: 'RECHAZADO_RIESGO',
    tone: 'undo',
    className: '',
  },
  {
    code: 'CP-04',
    title: 'Caída de la red externa',
    trigger: 'Interruptor de timeout en la pasarela.',
    compensation: 'Se anula el riesgo y luego se reintegra el débito.',
    status: 'RECHAZADO_RED',
    tone: 'undo',
    className: 'bg-[radial-gradient(120%_140%_at_10%_0%,rgba(226,161,60,0.12),transparent_60%)]',
  },
  {
    code: 'CP-05',
    title: 'Reintento idempotente',
    trigger: 'Se reenvía la misma clave de operación.',
    compensation: 'Se reconoce el duplicado sin cobrar de nuevo.',
    status: 'SIN CAMBIOS',
    tone: 'ok',
    className: '',
  },
];

const TONE_CHIP = {
  ok: 'border-accent/30 text-accent',
  fail: 'border-danger/35 text-danger',
  undo: 'border-warn/35 text-warn',
} as const;

export default function TestCases() {
  const reduce = useReducedMotion();

  return (
    <section id="casos" className="scroll-mt-[68px] border-t border-white/5 py-24 md:py-32">
      <div className="shell">
        <h2 className="max-w-[24ch] text-[clamp(2rem,4vw,3rem)] leading-[1.08] font-medium tracking-[-0.03em]">
          Cinco escenarios, dos modos, los mismos saldos
        </h2>
        <p className="mt-5 max-w-[58ch] text-[17px] leading-relaxed text-fog-500">
          El simulador reproduce cada caso con un clic. En los cuatro fallos la cuenta origen termina exactamente como
          empezó.
        </p>

        <div className="mt-14 grid gap-4 lg:grid-cols-3">
          {CASES.map((testCase, index) => (
            <motion.article
              key={testCase.code}
              initial={reduce ? false : { opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.5, delay: index * 0.06, ease: [0.16, 1, 0.3, 1] }}
              className={cx(
                'flex flex-col rounded-[16px] border border-white/8 bg-ink-850 p-7 hairline-top',
                testCase.className,
              )}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-[12px] text-fog-700">{testCase.code}</span>
                <span
                  className={cx(
                    'rounded-full border px-2.5 py-1 font-mono text-[10.5px] tracking-wide',
                    TONE_CHIP[testCase.tone],
                  )}
                >
                  {testCase.status}
                </span>
              </div>
              <h3 className="mt-4 text-[20px] font-medium tracking-[-0.015em] text-fog-100">{testCase.title}</h3>
              <p className="mt-2.5 text-[14.5px] leading-relaxed text-fog-500">{testCase.trigger}</p>
              <p className="mt-auto pt-6 text-[14px] leading-relaxed text-fog-300">{testCase.compensation}</p>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  );
}
