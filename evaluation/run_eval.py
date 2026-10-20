#!/usr/bin/env python3
"""Benchmark the three models on one document and write a results table.

Usage (backend must be running):
    python evaluation/run_eval.py --pdf path/to/document.pdf
    python evaluation/run_eval.py --pdf doc.pdf --judge        # also grade answers with an LLM
    python evaluation/run_eval.py --session SESSION_ID         # reuse an already-indexed session

Metrics per model:
  * latency (median / mean, seconds, measured end to end)
  * keyword score   - share of `expected_keywords` found in the answer (cheap, objective)
  * refusal rate    - for `expect_refusal` questions, how often the model admits the
                      document doesn't contain the answer (a keyword heuristic)
  * judge score     - optional 1-5 grade from an LLM ("--judge"); use it as a rough signal
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
REFUSAL_HINTS = (
    "does not contain", "doesn't contain", "does not mention", "doesn't mention",
    "not mentioned", "no information", "not provided", "cannot find", "can't find",
    "couldn't find", "could not find", "not in the document", "not covered",
    "not available in", "isn't in", "is not in", "unable to find", "no mention",
    "not specified", "does not say", "doesn't say", "not address",
)


def load_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    for path in (ROOT / "backend" / ".env", ROOT / ".env"):
        if path.is_file():
            for line in path.read_text().splitlines():
                line = line.split("#", 1)[0].strip()
                if "=" in line:
                    key, _, value = line.partition("=")
                    values[key.strip()] = value.strip().strip("\"'")
    return values


def keyword_score(answer: str, keywords: list[str]) -> float | None:
    if not keywords:
        return None
    lowered = answer.lower()
    return sum(1 for word in keywords if word.lower() in lowered) / len(keywords)


def looks_like_refusal(answer: str) -> bool:
    lowered = answer.lower()
    return any(hint in lowered for hint in REFUSAL_HINTS)


def judge(client: httpx.Client, env: dict[str, str], question: str, answer: str, context: str, model: str) -> int | None:
    """Ask an LLM to grade groundedness and helpfulness from 1 to 5."""
    prompt = (
        "You are grading an answer from a retrieval-augmented assistant.\n"
        f"QUESTION: {question}\n\nSOURCE PASSAGES:\n{context[:6000]}\n\nANSWER:\n{answer[:3000]}\n\n"
        "Score 1-5: 5 = correct, grounded in the passages, complete; 3 = partly right or vague; "
        "1 = wrong, invented, or ignores the passages. If the passages do not contain the answer, "
        "the best answer says so. Reply with only a JSON object like {\"score\": 4}."
    )
    try:
        response = client.post(
            env["LLM_BASE_URL"].rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {env['LLM_API_KEY']}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0},
            timeout=60,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"] or ""
        match = re.search(r'"score"\s*:\s*([1-5])', text)
        return int(match.group(1)) if match else None
    except Exception as exc:  # noqa: BLE001 - a failed judge call must not abort the run
        print(f"  judge failed: {exc}", file=sys.stderr)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--pdf", type=Path, help="PDF to index for the benchmark")
    parser.add_argument("--session", help="Use an existing session instead of uploading a PDF")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation" / "test_questions.json")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "eval_results.md")
    parser.add_argument("--judge", action="store_true", help="Grade answers with an LLM (needs LLM_API_KEY in .env)")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between requests (free tiers have rate limits)")
    parser.add_argument("--keep", action="store_true", help="Don't delete the temporary session afterwards")
    args = parser.parse_args()

    if not args.pdf and not args.session:
        parser.error("pass --pdf or --session")
    questions = json.loads(args.questions.read_text())["questions"]
    if any("REPLACE" in q["question"] for q in questions):
        parser.error(f"{args.questions} still has placeholder questions. Edit it first.")

    env = load_env_file()
    if args.judge and not (env.get("LLM_API_KEY") and env.get("LLM_BASE_URL")):
        parser.error("--judge needs LLM_API_KEY and LLM_BASE_URL in .env")

    api = args.api.rstrip("/")
    with httpx.Client(timeout=300) as client:
        models = client.get(f"{api}/models").raise_for_status().json()["models"]
        session = args.session
        created = False
        if args.pdf:
            session = f"eval-{uuid.uuid4().hex[:8]}"
            print(f"Indexing {args.pdf.name} into session {session} ...")
            with args.pdf.open("rb") as handle:
                client.post(f"{api}/ingest/pdf", files={"file": (args.pdf.name, handle, "application/pdf")},
                            data={"session_id": session}).raise_for_status()
            created = True

        results: dict[str, list[dict]] = {model: [] for model in models}
        for number, item in enumerate(questions, start=1):
            for model in models:
                print(f"[{number}/{len(questions)}] {model}: {item['question'][:60]}")
                started = time.perf_counter()
                row: dict = {"question": item["question"], "error": None, "answer": "", "latency": None}
                try:
                    response = client.post(f"{api}/chat", json={"session_id": session, "question": item["question"], "model": model})
                    row["latency"] = time.perf_counter() - started
                    if response.status_code != 200:
                        row["error"] = f"HTTP {response.status_code}: {response.text[:120]}"
                    else:
                        body = response.json()
                        row["answer"] = body["answer"]
                        row["keyword"] = keyword_score(body["answer"], item.get("expected_keywords", []))
                        if item.get("expect_refusal"):
                            row["refused"] = looks_like_refusal(body["answer"])
                        if args.judge:
                            context = "\n---\n".join(s.get("snippet") or "" for s in body["sources"])
                            row["judge"] = judge(client, env, item["question"], body["answer"], context, env.get("DEFAULT_LLM_MODEL", model))
                except httpx.HTTPError as exc:
                    row["error"] = str(exc)
                results[model].append(row)
                time.sleep(args.delay)

        if created and not args.keep:
            client.delete(f"{api}/sessions/{session}")

    # ---- report
    lines = [
        "# Evaluation results",
        "",
        f"Document: `{args.pdf.name if args.pdf else args.session}` · {len(questions)} questions · generated {time.strftime('%Y-%m-%d')}",
        "",
        "| Model | Median latency | Mean latency | Keyword score | Refusal rate | " + ("Judge (1-5) | " if args.judge else "") + "Errors |",
        "|---|---|---|---|---|" + ("---|" if args.judge else "") + "---|",
    ]
    for model, rows in results.items():
        latencies = [r["latency"] for r in rows if r["latency"] is not None and not r["error"]]
        keywords = [r["keyword"] for r in rows if r.get("keyword") is not None]
        refusals = [r["refused"] for r in rows if "refused" in r]
        judged = [r["judge"] for r in rows if r.get("judge")]
        cells = [
            f"`{model}`",
            f"{statistics.median(latencies):.1f}s" if latencies else "n/a",
            f"{statistics.mean(latencies):.1f}s" if latencies else "n/a",
            f"{statistics.mean(keywords):.0%}" if keywords else "n/a",
            f"{sum(refusals)}/{len(refusals)}" if refusals else "n/a",
        ]
        if args.judge:
            cells.append(f"{statistics.mean(judged):.2f}" if judged else "n/a")
        cells.append(str(sum(1 for r in rows if r["error"])))
        lines.append("| " + " | ".join(cells) + " |")

    lines += ["", "Keyword score = share of expected keywords found in the answer. Refusal rate = how often the model said the document "
              "doesn't contain the answer on questions where it shouldn't (keyword heuristic). Small samples: treat differences as "
              "indicative, not conclusive.", "", "## Per-question answers", ""]
    for index, item in enumerate(questions):
        lines.append(f"### {index + 1}. {item['question']}")
        for model in models:
            row = results[model][index]
            text = row["error"] or row["answer"].strip().replace("\n", " ")
            lines.append(f"- **{model}**: {text[:400]}")
        lines.append("")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
