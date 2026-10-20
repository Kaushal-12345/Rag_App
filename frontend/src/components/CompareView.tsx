import { shortModelName } from "@/lib/api";
import type { ChatItem } from "@/hooks/useChat";
import { CitationList } from "./CitationList";
import { Markdown } from "./Markdown";
import { Timing } from "./MessageBubble";

export function CompareView({ item }: { item: Extract<ChatItem, { kind: "compare" }> }) {
  const models = item.models;
  const allDone = models.length > 0 && models.every((model) => item.columns[model]?.status !== "streaming");

  return (
    <div className="space-y-2">
      {item.error && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/50 dark:text-red-300">
          {item.error}
        </p>
      )}
      {models.length === 0 && !item.error && <p className="animate-pulse text-sm text-neutral-500">Searching your sources…</p>}
      <div className="grid gap-3 lg:grid-cols-3">
        {models.map((model) => {
          const column = item.columns[model];
          return (
            <div
              key={model}
              className="flex min-h-[8rem] flex-col rounded-2xl border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900"
            >
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs font-medium dark:bg-neutral-800">
                  {shortModelName(model)}
                </span>
                <Timing latencyMs={column?.latencyMs} firstTokenMs={column?.firstTokenMs} />
              </div>
              {column?.text ? (
                <Markdown>{column.text}</Markdown>
              ) : column?.status === "streaming" ? (
                <p className="animate-pulse text-sm text-neutral-500">Thinking…</p>
              ) : null}
              {column?.error && (
                <p className="mt-2 rounded-md bg-red-50 px-2 py-1.5 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300">
                  {column.error}
                </p>
              )}
            </div>
          );
        })}
      </div>
      {allDone && (
        <div className="rounded-2xl border border-neutral-200 bg-white px-4 py-3 dark:border-neutral-800 dark:bg-neutral-900">
          <CitationList sources={item.sources} />
        </div>
      )}
    </div>
  );
}
