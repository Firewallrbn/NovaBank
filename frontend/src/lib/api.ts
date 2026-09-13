/** Cliente del API Gateway. Todas las rutas son relativas: nginx (o el proxy de
 *  Vite en desarrollo) las reenvía al gateway en :8000. */

export type SagaMode = 'orchestration' | 'choreography';

export type StepName = 'DEBIT' | 'RISK' | 'CLEARING' | 'CREDIT';

export type StepStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'SKIPPED'
  | 'COMPENSATING'
  | 'COMPENSATED';

export type TransferStatus =
  | 'PENDIENTE'
  | 'EN_PROCESO'
  | 'COMPENSANDO'
  | 'CONFIRMADO'
  | 'RECHAZADO_FONDOS'
  | 'RECHAZADO_CUENTA'
  | 'RECHAZADO_RIESGO'
  | 'RECHAZADO_RED'
  | 'FALLO_TECNICO';

export type Chaos = { force_fraud: boolean; clearing_timeout: boolean };

export type TransferStep = {
  step: StepName;
  status: StepStatus;
  detail: string | null;
  updated_at: string;
};

export type Transfer = {
  transfer_id: string;
  mode: SagaMode;
  source_account: string;
  destination_account: string;
  amount_cents: number;
  chaos: Chaos;
  delay_seconds: number;
  status: TransferStatus;
  failure_reason: string | null;
  detail: string | null;
  duplicate_requests: number;
  created_at: string;
  updated_at: string;
  steps: TransferStep[];
  prefect: { flow_run_id: string | null; flow_run_url: string | null; tag: string };
};

export type AuditEntry = {
  id: number;
  transfer_id: string;
  at: string;
  source: string;
  category: 'SOLICITUD' | 'DUPLICADO' | 'DESPACHO' | 'PASO' | 'ESTADO' | 'EVENTO';
  step: StepName | null;
  status: string | null;
  event_type: string | null;
  reason: string | null;
  detail: string | null;
};

export type Account = { id: string; owner: string; balance_cents: number; updated_at: string };

export type GatewayConfig = {
  prefect_ui_url: string;
  rabbitmq_ui_url: string;
  min_delay_seconds: number;
  max_delay_seconds: number;
  modes: SagaMode[];
};

export type TransferRequest = {
  source_account: string;
  destination_account: string;
  amount: number;
  mode: SagaMode;
  chaos: Chaos;
  delay_seconds: number;
};

export type CreateTransferResponse = {
  duplicate: boolean;
  idempotency_key: string;
  transfer: Transfer;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError('No hay conexión con el API Gateway', 0);
  }
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    throw new ApiError(typeof detail === 'string' ? detail : `Error ${response.status}`, response.status);
  }
  return body as T;
}

export const getConfig = () => request<GatewayConfig>('/config');
export const getAccounts = () => request<Account[]>('/accounts');
export const listTransfers = () => request<Transfer[]>('/transfers?limit=30');
export const getTransfer = (id: string) => request<Transfer & { audit: AuditEntry[] }>(`/transfers/${id}`);
export const getAudit = (id: string) => request<AuditEntry[]>(`/transfers/${id}/audit`);
export const servicesHealth = () => request<Record<string, string>>('/services/health');
export const resetAll = () => request<{ status: string }>('/admin/reset', { method: 'POST' });
export const issueIdempotencyKey = () =>
  request<{ idempotency_key: string }>('/idempotency-keys', { method: 'POST' });

export const createTransfer = (body: TransferRequest, idempotencyKey: string) =>
  request<CreateTransferResponse>('/transfers', {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify(body),
  });
