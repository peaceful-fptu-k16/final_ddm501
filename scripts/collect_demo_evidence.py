from __future__ import annotations

import base64
import csv
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "demo_evidence"
DOCS_DIR = ROOT / "docs"
SCREENSHOT_DIR = DOCS_DIR / "assets" / "screenshots"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "unavailable", "reason": f"Missing file: {path}"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "unavailable", "reason": str(exc)}


def _run(args: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}


def _http_json(
    url: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
    username: str | None = None,
    password: str | None = None,
    timeout: int = 10,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "final-ddm501-evidence-collector"}
    if extra_headers:
        headers.update(extra_headers)
    if username and password:
        token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = {"text": raw}
            return {
                "status": "ok",
                "status_code": response.status,
                "body": body,
            }
    except HTTPError as exc:
        return {
            "status": "unavailable",
            "status_code": exc.code,
            "reason": exc.read().decode("utf-8", errors="replace"),
        }
    except (TimeoutError, URLError) as exc:
        return {"status": "unavailable", "status_code": None, "reason": str(exc)}


def _prometheus_query(query: str) -> dict[str, Any]:
    url = f"http://localhost:9090/api/v1/query?{urlencode({'query': query})}"
    response = _http_json(url)
    if response.get("status") != "ok":
        return response
    body = response.get("body", {})
    if body.get("status") != "success":
        return {"status": "unavailable", "reason": body}
    results = body.get("data", {}).get("result", [])
    values = []
    for result in results:
        metric = result.get("metric", {})
        value = result.get("value", [None, None])[1]
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = value
        values.append({"metric": metric, "value": parsed})
    return {"status": "ok", "values": values}


def _first_value(query_result: dict[str, Any]) -> float | None:
    values = query_result.get("values") or []
    if not values:
        return None
    value = values[0].get("value")
    return float(value) if isinstance(value, int | float) else None


def _parse_compose_ps(raw: str) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        rows = []
        for line in raw.splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows


def _collect_docker() -> dict[str, Any]:
    compose = _run(["docker", "compose", "ps", "--format", "json"])
    images = _run(["docker", "images", "--digests", "--format", "{{json .}}"])
    image_rows = []
    for line in images.get("stdout", "").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        repository = row.get("Repository", "")
        if any(token in repository.lower() for token in ["ddm", "final"]):
            image_rows.append(row)
    return {
        "compose_services": _parse_compose_ps(compose.get("stdout", "")),
        "compose_error": compose.get("stderr") if not compose.get("ok") else "",
        "images": image_rows,
    }


def _collect_postgres() -> dict[str, Any]:
    summary_sql = (
        "select count(*) as total, "
        "count(*) filter (where prediction='normal') as normal, "
        "count(*) filter (where prediction='anomaly') as anomaly, "
        "round(avg(anomaly_score)::numeric, 6) as avg_score "
        "from prediction_logs;"
    )
    risk_sql = "select risk_level, count(*) from prediction_logs group by risk_level order by risk_level;"
    psql_base = [
        "docker",
        "compose",
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "airflow",
        "-d",
        "mlops",
        "-At",
        "-F",
        ",",
        "-c",
    ]
    summary = _run([*psql_base, summary_sql])
    risk = _run([*psql_base, risk_sql])
    payload: dict[str, Any] = {"status": "unavailable", "summary_raw": summary, "risk_raw": risk}
    if summary.get("ok") and summary.get("stdout"):
        parts = summary["stdout"].splitlines()[-1].split(",")
        if len(parts) >= 4:
            payload.update(
                {
                    "status": "ok",
                    "total": int(parts[0]),
                    "normal": int(parts[1]),
                    "anomaly": int(parts[2]),
                    "avg_anomaly_score": float(parts[3]) if parts[3] else None,
                }
            )
    if risk.get("ok"):
        payload["risk_distribution"] = {
            row.split(",")[0]: int(row.split(",")[1])
            for row in risk.get("stdout", "").splitlines()
            if "," in row
        }
    return payload


