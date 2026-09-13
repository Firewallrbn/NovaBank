import { Link } from 'react-router-dom';
import { BrandMark, Wordmark } from './brand';
import { LinkButton } from './ui';

const LINKS = [
  { href: '#arquitectura', label: 'Arquitectura' },
  { href: '#modos', label: 'Orquestación y coreografía' },
  { href: '#casos', label: 'Casos de prueba' },
  { href: '#observabilidad', label: 'Observabilidad' },
];

export default function SiteNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-ink-600/80 backdrop-blur-xl">
      <nav className="shell flex h-[68px] items-center justify-between gap-6">
        <Link to="/" className="flex shrink-0 items-center gap-2.5">
          <BrandMark />
          <Wordmark className="text-[17px]" />
        </Link>

        <ul className="hidden items-center gap-7 lg:flex">
          {LINKS.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="text-[14px] text-fog-300 transition-colors duration-200 hover:text-fog-100"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>

        <div className="flex shrink-0 items-center gap-2">
          <a
            href="#acceso"
            className="hidden h-9 items-center rounded-[10px] px-3.5 text-[14px] font-medium text-fog-100 transition-colors duration-200 hover:bg-white/10 sm:inline-flex"
          >
            Sign in
          </a>
          <LinkButton to="/simulador" size="sm">
            Simulador
          </LinkButton>
        </div>
      </nav>
    </header>
  );
}
