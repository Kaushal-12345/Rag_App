"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatItem } from "@/hooks/useChat";
import { CompareView } from "./CompareView";
import { MessageBubble } from "./MessageBubble";

type Props = {
  items: ChatItem[];
  busy: boolean;
  hasSources: boolean;
  onSend: (question: string) => void;
  onStop: () => void;
};

const SUGGESTIONS = ["Summarize this in 5 bullet points", "What are the key takeaways?", "What topics does it cover?"];

export function ChatWindow({ items, busy, hasSources, onSend, onStop }: Props) {
  const [draft, setDraft] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [items]);

  function submit(event?: React.FormEvent) {
    event?.preventDefault();
    if (!draft.trim() || busy) return;
    onSend(draft);
    setDraft("");
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-6">
        {items.length === 0 && (
          <div className="mx-auto mt-16 max-w-md text-center">
            <h2 className="text-lg font-semibold">Ask anything about your sources</h2>
            <p className="mt-1 text-sm text-neutral-500">
              {hasSources
                ? "Answers cite the exact page or video timestamp they came from."
                : "Add a PDF or a YouTube link on the left to get started."}
            </p>
            {hasSources && (
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((text) => (
                  <button
                    key={text}
                    onClick={() => onSend(text)}
                    className="rounded-full border border-neutral-300 px-3 py-1.5 text-sm hover:border-indigo-400 dark:border-neutral-700"
                  >
                    {text}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        {items.map((item) =>
          item.kind === "compare" ? <CompareView key={item.id} item={item} /> : <MessageBubble key={item.id} item={item} />,
        )}
        <div ref={bottom} />
      </div>

      <form onSubmit={submit} className="border-t border-neutral-200 p-3 dark:border-neutral-800">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) submit(event);
            }}
            rows={1}
            placeholder={hasSources ? "Ask a question…" : "Add a source first"}
            disabled={!hasSources}
            className="max-h-40 min-h-[2.75rem] flex-1 resize-none rounded-xl border border-neutral-300 bg-white px-3 py-2.5 text-[15px] outline-none focus:border-indigo-500 disabled:opacity-60 dark:border-neutral-700 dark:bg-neutral-900"
          />
          {busy ? (
            <button
              type="button"
              onClick={onStop}
              className="h-11 rounded-xl bg-neutral-800 px-4 text-sm font-medium text-white hover:bg-neutral-700 dark:bg-neutral-200 dark:text-neutral-900"
            >
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!draft.trim() || !hasSources}
              className="h-11 rounded-xl bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              Send
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
