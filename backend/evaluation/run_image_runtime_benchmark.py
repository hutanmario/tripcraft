#!/usr/bin/env python3
"""
Benchmark runtime/resurse pentru pipeline-urile de recunoastere imagini.

Ruleaza pipeline-urile in procese separate si masoara:
- wall time total
- peak working set / RAM de proces
- throughput imagini/secunda
- metricile deja calculate de evaluator, daca exista rezultate

Rulare (din directorul backend/):
    python -m evaluation.run_image_runtime_benchmark

Rulare rapida:
    python -m evaluation.run_image_runtime_benchmark --limit 10
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import json
import os
import platform
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ctypes import wintypes


EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent
RESULTS_DIR = EVAL_DIR / "results"
DEFAULT_DATASET_PATH = EVAL_DIR / "image_recognition_dataset.json"

SUMMARY_MD = RESULTS_DIR / "SUMMARY_IMAGE_RUNTIME_BENCHMARK.md"
OUTPUT_JSON = RESULTS_DIR / "image_runtime_benchmark.json"
OUTPUT_CSV = RESULTS_DIR / "image_runtime_benchmark.csv"


PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _get_windows_memory(pid: int) -> dict[str, int] | None:
    if platform.system().lower() != "windows":
        return None

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        return None

    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        if not ok:
            return None
        return {
            "working_set_bytes": int(counters.WorkingSetSize),
            "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
            "pagefile_bytes": int(counters.PagefileUsage),
            "peak_pagefile_bytes": int(counters.PeakPagefileUsage),
        }
    finally:
        kernel32.CloseHandle(handle)


def _mb(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / (1024 * 1024), 2)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _dataset_count(dataset_path: Path, limit: int | None) -> int:
    payload = _read_json(dataset_path)
    if not payload:
        return 0
    count = len(payload.get("images", []))
    return min(limit, count) if limit is not None else count


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    command: list[str]
    predictions_path: Path
    notes: str


def _run_monitored(command: list[str], cwd: Path, poll_interval: float) -> dict[str, Any]:
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    peak_working_set = None
    peak_pagefile = None
    output_lines_queue: queue.Queue[str] = queue.Queue()
    output_lines: list[str] = []

    def read_output() -> None:
        if not process.stdout:
            return
        for line in process.stdout:
            output_lines_queue.put(line.rstrip())

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()

    while True:
        while True:
            try:
                output_lines.append(output_lines_queue.get_nowait())
            except queue.Empty:
                break

        mem = _get_windows_memory(process.pid)
        if mem:
            peak_working_set = max(peak_working_set or 0, mem["peak_working_set_bytes"])
            peak_pagefile = max(peak_pagefile or 0, mem["peak_pagefile_bytes"])

        if process.poll() is not None:
            break

        time.sleep(poll_interval)

    reader.join(timeout=2)
    while True:
        try:
            output_lines.append(output_lines_queue.get_nowait())
        except queue.Empty:
            break

    elapsed = time.perf_counter() - started
    worker_result = None
    for line in output_lines:
        if line.startswith("BENCHMARK_RESULT_JSON="):
            worker_result = json.loads(line.split("=", 1)[1])

    return {
        "returncode": process.returncode,
        "wall_time_sec": round(elapsed, 3),
        "peak_working_set_mb": _mb(peak_working_set),
        "peak_pagefile_mb": _mb(peak_pagefile),
        "output_tail": output_lines[-40:],
        "worker_result": worker_result,
    }


def _build_cases(
    python_exe: str,
    dataset_path: Path,
    limit: int | None,
    poll_interval: float,
) -> list[BenchmarkCase]:
    limit_args = ["--limit", str(limit)] if limit is not None else []
    prompt_output = RESULTS_DIR / "image_prompt_multitag_benchmark_predictions.json"

    return [
        BenchmarkCase(
            name="current_pipeline",
            command=[
                python_exe,
                "-m",
                "evaluation.run_image_runtime_benchmark",
                "--worker",
                "current_pipeline",
                "--dataset",
                str(dataset_path),
                "--poll-interval",
                str(poll_interval),
                *limit_args,
            ],
            predictions_path=RESULTS_DIR / "image_baseline_current.json",
            notes="Pipeline actual: CLIP generic + scene/colors/season + SentenceTransformer mapping.",
        ),
        BenchmarkCase(
            name="prompt_top2_mean",
            command=[
                python_exe,
                "-m",
                "evaluation.run_image_runtime_benchmark",
                "--worker",
                "prompt_top2_mean",
                "--dataset",
                str(dataset_path),
                "--worker-output",
                str(prompt_output),
                "--poll-interval",
                str(poll_interval),
                *limit_args,
            ],
            predictions_path=prompt_output,
            notes="Pipeline nou: prompturi directe pe tagurile TripCraft, score_mode=top2_mean.",
        ),
    ]


def _evaluate_case(case: BenchmarkCase, dataset_path: Path, limit: int | None) -> dict[str, Any]:
    eval_name = f"bench_{case.name}"
    command = [
        sys.executable,
        "-m",
        "evaluation.run_image_recognition_eval",
        "--dataset",
        str(dataset_path),
        "--predictions",
        str(case.predictions_path),
        "--names",
        eval_name,
    ]
    if limit is not None:
        # Evaluatorul cere predictii pentru toate imaginile din dataset. Pentru limit,
        # folosim metricile din payload-ul pipeline-ului daca exista.
        return {}

    result = subprocess.run(
        command,
        cwd=str(BACKEND_DIR),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return {"error": result.stdout[-2000:]}

    eval_payload = _read_json(RESULTS_DIR / f"image_recognition_eval_{eval_name}.json")
    if not eval_payload:
        return {}
    summary = eval_payload.get("summary", {})
    return {
        "precision_at_3": summary.get("macro_precision_at_3"),
        "recall_at_5": summary.get("macro_recall_at_5"),
        "ndcg_at_5": summary.get("ndcg_at_5"),
        "zero_hit_rate_at_5": summary.get("zero_hit_rate_at_5"),
    }


def run_benchmark(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    limit: int | None = None,
    poll_interval: float = 0.2,
    skip_eval: bool = False,
) -> dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    python_exe = sys.executable
    num_images = _dataset_count(dataset_path, limit)
    cases = _build_cases(python_exe, dataset_path, limit, poll_interval)

    rows = []
    for case in cases:
        print(f"Running {case.name}...")
        result = _run_monitored(case.command, BACKEND_DIR, poll_interval)
        worker = result.get("worker_result") or {}
        predictions = _read_json(case.predictions_path) or {}
        pipeline_time = worker.get("pipeline_reported_time_sec", predictions.get("processing_time_sec"))
        per_image_times = [
            item.get("processing_time_sec")
            for item in predictions.get("results", [])
            if isinstance(item.get("processing_time_sec"), (int, float))
        ]
        measured_images = predictions.get("num_images") or len(predictions.get("results", [])) or num_images

        metrics = {} if skip_eval else _evaluate_case(case, dataset_path, limit)
        row = {
            "name": case.name,
            "notes": case.notes,
            "returncode": result["returncode"],
            "num_images": measured_images,
            "wall_time_sec": worker.get("wall_time_sec", result["wall_time_sec"]),
            "process_wall_time_sec": result["wall_time_sec"],
            "pipeline_reported_time_sec": pipeline_time,
            "sec_per_image_wall": round(result["wall_time_sec"] / measured_images, 4) if measured_images else None,
            "sec_per_image_reported": round(pipeline_time / measured_images, 4) if pipeline_time and measured_images else None,
            "mean_inner_image_sec": round(sum(per_image_times) / len(per_image_times), 4) if per_image_times else None,
            "peak_working_set_mb": worker.get("peak_working_set_mb", result["peak_working_set_mb"]),
            "peak_pagefile_mb": worker.get("peak_pagefile_mb", result["peak_pagefile_mb"]),
            "predictions_path": str(case.predictions_path),
            "metrics": metrics,
            "output_tail": result["output_tail"],
        }
        rows.append(row)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset_path),
        "limit": limit,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python_executable": python_exe,
            "torch_num_threads": _torch_threads(),
        },
        "results": rows,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_csv(rows)
    _write_markdown(payload)
    return payload


def _torch_threads() -> int | None:
    try:
        import torch

        return int(torch.get_num_threads())
    except Exception:
        return None


def _monitor_current_process(stop_event: threading.Event, sample: dict[str, int | None], poll_interval: float) -> None:
    pid = os.getpid()
    while not stop_event.is_set():
        mem = _get_windows_memory(pid)
        if mem:
            sample["peak_working_set_bytes"] = max(
                int(sample.get("peak_working_set_bytes") or 0),
                mem["peak_working_set_bytes"],
            )
            sample["peak_pagefile_bytes"] = max(
                int(sample.get("peak_pagefile_bytes") or 0),
                mem["peak_pagefile_bytes"],
            )
        time.sleep(poll_interval)


def run_worker(
    worker: str,
    dataset_path: Path,
    limit: int | None,
    output_path: Path | None,
    poll_interval: float,
) -> dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    memory_sample: dict[str, int | None] = {
        "peak_working_set_bytes": None,
        "peak_pagefile_bytes": None,
    }
    stop_event = threading.Event()
    monitor = threading.Thread(
        target=_monitor_current_process,
        args=(stop_event, memory_sample, poll_interval),
        daemon=True,
    )

    started = time.perf_counter()
    monitor.start()
    try:
        if worker == "current_pipeline":
            from evaluation.run_image_baseline import run_baseline

            payload = run_baseline(dataset_path=dataset_path, limit=limit)
            predictions_path = RESULTS_DIR / "image_baseline_current.json"
        elif worker == "prompt_top2_mean":
            from evaluation.run_image_prompt_pipeline import run_prompt_pipeline

            predictions_path = output_path or RESULTS_DIR / "image_prompt_multitag_benchmark_predictions.json"
            payload = run_prompt_pipeline(
                dataset_path=dataset_path,
                output_path=predictions_path,
                limit=limit,
                score_mode="top2_mean",
            )
        else:
            raise ValueError(f"Worker necunoscut: {worker}")
    finally:
        stop_event.set()
        monitor.join(timeout=2)

    wall_time = time.perf_counter() - started
    result = {
        "worker": worker,
        "wall_time_sec": round(wall_time, 3),
        "pipeline_reported_time_sec": payload.get("processing_time_sec"),
        "num_images": payload.get("num_images"),
        "predictions_path": str(predictions_path),
        "peak_working_set_mb": _mb(memory_sample.get("peak_working_set_bytes")),
        "peak_pagefile_mb": _mb(memory_sample.get("peak_pagefile_bytes")),
    }
    print("BENCHMARK_RESULT_JSON=" + json.dumps(result, ensure_ascii=False))
    return result


def _write_csv(rows: list[dict[str, Any]]) -> None:
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "name",
            "num_images",
            "wall_time_sec",
            "pipeline_reported_time_sec",
            "sec_per_image_wall",
            "sec_per_image_reported",
            "mean_inner_image_sec",
            "peak_working_set_mb",
            "peak_pagefile_mb",
            "precision_at_3",
            "recall_at_5",
            "ndcg_at_5",
            "zero_hit_rate_at_5",
            "returncode",
            "predictions_path",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            metrics = row.get("metrics") or {}
            writer.writerow(
                {
                    **{key: row.get(key) for key in fieldnames},
                    "precision_at_3": metrics.get("precision_at_3"),
                    "recall_at_5": metrics.get("recall_at_5"),
                    "ndcg_at_5": metrics.get("ndcg_at_5"),
                    "zero_hit_rate_at_5": metrics.get("zero_hit_rate_at_5"),
                }
            )


def _write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# Image Runtime Benchmark",
        "",
        f"Generated at: `{payload['generated_at']}`",
        f"Dataset: `{payload['dataset']}`",
        f"Limit: `{payload['limit'] if payload['limit'] is not None else 'full'}`",
        "",
        "## Environment",
        "",
        f"- Python: `{payload['environment']['python']}`",
        f"- Platform: `{payload['environment']['platform']}`",
        f"- Torch threads: `{payload['environment']['torch_num_threads']}`",
        "",
        "## Results",
        "",
        "| Pipeline | Images | Wall time | sec/img | Peak RAM MB | P@3 | R@5 | NDCG@5 | Zero-hit@5 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for row in payload["results"]:
        metrics = row.get("metrics") or {}
        lines.append(
            "| {name} | {n} | {wall} | {spi} | {ram} | {p3} | {r5} | {ndcg} | {zero} |".format(
                name=row["name"],
                n=row["num_images"],
                wall=row["wall_time_sec"],
                spi=row["sec_per_image_wall"],
                ram=row["peak_working_set_mb"],
                p3=metrics.get("precision_at_3", ""),
                r5=metrics.get("recall_at_5", ""),
                ndcg=metrics.get("ndcg_at_5", ""),
                zero=metrics.get("zero_hit_rate_at_5", ""),
            )
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Wall time include pornirea procesului, importurile Python si incarcarea modelelor.",
            "- Peak RAM este `PeakWorkingSetSize` al procesului copil pe Windows.",
            "- `pipeline_reported_time_sec` din JSON exclude o parte din overhead-ul de startup, dar include inferenta pipeline-ului.",
            "",
            "## Files",
            "",
            f"- JSON: `{OUTPUT_JSON.name}`",
            f"- CSV: `{OUTPUT_CSV.name}`",
        ]
    )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark runtime pentru pipeline-urile de recunoastere imagini.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH), help="Manifest JSON cu imagini.")
    parser.add_argument("--limit", type=int, default=None, help="Ruleaza doar primele N imagini.")
    parser.add_argument("--poll-interval", type=float, default=0.2, help="Interval monitorizare memorie.")
    parser.add_argument("--skip-eval", action="store_true", help="Nu ruleaza evaluatorul dupa benchmark.")
    parser.add_argument(
        "--worker",
        choices=["current_pipeline", "prompt_top2_mean"],
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--worker-output", default=None, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.worker:
        run_worker(
            worker=args.worker,
            dataset_path=Path(args.dataset),
            limit=args.limit,
            output_path=Path(args.worker_output) if args.worker_output else None,
            poll_interval=args.poll_interval,
        )
        return

    payload = run_benchmark(
        dataset_path=Path(args.dataset),
        limit=args.limit,
        poll_interval=args.poll_interval,
        skip_eval=args.skip_eval,
    )
    print(f"Saved {OUTPUT_JSON}")
    for row in payload["results"]:
        print(
            "{name}: {wall}s, {sec_img}s/img, peak RAM {ram} MB".format(
                name=row["name"],
                wall=row["wall_time_sec"],
                sec_img=row["sec_per_image_wall"],
                ram=row["peak_working_set_mb"],
            )
        )


if __name__ == "__main__":
    main()
