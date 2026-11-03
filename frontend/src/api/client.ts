const API_BASE = "http://127.0.0.1:8000/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }
  return payload as T;
}

export type DatabaseConfig = {
  db_type: "mysql" | "postgresql";
  name: string;
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
  ssl: boolean;
};

export type MySQLConfig = DatabaseConfig;

export type ModelProvider = "llama_cpp" | "gemini";

export type ModelConfig = {
  provider: ModelProvider;
  model_path: string;
  context_window: number;
  temperature: number;
  max_tokens: number;
  gemini_model: string;
  gemini_api_key: string;
  api_key_configured: boolean;
};

export type SchemaSnapshot = {
  database: string;
  tables: Array<{
    name: string;
    object_type: "table" | "view";
    comment?: string | null;
    columns: Array<{
      name: string;
      type: string;
      nullable: boolean;
      primary_key: boolean;
      foreign_key?: string | null;
      comment?: string | null;
    }>;
  }>;
};

export type ChatResponse = {
  answer: string;
  sql?: string | null;
  columns: string[];
  rows: Record<string, unknown>[];
  csv_url?: string | null;
  excel_url?: string | null;
  report_title?: string | null;
  database: string;
};

export const api = {
  testDb: (config: DatabaseConfig) =>
    request<{ ok: boolean }>("/db/test", { method: "POST", body: JSON.stringify(config) }),
  saveDb: (config: DatabaseConfig) =>
    request<{ ok: boolean }>("/db/save", { method: "POST", body: JSON.stringify(config) }),
  getActiveDb: () => request<{ config: DatabaseConfig | null }>("/db/active"),
  listDatabases: () => request<{ databases: string[]; active_database: string }>("/db/databases"),
  activateDatabase: (database: string) =>
    request<{ ok: boolean; database: string }>("/db/activate", {
      method: "POST",
      body: JSON.stringify({ database }),
    }),
  getSchema: () => request<SchemaSnapshot>("/db/schema"),
  getActiveModel: () => request<{ config: ModelConfig }>("/model/active"),
  testModel: (config: ModelConfig) =>
    request<{ ok: boolean }>("/model/test", { method: "POST", body: JSON.stringify(config) }),
  saveModel: (config: ModelConfig) =>
    request<{ ok: boolean; provider: ModelProvider }>("/model/save", {
      method: "POST",
      body: JSON.stringify(config),
    }),
  listGoogleModels: (geminiApiKey: string) =>
    request<{ models: string[] }>("/model/google/models", {
      method: "POST",
      body: JSON.stringify({ gemini_api_key: geminiApiKey }),
    }),
  chat: (message: string, conversationId = "default") =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, conversation_id: conversationId, preview_limit: 100 }),
    }),
  reportUrl: (path: string) => `${API_BASE.replace("/api", "")}${path}`,
};