def _collect_mlflow() -> dict[str, Any]:
    health = _http_json("http://localhost:5000/health")
    experiments = _http_json(
        "http://localhost:5000/api/2.0/mlflow/experiments/search",
        method="POST",
        payload={"max_results": 20},
    )
    payload: dict[str, Any] = {"health": health, "experiments": experiments}
    experiment_id = None
    for experiment in experiments.get("body", {}).get("experiments", []):
        if experiment.get("name") == "server-log-anomaly":
            experiment_id = experiment.get("experiment_id")
            break
    if experiment_id is not None:
        runs = _http_json(
            "http://localhost:5000/api/2.0/mlflow/runs/search",
            method="POST",
            payload={
                "experiment_ids": [experiment_id],
                "max_results": 5,
                "order_by": ["attributes.start_time DESC"],
            },
        )
        payload["latest_runs"] = runs
    return payload


def _collect_airflow() -> dict[str, Any]:
    health = _http_json("http://localhost:8080/health")
    dag_runs = _http_json(
        "http://localhost:8080/api/v1/dags/server_log_anomaly_retraining/dagRuns?limit=5&order_by=-start_date",
        username="admin",
        password="admin",
    )
    return {"health": health, "latest_retraining_dag_runs": dag_runs}


def _collect_github() -> dict[str, Any]:
    remote = _run(["git", "config", "--get", "remote.origin.url"])
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    commit = _run(["git", "rev-parse", "--short", "HEAD"])
    status = _run(["git", "status", "--short"])
    payload: dict[str, Any] = {
        "remote": remote.get("stdout"),
        "branch": branch.get("stdout"),
        "commit": commit.get("stdout"),
        "dirty_files": [line for line in status.get("stdout", "").splitlines() if line],
    }
    owner_repo = _github_owner_repo(remote.get("stdout", ""))
    if owner_repo:
        owner, repo = owner_repo
        payload["owner"] = owner
        payload["repo"] = repo
        actions_runs = _http_json(
            f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=5",
            timeout=15,
        )
        payload["actions_runs"] = actions_runs
        latest_run = (actions_runs.get("body", {}).get("workflow_runs") or [{}])[0]
        jobs_url = latest_run.get("jobs_url")
        if jobs_url:
            payload["latest_run_jobs"] = _http_json(jobs_url, timeout=15)
    return payload


def _github_owner_repo(remote: str) -> tuple[str, str] | None:
    patterns = [
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
        r"https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, remote)
        if match:
            return match.group("owner"), match.group("repo")
    return None


def _collect_loadtest() -> dict[str, Any]:
    stats_path = REPORT_DIR / "loadtest_stats.csv"
    if not stats_path.exists():
        return {"status": "unavailable", "reason": f"Missing file: {stats_path}"}

    with stats_path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if any(row.values())]
    aggregate = next((row for row in rows if row.get("Name") == "Aggregated"), None)
    if aggregate is None:
        return {"status": "unavailable", "reason": "Aggregated row not found", "rows": rows}

    request_count = float(aggregate.get("Request Count") or 0)
    failure_count = float(aggregate.get("Failure Count") or 0)
    failure_rate = failure_count / request_count if request_count else 0.0
    return {
        "status": "ok",
        "stats_path": str(stats_path),
        "request_count": int(request_count),
        "failure_count": int(failure_count),
        "failure_rate": round(failure_rate, 6),
        "requests_per_second": round(float(aggregate.get("Requests/s") or 0), 6),
        "p50_ms": float(aggregate.get("50%") or 0),
        "p95_ms": float(aggregate.get("95%") or 0),
        "p99_ms": float(aggregate.get("99%") or 0),
        "max_ms": float(aggregate.get("Max Response Time") or 0),
        "rows": rows,
    }


