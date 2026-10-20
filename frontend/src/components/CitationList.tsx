"use client";

import { useState } from "react";
import { formatTimestamp, type Citation } from "@/lib/api";
import { SourceViewer } from "./SourceViewer";

const chip =
  "inline-flex max-w-full items-center gap-1 rounded-full border border-neutral-300 bg-white px-2.5 py-1 text-xs text-neutral-700 hover:border-indigo-400 hover:text-indigo-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:border-indigo-500 dark:hover:text-indigo-300";

function truncate(text: string, max = 28) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export function CitationList({ sources }: { sources: Citation[] }) {
  const [open, setOpen] = useState<Citation | null>(null);
  if (sources.length === 0) return null;

  return (
    <div className="mt-3">
      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-neutral-500">Sources</p>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((citation, index) => {
          const key = `${citation.chunk_id ?? citation.url ?? citation.source}-${index}`;
          if (citation.source_type === "youtube" && citation.url) {
            return (
              <a key={key} href={citation.url} target="_blank" rel="noreferrer" className={chip} title={citation.source}>
                <span aria-hidden>▶</span>
                {truncate(citation.source)} @ {formatTimestamp(citation.start_seconds ?? 0)}
              </a>
            );
          }
          if (citation.source_type === "web" && citation.url) {
            return (
              <a key={key} href={citation.url} target="_blank" rel="noreferrer" className={chip} title={citation.source}>
                <span aria-hidden>🌐</span>
                {truncate(citation.source)}
              </a>
            );
          }
          return (
            <button key={key} onClick={() => setOpen(citation)} className={chip} title="View the passage">
              <span aria-hidden>📄</span>
              {truncate(citation.source)}
              {citation.page ? ` · p. ${citation.page}` : ""}
            </button>
          );
        })}
      </div>
      {open && <SourceViewer citation={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
