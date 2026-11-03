import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const activeLocalConfig = {
  provider: "llama_cpp" as const,
  model_path: "C:/models/local.gguf",
  context_window: 4096,
  temperature: 0.2,
  max_tokens: 768,
  gemini_model: "gemini-3.6-flash",
  gemini_api_key: "",
  api_key_configured: false,
};

const apiMock = vi.hoisted(() => ({
  getActiveModel: vi.fn(),
  testModel: vi.fn(),
  saveModel: vi.fn(),
  listGoogleModels: vi.fn(),
  testDb: vi.fn(),
  saveDb: vi.fn(),
  getActiveDb: vi.fn(),
  listDatabases: vi.fn(),
  activateDatabase: vi.fn(),
  getSchema: vi.fn(),
  chat: vi.fn(),
  reportUrl: vi.fn((path: string) => path),
}));

vi.mock("./api/client", () => ({ api: apiMock }));

import { App } from "./main";

describe("model provider panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.getActiveModel.mockResolvedValue({ config: activeLocalConfig });
    apiMock.testModel.mockResolvedValue({ ok: true });
    apiMock.saveModel.mockResolvedValue({ ok: true, provider: "gemini" });
    apiMock.listGoogleModels.mockResolvedValue({ models: ["gemini-3.6-flash", "gemini-3.5-flash-lite"] });
    apiMock.getActiveDb.mockResolvedValue({ config: null });
    apiMock.listDatabases.mockResolvedValue({ databases: [], active_database: "" });
    apiMock.activateDatabase.mockResolvedValue({ ok: true, database: "brac_microfinance_demo" });
    apiMock.getSchema.mockResolvedValue({ database: "brac_microfinance_demo", tables: [] });
  });

  it("switches to Gemini and tests the entered key", async () => {
    render(<App />);
    const provider = await screen.findByLabelText("Model provider");

    fireEvent.change(provider, { target: { value: "gemini" } });
    const keyInput = screen.getByLabelText("Gemini API key");
    fireEvent.change(keyInput, { target: { value: "test-key" } });
    fireEvent.click(screen.getByRole("button", { name: "Test API" }));

    await waitFor(() => expect(apiMock.testModel).toHaveBeenCalled());
    expect(apiMock.testModel.mock.calls[0][0]).toMatchObject({
      provider: "gemini",
      gemini_api_key: "test-key",
    });
    expect(screen.getByText(/not credentials or result rows/i)).toBeInTheDocument();
  });

  it("loads a saved Gemini configuration without exposing its key", async () => {
    apiMock.getActiveModel.mockResolvedValueOnce({
      config: { ...activeLocalConfig, provider: "gemini", api_key_configured: true },
    });

    render(<App />);

    const keyInput = await screen.findByLabelText("Gemini API key");
    expect(keyInput).toHaveValue("");
    expect(keyInput).toHaveAttribute("placeholder", expect.stringMatching(/saved key/i));
    expect(screen.getByLabelText("Model provider")).toHaveValue("gemini");
  });

  it("loads PostgreSQL as the active database provider", async () => {
    apiMock.getActiveDb.mockResolvedValueOnce({
      config: { db_type: "postgresql", name: "docker-postgresql", host: "127.0.0.1", port: 55432, database: "brac_microfinance_demo", username: "ragdb", password: "", ssl: false },
    });
    apiMock.listDatabases.mockResolvedValueOnce({
      databases: ["brac_microfinance_demo"],
      active_database: "brac_microfinance_demo",
    });

    render(<App />);

    expect(await screen.findByLabelText("Database provider")).toHaveValue("postgresql");
    expect(screen.getByLabelText("Active database")).toHaveValue("brac_microfinance_demo");
  });

  it("activates a database and starts a clean database conversation", async () => {
    apiMock.getActiveDb.mockResolvedValueOnce({
      config: { db_type: "mysql", name: "default", host: "127.0.0.1", port: 3306, database: "company_sales_practice", username: "root", password: "", ssl: false },
    });
    apiMock.listDatabases.mockResolvedValueOnce({
      databases: ["company_sales_practice", "brac_microfinance_demo"],
      active_database: "company_sales_practice",
    });
    render(<App />);

    const selector = await screen.findByLabelText("Active database");
    await waitFor(() => expect(selector).toHaveValue("company_sales_practice"));
    fireEvent.change(selector, { target: { value: "brac_microfinance_demo" } });
    fireEvent.click(screen.getByRole("button", { name: "Activate" }));

    await waitFor(() => expect(apiMock.activateDatabase).toHaveBeenCalledWith("brac_microfinance_demo"));
    expect(await screen.findByText("DB: brac_microfinance_demo")).toBeInTheDocument();
    expect(apiMock.getSchema).toHaveBeenCalled();
  });
});
