"use client";

import type { SourceInfo } from "@/lib/api";

type Props = {
  sources: SourceInfo[];
  onDelete: (sourceId: string) => void;
};

export function SourceList({ sources, onDelete }: Props) {
  if (sources.length === 0) {
    return <p className="text-sm text-neutral-500">No sources yet. Add a PDF or a YouTube link to start.</p>;
  }
  return (
    <ul className="space-y-1.5">
      {sources.map((source) => (
        <li
          key={source.source_id}
          className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm dark:border-neutral-800 dark:bg-neutral-900"
        >
          <span aria-hidden>{source.source_type === "youtube" ? "▶" : "📄"}</span>
          <div className="min-w-0 flex-1">
            {source.url ? (
              <a href={source.url} target="_blank" rel="noreferrer" className="block truncate hover:underline" title={source.source}>
                {source.source}
              </a>
            ) : (
              <p className="truncate" title={source.source}>
                {source.source}
              </p>
            )}
            <p className="text-xs text-neutral-500">{source.chunks} passages</p>
          </div>
          <button
            onClick={() => onDelete(source.source_id)}
            className="rounded px-1.5 py-0.5 text-neutral-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40"
            aria-label={`Remove ${source.source}`}
            title="Remove"
          >
            ✕
          </button>
        </li>
      ))}
    </ul>
  );
}
