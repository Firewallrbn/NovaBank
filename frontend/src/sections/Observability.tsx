import { useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { ArrowUpRightIcon } from '@phosphor-icons/react';
import { getConfig } from '../lib/api';

const FACTS = [
  ['Delays de 2 a 4 segundos', 'Cada micro-paso se pausa antes de actuar, así la marcha atrás se ve suceder.'],
  ['Bitácora de auditoría', 'Cada cambio de estado queda registrado con su origen, su motivo y su hora.'],
  ['Contraste entre modos', 'Orquestación: un flow run con su grafo. Coreografía: un flow run por servicio.'],
  ['Despliegue permanente', 'La saga vive en Prefect como despliegue y puede lanzarse desde su consola.'],
];

export default function Observability() {
  const reduce = useReducedMotion();
  const [consoles, setConsoles] = useState({
    prefect: 'http://localhost:4200',
    rabbitmq: 'http://localhost:15672',
  });

  useEffect(() => {
    let alive = true;
    getConfig()
      .then((config) => {
        if (alive) setConsoles({ prefect: config.prefect_ui_url, rabbitmq: config.rabbitmq_ui_url });
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section id="observabilidad" className="scroll-mt-[68px] border-t border-white/5 py-24 md:py-32">
      <div className="shell grid items-center gap-14 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
        <div>
          <h2 className="text-[clamp(2rem,4vw,3rem)] leading-[1.08] font-medium tracking-[-0.03em]">
            Se ve fallar y se ve deshacerse
          </h2>
          <p className="mt-5 max-w-[46ch] text-[17px] leading-relaxed text-fog-500">
            Cada paso publica telemetría al bus. El gateway la convierte en bitácora y la empuja al navegador en vivo.
          </p>

          <dl className="mt-10 space-y-6 border-l border-white/8 pl-6">
            {FACTS.map(([term, description]) => (
              <div key={term}>
                <dt className="text-[15px] font-medium text-fog-100">{term}</dt>
                <dd className="mt-1 max-w-[42ch] text-[14.5px] leading-relaxed text-fog-500">{description}</dd>
              </div>
            ))}
          </dl>

          <div className="mt-10 flex flex-wrap gap-3">
            <a
              href={consoles.prefect}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-10 items-center gap-2 rounded-[10px] border border-white/10 bg-ink-800 px-4 text-[14px] text-fog-100 transition-colors duration-200 hover:border-white/20 hover:bg-ink-700"
            >
              Prefect
              <ArrowUpRightIcon size={13} weight="bold" className="text-fog-700" />
            </a>
            <a
              href={consoles.rabbitmq}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-10 items-center gap-2 rounded-[10px] border border-white/10 bg-ink-800 px-4 text-[14px] text-fog-100 transition-colors duration-200 hover:border-white/20 hover:bg-ink-700"
            >
              RabbitMQ
              <ArrowUpRightIcon size={13} weight="bold" className="text-fog-700" />
            </a>
          </div>
        </div>

        <motion.figure
          initial={reduce ? false : { opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.25 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="overflow-hidden rounded-[16px] border border-white/8 bg-ink-850 hairline-top"
        >
          <img
            src="/img/prefect-flow-run.png"
            alt="Flow run de la saga orquestada en Prefect, con el paso de liquidación fallido y las compensaciones posteriores"
            width={1324}
            height={368}
            loading="lazy"
            className="w-full"
          />
          <figcaption className="border-t border-white/8 px-6 py-4 text-[13.5px] text-fog-500">
            Saga orquestada con timeout en la pasarela, vista en Prefect.
          </figcaption>
        </motion.figure>
      </div>
    </section>
  );
}
