const money = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  currencyDisplay: 'narrowSymbol',
  minimumFractionDigits: 2,
});

/** El backend trabaja siempre en centavos (enteros). Aquí se convierte solo para mostrar. */
export const formatMoney = (cents: number) => money.format(cents / 100);

export const formatAmount = (units: number) => money.format(units);

const time = new Intl.DateTimeFormat('es-CO', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

export const formatTime = (iso: string) => time.format(new Date(iso));

export const formatElapsed = (fromIso: string, toIso: string) => {
  const seconds = (new Date(toIso).getTime() - new Date(fromIso).getTime()) / 1000;
  return `${seconds.toFixed(1)} s`;
};

export const shortId = (id: string) => id.slice(0, 8);