def _collect_api_evidence() -> dict[str, Any]:
    api_headers = {"X-API-Key": os.getenv("API_KEY", "local-dev-api-key")}
    return {
        "health": _http_json("http://localhost:8000/health"),
        "explain": _http_json(
            "http://localhost:8000/explain",
            method="POST",
            extra_headers=api_headers,
            payload={
                "server_id": "srv-report-01",
                "cpu_usage": 94.0,
                "memory_usage": 91.0,
                "request_count": 520,
                "error_rate": 0.32,
                "avg_latency_ms": 1700,
                "p95_latency_ms": 2600,
            },
        ),
        "drift": _http_json("http://localhost:8000/drift", method="POST", extra_headers=api_headers),
        "fairness": _http_json(
            "http://localhost:8000/fairness",
            method="POST",
            payload={},
            extra_headers=api_headers,
        ),
        "retrain_check": _http_json(
            "http://localhost:8000/retrain",
            method="POST",
            payload={"force": False, "drift_threshold": 999.0, "reload_after_train": False},
            extra_headers=api_headers,
            timeout=60,
        ),
    }


def _collect_prometheus() -> dict[str, Any]:
    queries = {
        "request_count": "api_request_count_total",
        "error_count": "api_error_count_total",
        "p95_latency_seconds": "histogram_quantile(0.95, sum(increase(api_latency_seconds_bucket[15m])) by (le))",
        "anomaly_rate": "prediction_anomaly_rate",
        "drift_score": "drift_score",
        "prediction_count_by_class": "sum(prediction_count_total) by (prediction)",
        "active_alerts": "ALERTS{alertstate=\"firing\"}",
    }
    return {name: _prometheus_query(query) for name, query in queries.items()}


def _write_bar_svg(path: Path, title: str, data: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width = 820
    height = 360
    margin_left = 180
    margin_right = 40
    bar_height = 28
    gap = 14
    max_value = max(data.values(), default=1.0) or 1.0
    rows = []
    for index, (label, value) in enumerate(data.items()):
        y = 72 + index * (bar_height + gap)
        bar_width = int((width - margin_left - margin_right) * (value / max_value))
        rows.append(
            f'<text x="24" y="{y + 20}" font-size="14" fill="#1f2937">{label}</text>'
            f'<rect x="{margin_left}" y="{y}" width="{bar_width}" height="{bar_height}" fill="#2563eb" rx="3" />'
            f'<text x="{margin_left + bar_width + 8}" y="{y + 20}" font-size="14" fill="#111827">{value:.4g}</text>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="#ffffff" />'
        f'<text x="24" y="36" font-size="22" font-family="Arial" font-weight="700" fill="#111827">{title}</text>'
        f'<g font-family="Arial">{"".join(rows)}</g></svg>'
    )
    path.write_text(svg, encoding="utf-8")


def _write_charts(evidence: dict[str, Any]) -> dict[str, str]:
    charts = {}
    prediction_counts = {}
    for item in evidence.get("prometheus", {}).get("prediction_count_by_class", {}).get("values", []):
        label = item.get("metric", {}).get("prediction", "unknown")
        prediction_counts[str(label)] = float(item.get("value", 0.0))
    if prediction_counts:
        path = REPORT_DIR / "prediction_distribution.svg"
        _write_bar_svg(path, "Prediction distribution", prediction_counts)
        charts["prediction_distribution"] = path.relative_to(ROOT).as_posix()

    explain_body = evidence.get("api", {}).get("explain", {}).get("body", {})
    feature_data = {
        item["feature"]: float(item.get("abs_impact", abs(item.get("impact", 0.0))))
        for item in explain_body.get("top_features", [])[:6]
    }
    if feature_data:
        path = REPORT_DIR / "explainability_top_features.svg"
        _write_bar_svg(path, "Top explainability impacts", feature_data)
        charts["explainability_top_features"] = path.relative_to(ROOT).as_posix()

    fairness_body = evidence.get("api", {}).get("fairness", {}).get("body", {})
    fairness_data = {
        group: float(metrics.get("anomaly_rate", 0.0))
        for group, metrics in fairness_body.get("group_metrics", {}).items()
    }
    if fairness_data:
        path = REPORT_DIR / "fairness_group_rates.svg"
        _write_bar_svg(path, "Anomaly rate by group", fairness_data)
        charts["fairness_group_rates"] = path.relative_to(ROOT).as_posix()
    return charts


def _fmt(value: Any, default: str = "n/a") -> str:
    if value is None or value == "":
        return default
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(item).replace("\n", " ") for item in row) + " |")
    return "\n".join(lines)


