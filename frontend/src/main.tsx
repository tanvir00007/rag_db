import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Bot, Cloud, Database, Download, Play, RefreshCw, Save, Send, Settings } from "lucide-react";
import { api, ChatResponse, DatabaseConfig, ModelConfig, SchemaSnapshot } from "./api/client";
import "./styles/app.css";

const emptyDb: DatabaseConfig = {
  db_type: "postgresql",
  name: "default",
  host: "127.0.0.1",
  port: 55432,
  database: "",
  username: "",
  password: "",
  ssl: false,
};

const emptyModel: ModelConfig = {
  provider: "llama_cpp",
  model_path: "",
  context_window: 4096,
  temperature: 0.2,
  max_tokens: 768,
  gemini_model: "gemini-3.6-flash",
  gemini_api_key: "",
  api_key_configured: false,
};

function newConversationId(): string {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `conversation-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function App() {
  const [db, setDb] = useState<DatabaseConfig>(emptyDb);
  const [model, setModel] = useState<ModelConfig>(emptyModel);
  const [schema, setSchema] = useState<SchemaSnapshot | null>(null);
  const [message, setMessage] = useState("");
  const [chat, setChat] = useState<Array<{ role: "user" | "assistant"; text: string; result?: ChatResponse }>>([]);
  const [status, setStatus] = useState("Local-only RAG database assistant");
  const [busy, setBusy] = useState(false);
  const [geminiModels, setGeminiModels] = useState<string[]>(["gemini-3.6-flash"]);
  const [databases, setDatabases] = useState<string[]>([]);
  const [selectedDatabase, setSelectedDatabase] = useState("");
  const [activeDatabase, setActiveDatabase] = useState("");
  const [conversationId, setConversationId] = useState(newConversationId);

  useEffect(() => {
    void api.getActiveModel()
      .then(({ config }) => {
        setModel({ ...emptyModel, ...config, gemini_api_key: "" });
        setGeminiModels((items) => Array.from(new Set([config.gemini_model, ...items])));
        setStatus(`Active model: ${providerLabel(config.provider)}`);
      })
      .catch((error) => {
        setStatus(error instanceof Error ? error.message : "Could not load model settings");
      });
    void api.getActiveDb()
      .then(async ({ config }) => {
        if (!config) return;
        const safeConfig = { ...config, password: "" };
        setDb(safeConfig);
        setActiveDatabase(config.database);
        setSelectedDatabase(config.database);
        const result = await api.listDatabases();
        setDatabases(result.databases);
        setActiveDatabase(result.active_database);
        setSelectedDatabase(result.active_database);
      })
      .catch((error) => setStatus(error instanceof Error ? error.message : "Could not load database settings"));
  }, []);

  async function refreshDatabases() {
    const result = await api.listDatabases();
    setDatabases(result.databases);
    setActiveDatabase(result.active_database);
    setSelectedDatabase((current) => current || result.active_database);
    setStatus(`Loaded ${result.databases.length} accessible databases`);
  }

  async function activateSelectedDatabase() {
    if (!selectedDatabase) return;
    const result = await api.activateDatabase(selectedDatabase);
    setActiveDatabase(result.database);
    setDb((current) => ({ ...current, database: result.database, password: "" }));
    setConversationId(newConversationId());
    setChat([]);
    setSchema(null);
    setMessage("");
    const nextSchema = await api.getSchema();
    setSchema(nextSchema);
    setStatus(`Activated ${result.database}; started a new database conversation`);
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage() {
    const trimmed = message.trim();
    if (!trimmed) return;
    setMessage("");
    setChat((items) => [...items, { role: "user", text: trimmed }]);
    setBusy(true);
    try {
      const result = await api.chat(trimmed, conversationId);
      setChat((items) => [...items, { role: "assistant", text: result.answer, result }]);
      setStatus(`Query completed on ${result.database} with ${providerLabel(model.provider)}`);
    } catch (error) {
      const text = error instanceof Error ? error.message : "Something went wrong";
      setStatus(text);
      setChat((items) => [...items, { role: "assistant", text: `I could not complete that request: ${text}` }]);
    } finally {
      setBusy(false);
    }
  }

  async function testActiveModel() {
    await api.testModel(model);
    setStatus(`${providerLabel(model.provider)} connection works`);
  }

  async function saveActiveModel() {
    await api.saveModel(model);
    setModel((current) => ({
      ...current,
      gemini_api_key: "",
      api_key_configured: current.provider === "gemini" ? true : current.api_key_configured,
    }));
    setStatus(`${providerLabel(model.provider)} saved and activated`);
  }

  async function refreshGeminiModels() {
    const result = await api.listGoogleModels(model.gemini_api_key);
    setGeminiModels(Array.from(new Set([model.gemini_model, ...result.models])));
    setStatus(`Loaded ${result.models.length} compatible Gemini models`);
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <section className="panel">
          <div className="panel-title">
            <Database size={18} />
            <h2>Database</h2>
          </div>
          <div className="form-grid">
            <label className="field-label">
              Database provider
              <select
                aria-label="Database provider"
                value={db.db_type}
                onChange={(e) => {
                  const dbType = e.target.value as DatabaseConfig["db_type"];
                  setDb({ ...db, db_type: dbType, port: dbType === "postgresql" ? 55432 : 3306 });
                }}
              >
                <option value="postgresql">PostgreSQL</option>
                <option value="mysql">MySQL / MariaDB</option>
              </select>
            </label>
            <input value={db.host} onChange={(e) => setDb({ ...db, host: e.target.value })} placeholder="Host" />
            <input type="number" value={db.port} onChange={(e) => setDb({ ...db, port: Number(e.target.value) })} />
            <input aria-label="Manual database name" value={db.database} onChange={(e) => setDb({ ...db, database: e.target.value })} placeholder="Database for manual connection" />
            <input value={db.username} onChange={(e) => setDb({ ...db, username: e.target.value })} placeholder="Username" />
            <input type="password" value={db.password} onChange={(e) => setDb({ ...db, password: e.target.value })} placeholder="Password" />
            <label className="check-row">
              <input type="checkbox" checked={db.ssl} onChange={(e) => setDb({ ...db, ssl: e.target.checked })} />
              SSL
            </label>
          </div>
          <label className="field-label">
            Active database
            <select aria-label="Active database" value={selectedDatabase} onChange={(e) => setSelectedDatabase(e.target.value)}>
              {!selectedDatabase && <option value="">Select a database</option>}
              {databases.map((name) => <option value={name} key={name}>{name}</option>)}
            </select>
          </label>
          <div className="button-row database-actions">
            <button className="secondary-button" onClick={() => run(refreshDatabases)} disabled={busy}>
              <RefreshCw size={16} /> Refresh
            </button>
            <button onClick={() => run(activateSelectedDatabase)} disabled={busy || !selectedDatabase}>
              <Database size={16} /> Activate
            </button>
          </div>
          <div className="button-row">
            <button onClick={() => run(async () => { await api.testDb(db); setStatus(`${databaseProviderLabel(db.db_type)} connection works`); })} disabled={busy}>
              <Play size={16} /> Test
            </button>
            <button onClick={() => run(async () => { await api.saveDb(db); setStatus(`${databaseProviderLabel(db.db_type)} config saved`); await refreshDatabases(); })} disabled={busy}>
              <Save size={16} /> Save
            </button>
          </div>
        </section>

        <section className="panel">
          <div className="panel-title">
            <Settings size={18} />
            <h2>Model</h2>
          </div>
          <label className="field-label">
            Provider
            <select
              aria-label="Model provider"
              value={model.provider}
              onChange={(e) => setModel({ ...model, provider: e.target.value as ModelConfig["provider"] })}
            >
              <option value="llama_cpp">Local GGUF</option>
              <option value="gemini">Google Gemini</option>
            </select>
          </label>

          {model.provider === "llama_cpp" ? (
            <>
              <label className="field-label">
                GGUF model path
                <input value={model.model_path} onChange={(e) => setModel({ ...model, model_path: e.target.value })} placeholder="D:\\models\\qwen.gguf" />
              </label>
              <div className="two-col">
                <label className="field-label">Context window<input type="number" min={512} value={model.context_window} onChange={(e) => setModel({ ...model, context_window: Number(e.target.value) })} /></label>
                <label className="field-label">Max tokens<input type="number" min={64} value={model.max_tokens} onChange={(e) => setModel({ ...model, max_tokens: Number(e.target.value) })} /></label>
              </div>
            </>
          ) : (
            <>
              <label className="field-label">
                Gemini API key
                <input
                  aria-label="Gemini API key"
                  type="password"
                  value={model.gemini_api_key}
                  onChange={(e) => setModel({ ...model, gemini_api_key: e.target.value })}
                  placeholder={model.api_key_configured ? "Saved key — leave blank to keep it" : "Enter a restricted Gemini API key"}
                  autoComplete="off"
                />
              </label>
              <label className="field-label">
                Gemini model
                <input
                  aria-label="Gemini model"
                  list="gemini-model-options"
                  value={model.gemini_model}
                  onChange={(e) => setModel({ ...model, gemini_model: e.target.value })}
                />
                <datalist id="gemini-model-options">
                  {geminiModels.map((name) => <option value={name} key={name} />)}
                </datalist>
              </label>
              <div className="two-col">
                <label className="field-label">Temperature<input type="number" min={0} max={2} step={0.1} value={model.temperature} onChange={(e) => setModel({ ...model, temperature: Number(e.target.value) })} /></label>
                <label className="field-label">Max tokens<input type="number" min={64} value={model.max_tokens} onChange={(e) => setModel({ ...model, max_tokens: Number(e.target.value) })} /></label>
              </div>
              <button className="secondary-button" onClick={() => run(refreshGeminiModels)} disabled={busy}>
                <RefreshCw size={16} /> Refresh Models
              </button>
              <div className="cloud-notice">
                <Cloud size={17} />
                <p>
                  Gemini receives your question, recent chat, and schema metadata—not credentials or result rows.
                  Unpaid API content may be used by Google to improve products; paid-service content is not.
                  {" "}<a href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noreferrer">Terms</a>
                </p>
              </div>
            </>
          )}
          <div className="button-row">
            <button onClick={() => run(testActiveModel)} disabled={busy}>
              <Play size={16} /> Test {model.provider === "gemini" ? "API" : "Model"}
            </button>
            <button onClick={() => run(saveActiveModel)} disabled={busy}>
              <Save size={16} /> Save &amp; Activate
            </button>
          </div>
        </section>

        <section className="panel schema-panel">
          <div className="panel-title">
            <Database size={18} />
            <h2>Schema</h2>
          </div>
          <button onClick={() => run(async () => { const next = await api.getSchema(); setSchema(next); setStatus(`Loaded ${next.tables.length} tables`); })} disabled={busy}>
            <Play size={16} /> Load Schema
          </button>
          <div className="schema-list">
            {schema?.tables.map((table) => (
              <details key={table.name}>
                <summary>{table.name} <small>{table.object_type}</small></summary>
                {table.columns.map((column) => (
                  <p key={column.name}>{column.name} <span>{column.type}</span></p>
                ))}
              </details>
            ))}
          </div>
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>RAG DB Chatbot</h1>
            <p>{status}</p>
          </div>
          <div className="provider-status">
            {activeDatabase && <span className="database-badge">DB: {activeDatabase}</span>}
            <span>{providerLabel(model.provider)}</span><Bot size={30} />
          </div>
        </header>

        <section className="chat-window">
          {chat.length === 0 && (
            <div className="empty-state">
              <h2>Ask in Bangla, English, Banglish, or mixed language.</h2>
              <p>Example: last month er top customer sales dekhao</p>
            </div>
          )}
          {chat.map((item, index) => (
            <article className={`message ${item.role}`} key={`${item.role}-${index}`}>
              <p>{item.text}</p>
              {item.result && <ResultPreview result={item.result} />}
            </article>
          ))}
        </section>

        <footer className="composer">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void sendMessage();
              }
            }}
            placeholder="Ask in Bangla, English, Banglish, or mixed language"
          />
          <button onClick={() => void sendMessage()} disabled={busy}>
            <Send size={18} />
          </button>
        </footer>
      </section>
    </main>
  );
}

function ResultPreview({ result }: { result: ChatResponse }) {
  return (
    <div className="result-preview">
      {result.sql && <pre>{result.sql}</pre>}
      {result.rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>{result.columns.map((column) => <th key={column}>{column}</th>)}</tr>
            </thead>
            <tbody>
              {result.rows.map((row, index) => (
                <tr key={index}>
                  {result.columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="download-row">
        {result.csv_url && <a href={api.reportUrl(result.csv_url)}><Download size={15} /> CSV</a>}
        {result.excel_url && <a href={api.reportUrl(result.excel_url)}><Download size={15} /> Excel</a>}
      </div>
    </div>
  );
}

function providerLabel(provider: ModelConfig["provider"]): string {
  return provider === "gemini" ? "Google Gemini" : "Local GGUF";
}

function databaseProviderLabel(provider: DatabaseConfig["db_type"]): string {
  return provider === "postgresql" ? "PostgreSQL" : "MySQL";
}

export { App, providerLabel };

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(<App />);
}
