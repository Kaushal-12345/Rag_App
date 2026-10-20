"use client";

import { useEffect } from "react";
import { formatTimestamp, type Citation } from "@/lib/api";

export function SourceViewer({ citation, onClose }: { citation: Citation; onClose: () => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const location =
    citation.source_type === "pdf" && citation.page
      ? `Page ${citation.page}`
      : citation.start_seconds != null
        ? `At ${formatTimestamp(citation.start_seconds)}`
        : "Web result";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="max-h-[80vh] w-full max-w-2xl overflow-hidden rounded-xl bg-white shadow-xl dark:bg-neutral-900"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-neutral-200 p-4 dark:border-neutral-800">
          <div className="min-w-0">
            <p className="truncate font-medium">{citation.source}</p>
            <p className="text-sm text-neutral-500">
              {location}
              {citation.score != null && ` · relevance ${(citation.score * 100).toFixed(0)}%`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            Close
          </button>
        </div>
        <div className="max-h-[55vh] overflow-y-auto whitespace-pre-wrap p-4 text-sm leading-relaxed">
          {citation.snippet ?? "No preview available."}
        </div>
        {citation.url && (
          <div className="border-t border-neutral-200 p-3 text-sm dark:border-neutral-800">
            <a href={citation.url} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline dark:text-indigo-400">
              {citation.source_type === "youtube" ? "Open the video at this moment ↗" : "Open the page ↗"}
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