def _latest_mlflow_run(evidence: dict[str, Any]) -> dict[str, Any]:
    runs = evidence.get("mlflow", {}).get("latest_runs", {}).get("body", {}).get("runs", [])
    return runs[0] if runs else {}


def _latest_github_run(evidence: dict[str, Any]) -> dict[str, Any]:
    runs = evidence.get("github", {}).get("actions_runs", {}).get("body", {}).get("workflow_runs", [])
    return runs[0] if runs else {}


def _github_job_rows(evidence: dict[str, Any]) -> list[list[Any]]:
    jobs = evidence.get("github", {}).get("latest_run_jobs", {}).get("body", {}).get("jobs", [])
    rows = []
    for job in jobs:
        name = job.get("name")
        if not name:
            continue
        rows.append(
            [
                name,
                job.get("status"),
                job.get("conclusion"),
                job.get("started_at"),
                job.get("completed_at"),
            ]
        )
    return rows


def _github_scan_step_rows(evidence: dict[str, Any]) -> list[list[Any]]:
    jobs = evidence.get("github", {}).get("latest_run_jobs", {}).get("body", {}).get("jobs", [])
    rows = []
    for job in jobs:
        for step in job.get("steps", []):
            step_name = str(step.get("name", ""))
            if "scan" not in step_name.lower() and "trivy" not in step_name.lower():
                continue
            rows.append(
                [
                    job.get("name"),
                    step_name,
                    step.get("status"),
                    step.get("conclusion"),
                    step.get("started_at"),
                    step.get("completed_at"),
                ]
            )
    return rows


