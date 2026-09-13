import { useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { ArrowRightIcon } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import Threads from '../components/Threads';
import { GoogleLogo } from '../components/brand';
import { servicesHealth } from '../lib/api';
import { cx } from '../components/ui';

/** Píldora del hero: estado real de los servicios, no un número decorativo. */
function ServicesPill() {
  const [health, setHealth] = useState<{ up: number; total: number } | null>(null);

  useEffect(() => {
    let alive = true;
    servicesHealth()
      .then((result) => {
        if (!alive) return;
        const values = Object.values(result);
        setHealth({ up: values.filter((state) => state === 'ok').length, total: values.length });
      })
      .catch(() => alive && setHealth(null));
    return () => {
      alive = false;
    };
  }, []);

  const allUp = health !== null && health.up === health.total;

  return (
    <Link
      to="/simulador"
      className={cx(
        'group inline-flex h-8 items-center gap-2.5 rounded-full border border-white/10 bg-ink-800/70 pr-2.5 pl-3',
        'backdrop-blur transition-colors duration-200 hover:border-white/20',
      )}
    >
      <span className="text-[13px] text-fog-500">Servicios en línea</span>
      {health === null ? (
        <span className="h-3 w-10 animate-pulse rounded bg-ink-600" />
      ) : (
        <span className="flex items-center gap-1.5">
          <span className={cx('h-1.5 w-1.5 rounded-full', allUp ? 'bg-accent' : 'bg-warn')} />
          <span className="font-mono text-[13px] text-accent">
            {health.up}/{health.total}
          </span>
        </span>
      )}
      <ArrowRightIcon
        size={13}
        weight="bold"
        className="text-fog-700 transition-transform duration-200 group-hover:translate-x-0.5"
      />
    </Link>
  );
}

export default function Hero() {
  const reduce = useReducedMotion();

  const rise = (delay: number) => ({
    initial: reduce ? false : { opacity: 0, y: 18 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.7, delay, ease: [0.16, 1, 0.3, 1] as const },
  });

  return (
    <section className="relative isolate overflow-hidden">
      {/* Fondo: haz de hilos WebGL. Es decoración, nunca recibe eventos. */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div
          className="absolute top-[-4%] right-[-12%] bottom-[-18%] left-[2%] rotate-[-28deg] opacity-45 md:left-[18%] md:opacity-95"
          style={{
            maskImage: 'linear-gradient(90deg, transparent 0%, #000 14%, #000 86%, transparent 100%)',
            WebkitMaskImage: 'linear-gradient(90deg, transparent 0%, #000 14%, #000 86%, transparent 100%)',
          }}
        >
          <Threads className="h-full w-full" amplitude={1.3} distance={0.06} speed={0.4} />
        </div>
        <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-b from-transparent to-ink-900" />
      </div>

      <div className="shell flex min-h-[calc(100dvh-68px)] flex-col justify-center pt-16 pb-36">
        <div className="max-w-[640px]">
          <motion.div {...rise(0)}>
            <ServicesPill />
          </motion.div>

          <motion.h1
            {...rise(0.08)}
            className="mt-8 text-[clamp(2.75rem,7vw,4.5rem)] leading-[1.02] font-medium tracking-[-0.035em] text-fog-100"
          >
            El dinero nunca
            <br />
            queda en el limbo
          </motion.h1>

          <motion.p {...rise(0.16)} className="mt-6 max-w-[34rem] text-[19px] leading-relaxed text-fog-500">
            Transferencias interbancarias con <strong className="font-medium text-fog-100">saga orquestada</strong>,{' '}
            <strong className="font-medium text-fog-100">coreografiada</strong> y compensación en orden inverso.
          </motion.p>

          <motion.div {...rise(0.24)} className="mt-10 flex flex-wrap items-center gap-3" id="acceso">
            <Link
              to="/simulador"
              className="group inline-flex h-12 items-center gap-2 rounded-[10px] bg-fog-100 px-6 text-[15px] font-medium text-ink-900 transition-colors duration-200 hover:bg-white active:translate-y-px"
            >
              Get started
              <ArrowRightIcon
                size={15}
                weight="bold"
                className="transition-transform duration-200 group-hover:translate-x-0.5"
              />
            </Link>
            <button
              type="button"
              className="inline-flex h-12 items-center gap-3 rounded-[10px] border border-white/10 bg-ink-800/80 px-5 text-[15px] font-medium text-fog-100 backdrop-blur transition-colors duration-200 hover:border-white/20 hover:bg-ink-700 active:translate-y-px"
            >
              <GoogleLogo />
              Sign up with Google
            </button>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
