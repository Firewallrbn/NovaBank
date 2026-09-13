/** Marca de NovaBank y logotipo de Google.
 *
 *  El glifo de NovaBank es una flecha de retorno: la compensación en orden
 *  inverso es, literalmente, el producto. El logotipo de Google es la marca
 *  oficial de cuatro colores, usada aquí en un botón de acceso de demostración.
 */

export function BrandMark({ className = 'h-7 w-7' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="novabank-mark" x1="2" y1="30" x2="30" y2="2" gradientUnits="userSpaceOnUse">
          <stop stopColor="#0C8F63" />
          <stop offset="1" stopColor="#7EF07A" />
        </linearGradient>
      </defs>
      {/* Bloque sólido con la flecha de retorno recortada: la compensación en
          orden inverso es el producto, y el contraste la hace legible a 20 px. */}
      <rect width="32" height="32" rx="9" fill="url(#novabank-mark)" />
      <path
        d="M10.2 18.6a6.6 6.6 0 1 0 1.6-6.9"
        stroke="#07100C"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
      <path d="M8.4 8.9v4.4h4.4" stroke="#07100C" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={className}>
      <span className="font-semibold tracking-[-0.02em] text-fog-100">nova</span>
      <span className="font-semibold tracking-[-0.02em] text-accent">bank</span>
    </span>
  );
}

export function GoogleLogo({ className = 'h-[18px] w-[18px]' }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}
