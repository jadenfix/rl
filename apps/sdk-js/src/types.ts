export interface InteractionCreateEvent {
  tenant_id: string;
  user_id: string;
  skill: string;
  input: Record<string, unknown>;
  context?: Record<string, unknown>;
  version: Record<string, unknown>;
  timings: Record<string, unknown>;
  costs: Record<string, unknown>;
  idempotency_key?: string;
  [key: string]: unknown;
}

export interface InteractionOutputEvent {
  tenant_id: string;
  interaction_id: string;
  output: Record<string, unknown>;
  timings: Record<string, unknown>;
  costs: Record<string, unknown>;
  version: Record<string, unknown>;
  idempotency_key?: string;
  [key: string]: unknown;
}

export interface FeedbackSubmitEvent {
  tenant_id: string;
  interaction_id: string;
  explicit?: Record<string, unknown>;
  implicit?: Record<string, unknown>;
  labels?: Record<string, unknown>;
  idempotency_key?: string;
  [key: string]: unknown;
}

export interface TaskResultEvent {
  tenant_id: string;
  interaction_id: string;
  label: Record<string, unknown>;
  idempotency_key?: string;
  [key: string]: unknown;
}

export interface ValidateResponse {
  event_type: string;
  valid: boolean;
}

export type TelemetryEvent =
  | InteractionCreateEvent
  | InteractionOutputEvent
  | FeedbackSubmitEvent
  | TaskResultEvent;
