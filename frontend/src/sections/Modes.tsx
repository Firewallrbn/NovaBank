import { motion, useReducedMotion } from 'motion/react';
import { ArrowDownIcon, ArrowRightIcon } from '@phosphor-icons/react';
import { cx } from '../components/ui';

const SERVICES = ['Account', 'Riesgo', 'Clearing'];

const EVENT_CHAIN = [
  'TransferenciaSolicitada',
  'SaldoDebitado',
  'RiesgoAprobado',
  'LiquidacionConfirmada',
  'SaldoAcreditado',
];

const FACTS = {
  orchestration: [
    ['Acoplamiento', 'El orquestador conoce las tres APIs. Los servicios no se conocen entre sí.'],
    ['Orden inverso', 'Explícito: una pila de pasos completados que se desapila al fallar.'],
    ['En Prefect', 'Un flow run con el grafo completo de tasks y compensaciones.'],
  ],
  choreography: [
    ['Acoplamiento', 'Nadie conoce APIs ajenas. Solo contratos de eventos en el bus.'],
    ['Orden inverso', 'Emergente: Account reintegra solo cuando Riesgo ya anuló su aprobación.'],
    ['En Prefect', 'Un flow run por servicio, correlacionados por el tag de la transferencia.'],
  ],
};

function FactList({ facts }: { facts: string[][] }) {
  return (
    <dl className="mt-8 space-y-5">
      {facts.map(([term, description]) => (
        <div key={term} className="grid gap-1">
          <dt className="font-mono text-[11.5px] tracking-wide text-fog-700 uppercase">{term}</dt>
          <dd className="text-[14.5px] leading-relaxed text-fog-300">{description}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function Modes() {
  const reduce = useReducedMotion();
  const reveal = (delay: number) => ({
    initial: reduce ? false : { opacity: 0, y: 20 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true, amount: 0.25 },
    transition: { duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] as const },
  });

  return (
    <section id="modos" className="scroll-mt-[68px] border-t border-white/5 py-24 md:py-32">
      <div className="shell">
        <h2 className="max-w-[22ch] text-[clamp(2rem,4vw,3rem)] leading-[1.08] font-medium tracking-[-0.03em]">
          La misma saga, con y sin coordinador
        </h2>
        <p className="mt-5 max-w-[58ch] text-[17px] leading-relaxed text-fog-500">
          Las dos modalidades comparten la lógica de negocio de cada servicio. Lo único que cambia es quién decide el
          siguiente paso.
        </p>

        <div className="mt-14 grid gap-5 lg:grid-cols-2">
          <motion.article
            {...reveal(0)}
            className="rounded-[16px] border border-white/8 bg-ink-850 p-8 hairline-top md:p-10"
          >
            <h3 className="text-[22px] font-medium tracking-[-0.02em]">Orquestación</h3>
            <p className="mt-2 text-[14.5px] text-fog-500">Un flow de Prefect comanda cada paso por HTTP.</p>

            {/* Diagrama: coordinador central con tres radios. */}
            <div className="mt-9 rounded-[12px] border border-white/8 bg-ink-900/60 p-6">
              <div className="mx-auto w-fit rounded-[10px] border border-accent/40 bg-accent-dim px-4 py-2 font-mono text-[12px] text-accent">
                Orquestador
              </div>
              <div className="mx-auto my-3 flex w-fit justify-center">
                <ArrowDownIcon size={14} weight="bold" className="text-fog-700" />
              </div>
              <div className="grid grid-cols-3 gap-2">
                {SERVICES.map((service) => (
                  <div
                    key={service}
                    className="rounded-[10px] border border-white/10 bg-ink-800 py-2.5 text-center font-mono text-[11.5px] text-fog-300"
                  >
                    {service}
                  </div>
                ))}
              </div>
            </div>

            <FactList facts={FACTS.orchestration} />
          </motion.article>

          <motion.article
            {...reveal(0.1)}
            className="rounded-[16px] border border-white/8 bg-ink-850 p-8 hairline-top md:p-10"
          >
            <h3 className="text-[22px] font-medium tracking-[-0.02em]">Coreografía</h3>
            <p className="mt-2 text-[14.5px] text-fog-500">Cada servicio reacciona a eventos del bus. No hay centro.</p>

            {/* Diagrama: cadena causal de eventos, sin nodo central. */}
            <div className="mt-9 rounded-[12px] border border-white/8 bg-ink-900/60 p-6">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-2.5">
                {EVENT_CHAIN.map((event, index) => (
                  <span key={event} className="flex items-center gap-2">
                    <span
                      className={cx(
                        'rounded-full border px-2.5 py-1 font-mono text-[11px] whitespace-nowrap',
                        index === EVENT_CHAIN.length - 1
                          ? 'border-accent/40 bg-accent-dim text-accent'
                          : 'border-white/10 bg-ink-800 text-fog-300',
                      )}
                    >
                      {event}
                    </span>
                    {index < EVENT_CHAIN.length - 1 && (
                      <ArrowRightIcon size={11} weight="bold" className="text-fog-700" />
                    )}
                  </span>
                ))}
              </div>
            </div>

            <FactList facts={FACTS.choreography} />
          </motion.article>
        </div>
      </div>
    </section>
  );
}
