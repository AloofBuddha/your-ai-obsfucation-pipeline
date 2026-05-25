/** API client — typed wrappers over the FastAPI endpoints. */
import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export const http = axios.create({ baseURL: BASE_URL });

export type Strategy = 'tokenize' | 'pseudonymize';

export interface StartSessionResponse {
  session_id: string;
  user_id: string;
  strategy: Strategy;
}

export interface UploadDocumentResponse {
  doc_id: string;
  filename: string;
}

export interface Entity {
  type: string;
  text: string;
  start: number;
  end: number;
  confidence: number;
}

export interface PipelineResult {
  user_query: string;
  obfuscated_query: string;
  document_text: string;
  detected_entities: Entity[];
  obfuscated_document: string;
  obfuscated_prompt: string;
  llm_response_raw: string;
  restored_response: string;
  strategy_name: Strategy;
}

export type AuditStage = 'vault' | 'detect' | 'obfuscate' | 'llm' | 'restore';

export interface AuditEntry {
  timestamp: string;
  session_id: string;
  action: string;
  entity_type: string | null;
  token_id: string | null;
  metadata: Record<string, string | number | boolean | null>;
  stage: AuditStage;
}

const ACTION_TO_STAGE: Record<string, AuditStage> = {
  VAULT_CREATE: 'vault',
  VAULT_DESTROY: 'vault',
  DOCUMENT_INGEST: 'vault',
  OBFUSCATE: 'obfuscate',
  LLM_CALL: 'llm',
  DEOBFUSCATE: 'restore',
  PIPELINE_RUN: 'restore',
};

function deriveStage(action: string): AuditStage {
  return ACTION_TO_STAGE[action] ?? 'vault';
}

export async function startSession(
  user_id: string,
  strategy: Strategy,
): Promise<StartSessionResponse> {
  const { data } = await http.post('/sessions', { user_id, strategy });
  return data;
}

export async function endSession(session_id: string): Promise<void> {
  await http.delete(`/sessions/${session_id}`);
}

export async function uploadDocument(
  session_id: string,
  file: File,
): Promise<UploadDocumentResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await http.post(`/sessions/${session_id}/documents`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function runPipeline(
  session_id: string,
  doc_id: string,
  user_query: string,
): Promise<PipelineResult> {
  const { data } = await http.post(`/sessions/${session_id}/pipeline`, {
    doc_id,
    user_query,
  });
  return data;
}

export async function fetchAudit(session_id: string): Promise<AuditEntry[]> {
  const { data } = await http.get<Omit<AuditEntry, 'stage'>[]>(
    `/sessions/${session_id}/audit`,
  );
  return data.map((entry) => ({ ...entry, stage: deriveStage(entry.action) }));
}
