from __future__ import annotations

import argparse
import json

from src.models.register import (
    get_registry_state,
    promote_model_version,
    rollback_production_model,
    set_mlflow_registered_model_alias,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Operate the local and optional MLflow model registry.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Print local registry state.")

    promote = subparsers.add_parser("promote", help="Promote a local registry version to Production.")
    promote.add_argument("version", help="Local registry version, for example v2.")
    promote.add_argument("--sync-mlflow-alias", action="store_true")

    rollback = subparsers.add_parser("rollback", help="Rollback Production to an existing local registry version.")
    rollback.add_argument("version", help="Local registry version, for example v1.")
    rollback.add_argument("--sync-mlflow-alias", action="store_true")

    alias = subparsers.add_parser("set-mlflow-alias", help="Point an MLflow alias to a registered model version.")
    alias.add_argument("version", help="MLflow registered model version number.")
    alias.add_argument("--alias", default=None)
    alias.add_argument("--model-name", default=None)

    args = parser.parse_args()

    if args.command == "status":
        result = get_registry_state()
    elif args.command == "promote":
        result = promote_model_version(args.version)
        if args.sync_mlflow_alias:
            result["mlflow_alias"] = set_mlflow_registered_model_alias(args.version.lstrip("v"))
    elif args.command == "rollback":
        result = rollback_production_model(args.version)
        if args.sync_mlflow_alias:
            result["mlflow_alias"] = set_mlflow_registered_model_alias(args.version.lstrip("v"))
    else:
        result = set_mlflow_registered_model_alias(args.version, alias=args.alias, model_name=args.model_name)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
