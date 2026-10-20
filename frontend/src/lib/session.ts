const KEY = "rag.session";

function makeId(): string {
  return crypto.randomUUID().replace(/-/g, "").slice(0, 16);
}

/** One session = one collection of documents. Stored in the browser so a refresh keeps it. */
export function getSessionId(): string {
  const existing = window.localStorage.getItem(KEY);
  if (existing) return existing;
  return resetSessionId();
}

export function resetSessionId(): string {
  const id = makeId();
  window.localStorage.setItem(KEY, id);
  return id;
}
