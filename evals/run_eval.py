from __future__ import annotations

import json
from pathlib import Path

from src.graph import invoke_graph


def main() -> None:
    cases = [json.loads(line) for line in Path(__file__).with_name("golden_dataset.jsonl").read_text().splitlines()]
    passed = 0
    failures: list[str] = []
    for case in cases:
        result = invoke_graph(case["query"])
        task_ok = result.get("task_type") == case["expected_task"]
        review_ok = result.get("need_human_review") is case["human_review"]
        if task_ok and review_ok:
            passed += 1
        else:
            failures.append(f"{case['id']}: got={result.get('task_type')}/{result.get('need_human_review')}")
    print(f"Golden Dataset: {passed}/{len(cases)} passed")
    if failures:
        print("\n".join(failures))


if __name__ == "__main__":
    main()
