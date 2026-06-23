from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.monitoring.production import run_production_drift_detection


def main() -> None:
    parser = argparse.ArgumentParser(description="Run drift detection against FastAPI prediction logs.")
    parser.add_argument("--log-path", default=None)
    parser.add_argument("--reference-path", default=None)
    parser.add_argument("--report-path", default=None)
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()

    result = run_production_drift_detection(
        log_path=Path(args.log_path) if args.log_path else None,
        reference_path=Path(args.reference_path) if args.reference_path else None,
        report_path=Path(args.report_path) if args.report_path else None,
        threshold=args.threshold,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
