export * from "./generated/events";

export interface ValidateResponse {
  event_type: string;
  valid: boolean;
}
