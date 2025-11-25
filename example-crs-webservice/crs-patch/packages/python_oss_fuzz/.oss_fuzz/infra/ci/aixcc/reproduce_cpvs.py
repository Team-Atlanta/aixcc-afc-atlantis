#!/usr/bin/env python3

import os
import shutil
import sys

from benchmark_test import get_benchmarks_to_test, get_workload
from prepare_sources import prepare_sources, untar
from run_helper import build_benchmark, run_pov
from utils import ExecJobType, TaskMode

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, parent_dir)

import build

if __name__ == "__main__":
    all_benchmarks = get_benchmarks_to_test("project", sys.argv[1])
    jobs = get_workload(all_benchmarks, 0, 1, False)

    jobs = [job for job in jobs if job.job_type == ExecJobType.CPV_CHECK]

    for job in jobs:
         # Skip delta mode; generate crash_logs for full mode only
        if job.task.mode == TaskMode.DELTA: 
            continue
        src_dir_path, diff_tarball_path, repo_tars_path = prepare_sources(
            job.task, job.language, job.benchmark
        )
        build_benchmark(
            job.language, job.benchmark, job.engine, job.sanitizer, src_dir_path
        )
        stdout, stderr = run_pov(
            job.language,
            job.benchmark,
            job.harness.name,
            job.cpv.name,
            job.cpv.error_token,
            False,
        )
        crash_log_dir = os.path.join(
            build.get_oss_fuzz_root(),
            "projects",
            "aixcc",
            job.language,
            job.benchmark,
            ".aixcc",
            "crash_logs",
            job.harness.name
        )
        os.makedirs(crash_log_dir, exist_ok=True)
        crash_log_path = os.path.join(crash_log_dir, f"{job.cpv.name}.log")
        with open(crash_log_path, "w") as crash_log_file:
            crash_log_file.write(stdout)
