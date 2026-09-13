import { ArrowRightIcon } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import { BrandMark, Wordmark } from '../components/brand';

export default function SiteFooter() {
  return (
    <footer className="border-t border-white/5">
      <div className="shell flex flex-col items-start gap-8 py-20 lg:flex-row lg:items-center lg:justify-between lg:py-24">
        <div>
          <h2 className="max-w-[18ch] text-[clamp(1.75rem,3.4vw,2.5rem)] leading-[1.1] font-medium tracking-[-0.03em]">
            Rompa una transferencia a propósito
          </h2>
          <p className="mt-4 max-w-[46ch] text-[16px] leading-relaxed text-fog-500">
            El simulador expone los interruptores de caos y muestra cada compensación mientras ocurre.
          </p>
        </div>
        <Link
          to="/simulador"
          className="group inline-flex h-12 shrink-0 items-center gap-2 rounded-[10px] bg-fog-100 px-6 text-[15px] font-medium text-ink-900 transition-colors duration-200 hover:bg-white active:translate-y-px"
        >
          Get started
          <ArrowRightIcon
            size={15}
            weight="bold"
            className="transition-transform duration-200 group-hover:translate-x-0.5"
          />
        </Link>
      </div>

      <div className="border-t border-white/5">
        <div className="shell flex flex-col gap-4 py-8 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2.5">
            <BrandMark className="h-5 w-5" />
            <Wordmark className="text-[14px]" />
            <span className="ml-1 text-[13px] text-fog-700">International</span>
          </div>
          <p className="text-[13px] text-fog-700">
            Taller de arquitectura distribuida. Patrón Saga sobre el modelo BASE.
          </p>
        </div>
      </div>
    </footer>
  );
}
