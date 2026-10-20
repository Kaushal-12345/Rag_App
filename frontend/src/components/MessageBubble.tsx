import { shortModelName } from "@/lib/api";
import type { ChatItem } from "@/hooks/useChat";
import { CitationList } from "./CitationList";
import { Markdown } from "./Markdown";

export function Timing({ latencyMs, firstTokenMs }: { latencyMs?: number; firstTokenMs?: number | null }) {
  if (latencyMs == null) return null;
  return (
    <span className="text-xs text-neutral-500">
      {(latencyMs / 1000).toFixed(1)}s total
      {firstTokenMs != null && ` · first token ${(firstTokenMs / 1000).toFixed(1)}s`}
    </span>
  );
}

export function MessageBubble({ item }: { item: Extract<ChatItem, { kind: "user" | "assistant" }> }) {
  if (item.kind === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-[15px] text-white">
          {item.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[92%] rounded-2xl rounded-bl-md border border-neutral-200 bg-white px-4 py-3 dark:border-neutral-800 dark:bg-neutral-900">
        <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
          <span className="rounded bg-neutral-100 px-1.5 py-0.5 font-medium dark:bg-neutral-800">
            {shortModelName(item.model)}
          </span>
          {item.webUsed && <span className="rounded bg-sky-100 px-1.5 py-0.5 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">web search on</span>}
          <Timing latencyMs={item.latencyMs} firstTokenMs={item.firstTokenMs} />
        </div>
        {item.content ? (
          <Markdown>{item.content}</Markdown>
        ) : item.status === "streaming" ? (
          <p className="animate-pulse text-sm text-neutral-500">Thinking…</p>
        ) : null}
        {item.status === "streaming" && item.content && <span className="inline-block animate-pulse text-neutral-400">▍</span>}
        {item.error && (
          <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/50 dark:text-red-300">
            {item.error}
          </p>
        )}
        {item.status !== "streaming" && <CitationList sources={item.sources} />}
      </div>
    </div>
  );
}
