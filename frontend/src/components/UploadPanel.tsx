"use client";

import { useRef, useState } from "react";
import { ingestPdf, ingestYoutube } from "@/lib/api";

type Props = {
  sessionId: string;
  onIngested: () => void;
};

export function UploadPanel({ sessionId, onIngested }: Props) {
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [link, setLink] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  async function run(label: string, task: () => Promise<{ filename: string; chunks: number }>) {
    setWorking(true);
    setError(null);
    setStatus(label);
    try {
      const result = await task();
      setStatus(`Added “${result.filename}” (${result.chunks} passages)`);
      onIngested();
    } catch (err) {
      setStatus(null);
      setError((err as Error).message);
    } finally {
      setWorking(false);
    }
  }

  function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are supported.");
      return;
    }
    void run(`Reading ${file.name}… the first upload can take a few minutes while the embedding model downloads.`, () =>
      ingestPdf(file, sessionId),
    );
  }

  function handleLink(event: React.FormEvent) {
    event.preventDefault();
    const url = link.trim();
    if (!url) return;
    void run("Fetching the transcript…", () => ingestYoutube(url, sessionId)).then(() => setLink(""));
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          handleFiles(event.dataTransfer.files);
        }}
        onClick={() => !working && fileInput.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-5 text-center text-sm transition ${
          dragging
            ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30"
            : "border-neutral-300 hover:border-indigo-400 dark:border-neutral-700"
        } ${working ? "pointer-events-none opacity-60" : ""}`}
      >
        <p className="font-medium">Drop a PDF here</p>
        <p className="text-neutral-500">or click to browse</p>
        <input
          ref={fileInput}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={(event) => {
            handleFiles(event.target.files);
            event.target.value = "";
          }}
        />
      </div>

      <form onSubmit={handleLink} className="flex gap-2">
        <input
          value={link}
          onChange={(event) => setLink(event.target.value)}
          placeholder="Paste a YouTube link"
          disabled={working}
          className="min-w-0 flex-1 rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500 dark:border-neutral-700 dark:bg-neutral-900"
        />
        <button
          type="submit"
          disabled={working || !link.trim()}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          Add
        </button>
      </form>

      {working && status && <p className="animate-pulse text-xs text-neutral-500">{status}</p>}
      {!working && status && <p className="text-xs text-emerald-600 dark:text-emerald-400">{status}</p>}
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300">{error}</p>}
    </div>
  );
}
