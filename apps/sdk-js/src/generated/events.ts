/* tslint:disable */
/* eslint-disable */
// This file is auto-generated via npm run generate:types. Do not edit manually.

export interface InteractionCreateEvent {
  tenant_id: string;
  user_id: string;
  skill: string;
  input: InteractionCreateEventInput;
  context: InteractionCreateEventContext;
  version: InteractionCreateEventVersion;
  timings: InteractionCreateEventTimings;
  costs: InteractionCreateEventCosts;
  idempotency_key?: string;
  created_at?: string;
}

export interface InteractionCreateEventInput {
  text: string;
  attachments?: string[];
  metadata?: Record<string, unknown>;
  [k: string]: unknown;
}

export interface InteractionCreateEventContext {
  retrieval_chunks?: InteractionCreateEventContextRetrievalChunk[];
  customer_tier?: string;
  sla_mins?: number;
  [k: string]: unknown;
}

export interface InteractionCreateEventContextRetrievalChunk {
  id: string;
  text: string;
  score?: number;
  source?: string;
  [k: string]: unknown;
}

export interface InteractionCreateEventVersion {
  policy_id: string;
  base_model: string;
  adapter?: string;
  [k: string]: unknown;
}

export interface InteractionCreateEventTimings {
  ms_total: number;
  ms_decode?: number;
  [k: string]: unknown;
}

export interface InteractionCreateEventCosts {
  tokens_in: number;
  tokens_out: number;
  [k: string]: unknown;
}

export interface InteractionOutputEvent {
  tenant_id: string;
  interaction_id: string;
  output: InteractionOutputEventOutput;
  timings: InteractionCreateEventTimings;
  costs: InteractionCreateEventCosts;
  version: InteractionCreateEventVersion;
  idempotency_key?: string;
  created_at?: string;
  trace_id?: string;
}

export interface InteractionOutputEventOutput {
  text: string;
  tool_calls?: InteractionOutputEventToolCall[];
  citations?: InteractionOutputEventCitation[];
  [k: string]: unknown;
}

export interface InteractionOutputEventToolCall {
  tool_name: string;
  arguments: Record<string, unknown>;
  status?: string;
  latency_ms?: number;
  [k: string]: unknown;
}

export interface InteractionOutputEventCitation {
  chunk_id: string;
  confidence?: number;
  [k: string]: unknown;
}

export interface FeedbackSubmitEvent {
  tenant_id: string;
  interaction_id: string;
  explicit?: FeedbackSubmitEventExplicit;
  implicit?: FeedbackSubmitEventImplicit;
  labels?: Record<string, unknown>;
  idempotency_key?: string;
  created_at?: string;
}

export interface FeedbackSubmitEventExplicit {
  thumb?: -1 | 1;
  rating?: number;
  comment?: string;
  [k: string]: unknown;
}

export interface FeedbackSubmitEventImplicit {
  edited_text?: string;
  sent?: boolean;
  time_to_send_ms?: number;
  escalated?: boolean;
  follow_up_count?: number;
  [k: string]: unknown;
}

export interface TaskResultEvent {
  tenant_id: string;
  interaction_id: string;
  label: TaskResultEventLabel;
  observed_at?: string;
  note?: string;
  idempotency_key?: string;
  created_at?: string;
}

export interface TaskResultEventLabel {
  correct?: boolean;
  f1?: number;
  resolved?: boolean;
  kpi_delta?: number;
  [k: string]: unknown;
}

export type TelemetryEvent =
  | InteractionCreateEvent
  | InteractionOutputEvent
  | FeedbackSubmitEvent
  | TaskResultEvent;