def _write_docs(evidence: dict[str, Any]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    model_metrics = evidence["files"]["model_metrics"]
    data_quality = evidence["files"]["data_quality"]
    drift = evidence["api"].get("drift", {}).get("body", evidence["files"]["production_drift"])
    fairness = evidence["api"].get("fairness", {}).get("body", evidence["files"]["fairness"])
    explain = evidence["api"].get("explain", {}).get("body", evidence["files"]["explainability"])
    postgres = evidence["postgres"]
    prometheus = evidence["prometheus"]
    loadtest = evidence["loadtest"]
    health = evidence["api"]["health"].get("body", {})
    mlflow_run = _latest_mlflow_run(evidence)
    github_run = _latest_github_run(evidence)
    github_job_rows = _github_job_rows(evidence)
    github_scan_rows = _github_scan_step_rows(evidence)

    overview_rows = [
        ["Model precision", model_metrics.get("precision"), "models/latest/metrics.json"],
        ["Model recall", model_metrics.get("recall"), "models/latest/metrics.json"],
        ["Model f1_score", model_metrics.get("f1_score"), "models/latest/metrics.json"],
        ["False positive rate", model_metrics.get("false_positive_rate"), "models/latest/metrics.json"],
        ["Training rows", model_metrics.get("training_rows"), "models/latest/metrics.json"],
        ["Production requests", postgres.get("total"), "PostgreSQL prediction_logs"],
        ["Production anomaly count", postgres.get("anomaly"), "PostgreSQL prediction_logs"],
        ["Rolling anomaly rate", _first_value(prometheus.get("anomaly_rate", {})), "Prometheus"],
        ["API p95 latency seconds", _first_value(prometheus.get("p95_latency_seconds", {})), "Prometheus"],
        ["API error count", _first_value(prometheus.get("error_count", {})), "Prometheus"],
        ["Load test RPS", loadtest.get("requests_per_second"), "Locust CSV"],
        ["Load test p95 ms", loadtest.get("p95_ms"), "Locust CSV"],
        ["Load test p99 ms", loadtest.get("p99_ms"), "Locust CSV"],
        ["Load test failure rate", loadtest.get("failure_rate"), "Locust CSV"],
        ["Model source loaded", health.get("model_source"), "FastAPI /health"],
        ["Latest drift score", drift.get("max_drift_score"), "FastAPI /drift"],
        ["Fairness max gap", fairness.get("max_anomaly_rate_gap"), "FastAPI /fairness"],
        ["Explainability method", explain.get("method"), "FastAPI /explain"],
    ]
    evidence_rows = [
        ["MLflow", mlflow_run.get("info", {}).get("run_id"), "Experiment server-log-anomaly"],
        ["Airflow", evidence["airflow"]["health"].get("body", {}).get("metadatabase", {}).get("status"), "Health API"],
        ["Grafana", evidence["grafana"].get("body", {}).get("database"), "Grafana /api/health"],
        ["Alertmanager bridge", evidence["alertmanager_bridge"].get("body", {}).get("status"), "Bridge /health"],
        ["GitHub Actions", github_run.get("conclusion") or github_run.get("status"), github_run.get("html_url")],
        ["Git branch", evidence["github"].get("branch"), evidence["github"].get("commit")],
    ]
    screenshot_rows = [
        [path.name, f"docs/assets/screenshots/{path.name}"] for path in sorted(SCREENSHOT_DIR.glob("*.png"))
    ]
    chart_rows = [[name, path] for name, path in evidence.get("charts", {}).items()]
    data_quality_rows = [
        ["Valid", data_quality.get("valid")],
        ["Rows after validation", data_quality.get("row_count")],
        ["Errors", "; ".join(data_quality.get("errors", [])) or "0"],
        ["Warnings", "; ".join(data_quality.get("warnings", [])) or "0"],
    ]
    production_rows = [
        ["Total requests", postgres.get("total")],
        ["Normal", postgres.get("normal")],
        ["Anomaly", postgres.get("anomaly")],
        ["Average anomaly score", postgres.get("avg_anomaly_score")],
        ["Risk distribution", json.dumps(postgres.get("risk_distribution", {}), ensure_ascii=False)],
    ]
    top_feature_rows = [
        [item.get("feature"), item.get("impact"), item.get("direction")]
        for item in explain.get("top_features", [])[:8]
    ]
    fairness_group_rows = [
        [group, metrics.get("request_count"), metrics.get("anomaly_rate"), metrics.get("high_risk_rate")]
        for group, metrics in fairness.get("group_metrics", {}).items()
    ]
    github_run_json = (
        _markdown_table(
            ["Metric", "Giá trị"],
            [
                ["Run number", github_run.get("run_number")],
                ["Status", github_run.get("status")],
                ["Conclusion", github_run.get("conclusion")],
                ["Event", github_run.get("event")],
                ["Started", github_run.get("run_started_at")],
                ["Updated", github_run.get("updated_at")],
                ["Commit", github_run.get("head_sha")],
                ["URL", github_run.get("html_url")],
            ],
        )
        if github_run
        else "Không lấy được latest run từ GitHub API."
    )
    github_jobs_table = (
        _markdown_table(["Job", "Status", "Conclusion", "Started", "Completed"], github_job_rows)
        if github_job_rows
        else ""
    )
    github_scan_table = (
        _markdown_table(["Job", "Step", "Status", "Conclusion", "Started", "Completed"], github_scan_rows)
        if github_scan_rows
        else ""
    )

    report = f"""# Báo cáo evidence vận hành MLOps

Thời điểm thu thập: `{evidence["collected_at"]}`.

Phạm vi: báo cáo này không triển khai concept drift vì production chưa có ground-truth label.
Các phần còn lại được chạy và ghi nhận qua API, MLflow, Airflow, Prometheus/Grafana,
Alertmanager bridge, PostgreSQL và GitHub.

## Bảng số liệu chính

{_markdown_table(["Chỉ số", "Giá trị", "Nguồn"], overview_rows)}

## Evidence theo hệ thống

{_markdown_table(["Nhóm", "Kết quả", "Nguồn/ghi chú"], evidence_rows)}

## Data quality

{_markdown_table(["Metric", "Giá trị"], data_quality_rows)}

## Production prediction

{_markdown_table(["Metric", "Giá trị"], production_rows)}

## Load test

{_markdown_table(
        ["Metric", "Giá trị"],
        [
            ["Requests", loadtest.get("request_count")],
            ["RPS", loadtest.get("requests_per_second")],
            ["p50 ms", loadtest.get("p50_ms")],
            ["p95 ms", loadtest.get("p95_ms")],
            ["p99 ms", loadtest.get("p99_ms")],
            ["Failure rate", loadtest.get("failure_rate")],
        ],
    )}

## Explainability và fairness

Explainability dùng `{explain.get("method", "n/a")}`. Top feature hiện tại:

{_markdown_table(["Feature", "Impact", "Direction"], top_feature_rows)}

Fairness dùng `{fairness.get("method", "n/a")}` theo nhóm `{fairness.get("group_column", "n/a")}`.

{_markdown_table(["Group", "Requests", "Anomaly rate", "High risk rate"], fairness_group_rows)}

## Biểu đồ sinh tự động

{_markdown_table(["Tên", "File"], chart_rows) if chart_rows else "Chưa có dữ liệu biểu đồ."}

## Ảnh chụp màn hình

{_markdown_table(["Ảnh", "Đường dẫn"], screenshot_rows) if screenshot_rows else "Chưa có ảnh chụp màn hình."}

## Ghi chú CI/CD

Workflow GitHub gồm lint, pytest, docker build, Trivy critical scan, GHCR publish trên `main`
và compose integration test. Latest run lấy từ GitHub API:

{github_run_json}

{github_jobs_table}

{github_scan_table}
"""
    (DOCS_DIR / "evidence_report_vi.md").write_text(report, encoding="utf-8")

    slide_summary = f"""# Tóm tắt slide

## 1. Mục tiêu
- Xây dựng stack MLOps cho phát hiện anomaly trên server metrics.
- Không làm concept drift vì chưa có actual label production.

## 2. Kiến trúc
- Data validation -> preprocessing -> feature engineering -> Isolation Forest.
- MLflow tracking/registry, FastAPI serving, PostgreSQL audit log.
- Prometheus/Grafana monitoring, Alertmanager -> Airflow retraining DAG.

## 3. Kết quả model
- Precision: {_fmt(model_metrics.get("precision"))}
- Recall: {_fmt(model_metrics.get("recall"))}
- F1-score: {_fmt(model_metrics.get("f1_score"))}
- Training rows: {_fmt(model_metrics.get("training_rows"))}

## 4. Production runtime
- Requests logged: {_fmt(postgres.get("total"))}
- Anomaly count: {_fmt(postgres.get("anomaly"))}
- API p95 latency: {_fmt(_first_value(prometheus.get("p95_latency_seconds", {})))} seconds
- Error count: {_fmt(_first_value(prometheus.get("error_count", {})))}
- Load test RPS: {_fmt(loadtest.get("requests_per_second"))}
- Load test p95/failure: {_fmt(loadtest.get("p95_ms"))} ms / {_fmt(loadtest.get("failure_rate"))}

## 5. Observability
- Prometheus scrape FastAPI metrics.
- Grafana dashboard hiển thị request rate, p95 latency, anomaly rate.
- Alertmanager route warning/critical alert sang bridge.

## 6. Explainability và fairness
- Explainability method: {_fmt(explain.get("method"))}
- Fairness group: {_fmt(fairness.get("group_column"))}
- Max anomaly-rate gap: {_fmt(fairness.get("max_anomaly_rate_gap"))}

## 7. Retraining
- API `/retrain` có check drift và force retraining.
- Alertmanager bridge tạo Airflow DAG run khi `DataDriftDetected` hoặc `HighAnomalyRate` firing.

## 8. CI/CD
- GitHub Actions chạy Ruff, pytest, Docker build, Trivy scan và compose integration.
- Latest run: {_fmt(github_run.get("conclusion") or github_run.get("status"))}
"""
    (DOCS_DIR / "slide_summary_vi.md").write_text(slide_summary, encoding="utf-8")


def collect_evidence() -> dict[str, Any]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    api_evidence = _collect_api_evidence()
    time.sleep(16)
    evidence = {
        "collected_at": _now(),
        "api": api_evidence,
        "prometheus": _collect_prometheus(),
        "mlflow": _collect_mlflow(),
        "airflow": _collect_airflow(),
        "grafana": _http_json("http://localhost:3000/api/health", username="admin", password="admin"),
        "alertmanager": _http_json("http://localhost:9093/-/ready"),
        "alertmanager_bridge": _http_json("http://localhost:9099/health"),
        "postgres": _collect_postgres(),
        "loadtest": _collect_loadtest(),
        "docker": _collect_docker(),
        "github": _collect_github(),
        "files": {
            "model_metrics": _read_json(ROOT / "models" / "latest" / "metrics.json"),
            "registry_state": _read_json(ROOT / "models" / "registry" / "registry_state.json"),
            "data_quality": _read_json(ROOT / "reports" / "data_quality" / "latest_report.json"),
            "production_drift": _read_json(ROOT / "reports" / "drift" / "latest_production_report.json"),
            "explainability": _read_json(ROOT / "reports" / "explainability" / "latest_report.json"),
            "fairness": _read_json(ROOT / "reports" / "fairness" / "latest_report.json"),
        },
    }
    evidence["charts"] = _write_charts(evidence)
    metrics_payload = json.dumps(evidence, indent=2, ensure_ascii=False)
    (REPORT_DIR / "latest_metrics.json").write_text(metrics_payload, encoding="utf-8")
    _write_metric_csv(evidence)
    _write_docs(evidence)
    return evidence


def _write_metric_csv(evidence: dict[str, Any]) -> None:
    rows = [
        ("collected_at", evidence["collected_at"]),
        ("model_precision", evidence["files"]["model_metrics"].get("precision")),
        ("model_recall", evidence["files"]["model_metrics"].get("recall")),
        ("model_f1_score", evidence["files"]["model_metrics"].get("f1_score")),
        ("production_requests", evidence["postgres"].get("total")),
        ("production_anomalies", evidence["postgres"].get("anomaly")),
        ("api_p95_latency_seconds", _first_value(evidence["prometheus"].get("p95_latency_seconds", {}))),
        ("api_error_count", _first_value(evidence["prometheus"].get("error_count", {}))),
        ("loadtest_rps", evidence["loadtest"].get("requests_per_second")),
        ("loadtest_p95_ms", evidence["loadtest"].get("p95_ms")),
        ("loadtest_p99_ms", evidence["loadtest"].get("p99_ms")),
        ("loadtest_failure_rate", evidence["loadtest"].get("failure_rate")),
        ("drift_score", evidence["api"].get("drift", {}).get("body", {}).get("max_drift_score")),
        ("fairness_max_gap", evidence["api"].get("fairness", {}).get("body", {}).get("max_anomaly_rate_gap")),
    ]
    with (REPORT_DIR / "metrics_table.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerows(rows)


if __name__ == "__main__":
    print(json.dumps(collect_evidence(), indent=2, ensure_ascii=False))
