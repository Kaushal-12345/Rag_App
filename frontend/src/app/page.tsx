"use client";

import { useCallback, useEffect, useState } from "react";
import { ChatWindow } from "@/components/ChatWindow";
import { ModelSelector } from "@/components/ModelSelector";
import { SourceList } from "@/components/SourceList";
import { Toggle } from "@/components/Toggle";
import { UploadPanel } from "@/components/UploadPanel";
import { useChat } from "@/hooks/useChat";
import { deleteSession, deleteSource, getModels, listSources, type SourceInfo } from "@/lib/api";
import { getSessionId, resetSessionId } from "@/lib/session";

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [webSearch, setWebSearch] = useState(false);
  const [compare, setCompare] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const { items, busy, send, stop, clear } = useChat();

  const refreshSources = useCallback(async (id: string) => {
    try {
      setSources(await listSources(id));
    } catch {
      /* backend errors are surfaced by the models call below */
    }
  }, []);

  useEffect(() => {
    const id = getSessionId();
    setSessionId(id);
    void refreshSources(id);
    getModels()
      .then((info) => {
        setModels(info.models);
        setModel(info.default);
      })
      .catch((error: Error) => setBackendError(error.message));
  }, [refreshSources]);

  async function handleDeleteSource(sourceId: string) {
    if (!sessionId) return;
    await deleteSource(sessionId, sourceId).catch(() => undefined);
    await refreshSources(sessionId);
  }

  async function handleNewChat() {
    if (sessionId) await deleteSession(sessionId).catch(() => undefined);
    const next = resetSessionId();
    setSessionId(next);
    setSources([]);
    clear();
  }

  const ready = sessionId !== null && model !== "";

  return (
    <div className="flex h-dvh flex-col md:flex-row">
      <aside
        className={`${panelOpen ? "block" : "hidden"} max-h-[60vh] shrink-0 overflow-y-auto border-b border-neutral-200 p-4 md:block md:max-h-none md:w-80 md:border-b-0 md:border-r dark:border-neutral-800`}
      >
        <h1 className="mb-4 text-lg font-semibold">Chat with your sources</h1>
        {sessionId && <UploadPanel sessionId={sessionId} onIngested={() => refreshSources(sessionId)} />}
        <h2 className="mb-2 mt-6 text-xs font-medium uppercase tracking-wide text-neutral-500">Your sources</h2>
        <SourceList sources={sources} onDelete={handleDeleteSource} />
        {sources.length > 0 && (
          <button onClick={handleNewChat} className="mt-4 text-xs text-neutral-500 underline hover:text-red-600">
            Clear everything and start over
          </button>
        )}
      </aside>

      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-neutral-200 px-4 py-2.5 dark:border-neutral-800">
          <button
            className="rounded-md border border-neutral-300 px-2 py-1 text-sm md:hidden dark:border-neutral-700"
            onClick={() => setPanelOpen((open) => !open)}
          >
            {panelOpen ? "Hide sources" : "Sources"}
          </button>
          <ModelSelector models={models} value={model} onChange={setModel} disabled={compare || models.length === 0} />
          <Toggle
            label="Compare models"
            checked={compare}
            onChange={setCompare}
            title="Send the same question to all three models side by side"
          />
          <Toggle
            label="Web search"
            checked={webSearch}
            onChange={setWebSearch}
            title="Add live web results alongside your documents"
          />
          {items.length > 0 && (
            <button onClick={clear} className="ml-auto text-sm text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200">
              Clear chat
            </button>
          )}
        </header>

        {backendError && (
          <p className="bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-950/50 dark:text-red-300">{backendError}</p>
        )}

        <div className="min-h-0 flex-1">
          <ChatWindow
            items={items}
            busy={busy}
            hasSources={sources.length > 0 && ready}
            onStop={stop}
            onSend={(question) =>
              sessionId && void send(question, { sessionId, model, webSearch, compare })
            }
          />
        </div>
      </main>
    </div>
  );
}
