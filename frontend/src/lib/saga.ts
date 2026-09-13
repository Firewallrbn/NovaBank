import type { StepName, StepStatus, TransferStatus } from './api';

export const SAGA_STEPS: StepName[] = ['DEBIT', 'RISK', 'CLEARING', 'CREDIT'];

export const STEP_LABELS: Record<StepName, string> = {
  DEBIT: 'Débito en cuenta origen',
  RISK: 'Evaluación de riesgo',
  CLEARING: 'Liquidación interbancaria',
  CREDIT: 'Crédito en cuenta destino',
};

export const STEP_SERVICE: Record<StepName, string> = {
  DEBIT: 'Account & Ledger',
  RISK: 'Riesgo y antifraude',
  CLEARING: 'Pasarela interbancaria',
  CREDIT: 'Account & Ledger',
};

export const COMPENSATION_LABELS: Partial<Record<StepName, string>> = {
  DEBIT: 'Reintegro del débito',
  RISK: 'Anulación de la aprobación',
  CLEARING: 'Anulación de la liquidación',
};

export const STEP_STATUS_LABELS: Record<StepStatus, string> = {
  PENDING: 'pendiente',
  RUNNING: 'en ejecución',
  SUCCEEDED: 'exitoso',
  FAILED: 'fallido',
  SKIPPED: 'omitido',
  COMPENSATING: 'compensando',
  COMPENSATED: 'compensado',
};

/** Tono semántico de la máquina de estados. Los colores de fallo y compensación
 *  no son un segundo acento decorativo: comunican el estado real de la saga. */
export type Tone = 'idle' | 'active' | 'ok' | 'fail' | 'undo';

export const STEP_TONE: Record<StepStatus, Tone> = {
  PENDING: 'idle',
  RUNNING: 'active',
  SUCCEEDED: 'ok',
  FAILED: 'fail',
  SKIPPED: 'idle',
  COMPENSATING: 'undo',
  COMPENSATED: 'undo',
};

export const TRANSFER_STATUS_LABELS: Record<TransferStatus, string> = {
  PENDIENTE: 'Pendiente',
  EN_PROCESO: 'En proceso',
  COMPENSANDO: 'Compensando',
  CONFIRMADO: 'Confirmado',
  RECHAZADO_FONDOS: 'Rechazado por fondos',
  RECHAZADO_CUENTA: 'Cuenta inexistente',
  RECHAZADO_RIESGO: 'Rechazado por riesgo',
  RECHAZADO_RED: 'Rechazado por red',
  FALLO_TECNICO: 'Fallo técnico',
};

export const TRANSFER_TONE: Record<TransferStatus, Tone> = {
  PENDIENTE: 'idle',
  EN_PROCESO: 'active',
  COMPENSANDO: 'undo',
  CONFIRMADO: 'ok',
  RECHAZADO_FONDOS: 'fail',
  RECHAZADO_CUENTA: 'fail',
  RECHAZADO_RIESGO: 'fail',
  RECHAZADO_RED: 'fail',
  FALLO_TECNICO: 'fail',
};

export const TERMINAL_STATUSES: TransferStatus[] = [
  'CONFIRMADO',
  'RECHAZADO_FONDOS',
  'RECHAZADO_CUENTA',
  'RECHAZADO_RIESGO',
  'RECHAZADO_RED',
  'FALLO_TECNICO',
];

export const isTerminal = (status: TransferStatus) => TERMINAL_STATUSES.includes(status);

export const MODE_LABELS = {
  orchestration: 'Orquestación',
  choreography: 'Coreografía',
} as const;

export const TONE_TEXT: Record<Tone, string> = {
  idle: 'text-fog-700',
  active: 'text-accent',
  ok: 'text-accent',
  fail: 'text-danger',
  undo: 'text-warn',
};

export const TONE_DOT: Record<Tone, string> = {
  idle: 'bg-ink-500',
  active: 'bg-accent',
  ok: 'bg-accent',
  fail: 'bg-danger',
  undo: 'bg-warn',
};

export const TONE_BORDER: Record<Tone, string> = {
  idle: 'border-white/8',
  active: 'border-accent/45',
  ok: 'border-accent/30',
  fail: 'border-danger/40',
  undo: 'border-warn/40',
};
