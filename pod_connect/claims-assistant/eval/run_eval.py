"""Scores the assistant against eval/cases.json. Exit code 1 if accuracy is below the threshold.

Usage:
  python -m eval.run_eval                 # uses LLM_PROVIDER (default offline)
  python -m eval.run_eval --threshold 0.95
Run this in CI so a prompt, model, or knowledge change that lowers accuracy fails the build.
"""
import argparse
import json
import sys
from pathlib import Path

from app.agent import ClaimsAssistant


def run(threshold: float) -> int:
    cases = json.loads((Path(__file__).parent / "cases.json").read_text())
    assistant = ClaimsAssistant()
    print(f"LLM backend: {assistant.llm.provider} ({assistant.llm.model})\n")
    passed = 0
    for c in cases:
        r = assistant.ask(c["member"], c["question"])
        text = r.answer.lower()
        problems = [f"missing '{s}'" for s in c["must_include"] if s.lower() not in text]
        problems += [f"contains '{s}'" for s in c["must_not_include"] if s.lower() in text]
        if r.escalate != c["escalate"]:
            problems.append(f"escalate={r.escalate}, expected {c['escalate']}")
        ok = not problems
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {c['id']:<22} {'; '.join(problems)}")
    score = passed / len(cases)
    print(f"\n{passed}/{len(cases)} passed  ({score:.0%}), threshold {threshold:.0%}")
    return 0 if score >= threshold else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=1.0)
    sys.exit(run(ap.parse_args().threshold))
