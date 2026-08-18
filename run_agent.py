#!/usr/bin/env python3
from __future__ import annotations

from src.graph import invoke_graph


def main() -> None:
    print("🤖 金融多智能体系统已启动，输入 exit 退出。")
    while True:
        try:
            query = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            return
        if query.lower() in {"exit", "quit", "q"}:
            print("再见！")
            return
        if not query:
            continue
        result = invoke_graph(query)
        print(f"\nAgent: {result.get('final_report', '')}")
        print(f"\n[任务类型: {result.get('task_type')}; 执行链路: {' -> '.join(result.get('trace', []))}]")


if __name__ == "__main__":
    main()
