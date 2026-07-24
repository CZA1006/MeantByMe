from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from meantbyme.eval.models import EvaluationMode
from meantbyme.eval.runner import run_evaluation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run simulated MeantByMe quality evaluation."
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in EvaluationMode],
        default=EvaluationMode.MOCK.value,
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--gateway-url")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_evaluation(
        dataset=args.dataset,
        mode=args.mode,
        report=args.report,
        gateway_url=args.gateway_url,
    )
    print(json.dumps(result["aggregate"], ensure_ascii=False))
    return 0 if result["hard_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
