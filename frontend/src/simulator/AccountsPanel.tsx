import { useEffect, useRef, useState } from 'react';
import type { Account } from '../lib/api';
import { formatMoney } from '../lib/format';
import { cx } from '../components/ui';

/** Resalta un saldo durante un instante cuando cambia: el efecto de la saga
 *  sobre el dinero real es lo que el taller pide ver. */
function useChanged(value: number) {
  const previous = useRef(value);
  const [changed, setChanged] = useState(false);

  useEffect(() => {
    if (previous.current === value) return;
    previous.current = value;
    setChanged(true);
    const timer = window.setTimeout(() => setChanged(false), 1200);
    return () => window.clearTimeout(timer);
  }, [value]);

  return changed;
}

function AccountRow({ account }: { account: Account }) {
  const changed = useChanged(account.balance_cents);

  return (
    <li className="flex items-baseline justify-between gap-4 py-2.5">
      <span className="min-w-0">
        <span className="font-mono text-[13px] text-fog-300">{account.id}</span>
        <span className="ml-2 truncate text-[13px] text-fog-700">{account.owner}</span>
      </span>
      <span
        className={cx(
          'font-mono text-[13.5px] tabular-nums transition-colors duration-500',
          changed ? 'text-accent' : 'text-fog-100',
        )}
      >
        {formatMoney(account.balance_cents)}
      </span>
    </li>
  );
}

export default function AccountsPanel({ accounts }: { accounts: Account[] }) {
  const total = accounts.reduce((sum, account) => sum + account.balance_cents, 0);

  if (accounts.length === 0) {
    return (
      <ul className="space-y-3 py-1">
        {[0, 1, 2, 3].map((index) => (
          <li key={index} className="h-4 animate-pulse rounded bg-ink-700" />
        ))}
      </ul>
    );
  }

  return (
    <div>
      <ul className="divide-y divide-white/5">
        {accounts.map((account) => (
          <AccountRow key={account.id} account={account} />
        ))}
      </ul>
      <div className="mt-3 flex items-baseline justify-between border-t border-white/8 pt-3">
        <span className="text-[12.5px] text-fog-700">Dinero total en el sistema</span>
        <span className="font-mono text-[13.5px] tabular-nums text-fog-300">{formatMoney(total)}</span>
      </div>
    </div>
  );
}
