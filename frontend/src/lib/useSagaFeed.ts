import { useCallback, useEffect, useRef, useState } from 'react';
import { getAccounts, listTransfers, type Account, type AuditEntry, type Transfer } from './api';

type StreamMessage = {
  type: 'transfer' | 'reset';
  transfer_id: string | null;
  transfer?: Transfer;
  audit?: AuditEntry[];
};

const byNewest = (a: Transfer, b: Transfer) => b.created_at.localeCompare(a.created_at);

/**
 * Feed en vivo de la saga. El gateway empuja cada cambio de paso y de estado por
 * SSE (`GET /api/stream`); aquí solo se aplica al modelo local. Los saldos se
 * releen tras cada evento porque los mueve otro servicio, no el gateway.
 */
export function useSagaFeed() {
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [audit, setAudit] = useState<Record<string, AuditEntry[]>>({});
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const accountsTimer = useRef<number | undefined>(undefined);

  const refreshAccounts = useCallback(async () => {
    try {
      setAccounts(await getAccounts());
    } catch {
      /* el panel de saldos conserva el último valor conocido */
    }
  }, []);

  const refreshTransfers = useCallback(async () => {
    try {
      const list = await listTransfers();
      setTransfers(list.sort(byNewest));
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'No se pudo cargar el historial');
    } finally {
      setLoading(false);
    }
  }, []);

  // Relectura de saldos con un pequeño retardo: durante una saga llegan varios
  // eventos seguidos y no tiene sentido pedir los saldos una vez por evento.
  const scheduleAccountsRefresh = useCallback(() => {
    window.clearTimeout(accountsTimer.current);
    accountsTimer.current = window.setTimeout(refreshAccounts, 250);
  }, [refreshAccounts]);

  useEffect(() => {
    void refreshTransfers();
    void refreshAccounts();

    const source = new EventSource('/api/stream');
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);

    const onTransfer = (event: MessageEvent<string>) => {
      const message: StreamMessage = JSON.parse(event.data);
      if (message.transfer) {
        const incoming = message.transfer;
        setTransfers((current) => {
          const rest = current.filter((t) => t.transfer_id !== incoming.transfer_id);
          return [incoming, ...rest].sort(byNewest);
        });
      }
      if (message.audit?.length && message.transfer_id) {
        const id = message.transfer_id;
        setAudit((current) => {
          const existing = current[id] ?? [];
          const seen = new Set(existing.map((entry) => entry.id));
          const added = message.audit!.filter((entry) => !seen.has(entry.id));
          if (added.length === 0) return current;
          return { ...current, [id]: [...existing, ...added].sort((a, b) => a.id - b.id) };
        });
      }
      scheduleAccountsRefresh();
    };

    const onReset = () => {
      setTransfers([]);
      setAudit({});
      scheduleAccountsRefresh();
    };

    source.addEventListener('transfer', onTransfer as EventListener);
    source.addEventListener('reset', onReset);

    return () => {
      source.removeEventListener('transfer', onTransfer as EventListener);
      source.removeEventListener('reset', onReset);
      source.close();
      window.clearTimeout(accountsTimer.current);
    };
  }, [refreshAccounts, refreshTransfers, scheduleAccountsRefresh]);

  const mergeAudit = useCallback((transferId: string, entries: AuditEntry[]) => {
    setAudit((current) => {
      const existing = current[transferId] ?? [];
      const seen = new Set(existing.map((entry) => entry.id));
      const added = entries.filter((entry) => !seen.has(entry.id));
      if (added.length === 0) return current;
      return { ...current, [transferId]: [...existing, ...added].sort((a, b) => a.id - b.id) };
    });
  }, []);

  const upsertTransfer = useCallback((transfer: Transfer) => {
    setTransfers((current) => {
      const rest = current.filter((t) => t.transfer_id !== transfer.transfer_id);
      return [transfer, ...rest].sort(byNewest);
    });
  }, []);

  return {
    transfers,
    audit,
    accounts,
    connected,
    loading,
    error,
    mergeAudit,
    upsertTransfer,
    refreshAccounts,
    refreshTransfers,
  };
}
