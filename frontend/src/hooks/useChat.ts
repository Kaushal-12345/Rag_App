"use client";

import { useCallback, useRef, useState } from "react";
import { streamEvents, type Citation, type HistoryMessage, type StreamEvent } from "@/lib/api";

export type Column = {
  text: string;
  status: "streaming" | "done" | "error";
  error?: string;
  latencyMs?: number;
  firstTokenMs?: number | null;
};

export type ChatItem =
  | { kind: "user"; id: string; content: string }
  | {
      kind: "assistant";
      id: string;
      model: string;
      content: string;
      sources: Citation[];
      webUsed: boolean;
      status: "streaming" | "done" | "error";
      error?: string;
      latencyMs?: number;
      firstTokenMs?: number | null;
    }
  | {
      kind: "compare";
      id: string;
      question: string;
      models: string[];
      sources: Citation[];
      webUsed: boolean;
      columns: Record<string, Column>;
      error?: string;
    };

export type SendOptions = {
  sessionId: string;
  model: string;
  webSearch: boolean;
  compare: boolean;
};

const uid = () => Math.random().toString(36).slice(2, 10);

export function useChat() {
  const [items, setItems] = useState<ChatItem[]>([]);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const itemsRef = useRef<ChatItem[]>([]);
  itemsRef.current = items;

  const patch = useCallback((id: string, update: (item: ChatItem) => ChatItem) => {
    setItems((prev) => prev.map((item) => (item.id === id ? update(item) : item)));
  }, []);

  const buildHistory = (): HistoryMessage[] =>
    itemsRef.current
      .filter(
        (item) => item.kind === "user" || (item.kind === "assistant" && item.status === "done" && item.content),
      )
      .map((item) => ({
        role: item.kind === "user" ? "user" : "assistant",
        content: item.kind === "user" || item.kind === "assistant" ? item.content : "",
      }));

  const send = useCallback(
    async (question: string, options: SendOptions) => {
      const text = question.trim();
      if (!text || busy) return;

      const history = buildHistory();
      const controller = new AbortController();
      abortRef.current = controller;
      setBusy(true);

      const replyId = uid();
      const userItem: ChatItem = { kind: "user", id: uid(), content: text };

      if (options.compare) {
        setItems((prev) => [
          ...prev,
          userItem,
          { kind: "compare", id: replyId, question: text, models: [], sources: [], webUsed: false, columns: {} },
        ]);
      } else {
        setItems((prev) => [
          ...prev,
          userItem,
          {
            kind: "assistant",
            id: replyId,
            model: options.model,
            content: "",
            sources: [],
            webUsed: false,
            status: "streaming",
          },
        ]);
      }

      const onSingleEvent = (event: StreamEvent) => {
        patch(replyId, (item) => {
          if (item.kind !== "assistant") return item;
          switch (event.type) {
            case "meta":
              return { ...item, sources: event.sources, webUsed: event.web_used, model: event.model ?? item.model };
            case "token":
              return { ...item, content: item.content + event.text };
            case "done":
              return { ...item, status: "done", latencyMs: event.latency_ms, firstTokenMs: event.first_token_ms };
            case "error":
              return { ...item, status: "error", error: event.message };
            default:
              return item;
          }
        });
      };

      const onCompareEvent = (event: StreamEvent) => {
        patch(replyId, (item) => {
          if (item.kind !== "compare") return item;
          if (event.type === "meta") {
            const columns: Record<string, Column> = {};
            for (const model of event.models ?? []) columns[model] = { text: "", status: "streaming" };
            return { ...item, models: event.models ?? [], sources: event.sources, webUsed: event.web_used, columns };
          }
          if (event.type === "error" && !event.model) return { ...item, error: event.message };
          if (event.type !== "token" && event.type !== "done" && event.type !== "error") return item;
          const model = event.model as string;
          const column = item.columns[model] ?? { text: "", status: "streaming" };
          let next: Column = column;
          if (event.type === "token") next = { ...column, text: column.text + event.text };
          if (event.type === "done")
            next = { ...column, status: "done", latencyMs: event.latency_ms, firstTokenMs: event.first_token_ms };
          if (event.type === "error") next = { ...column, status: "error", error: event.message };
          return { ...item, columns: { ...item.columns, [model]: next } };
        });
      };

      const finishStuck = () =>
        patch(replyId, (item) => {
          if (item.kind === "assistant" && item.status === "streaming")
            return { ...item, status: item.content ? "done" : "error", error: item.content ? undefined : "Stopped." };
          if (item.kind === "compare") {
            const columns = Object.fromEntries(
              Object.entries(item.columns).map(([model, col]) => [
                model,
                col.status === "streaming" ? { ...col, status: col.text ? "done" : "error" } : col,
              ]),
            ) as Record<string, Column>;
            return { ...item, columns };
          }
          return item;
        });

      try {
        const body = {
          session_id: options.sessionId,
          question: text,
          web_search: options.webSearch,
          history,
          ...(options.compare ? {} : { model: options.model }),
        };
        await streamEvents(
          options.compare ? "/chat/compare" : "/chat/stream",
          body,
          options.compare ? onCompareEvent : onSingleEvent,
          controller.signal,
        );
      } catch (error) {
        const message = (error as Error).message;
        patch(replyId, (item) =>
          item.kind === "assistant"
            ? { ...item, status: "error", error: message }
            : item.kind === "compare"
              ? { ...item, error: message }
              : item,
        );
      } finally {
        finishStuck();
        setBusy(false);
        abortRef.current = null;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [busy, patch],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);
  const clear = useCallback(() => setItems([]), []);

  return { items, busy, send, stop, clear };
}
