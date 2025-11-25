#!/usr/bin/env python3

import os
import shutil
import sys

from benchmark_test import get_benchmarks_to_test, get_workload
from prepare_sources import prepare_sources, untar
from utils import ExecJobType

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, parent_dir)

import build

if __name__ == "__main__":
    if len(sys.argv) < 2:
        all_benchmarks = get_benchmarks_to_test("all", None)
    else:
        all_benchmarks = get_benchmarks_to_test("project", sys.argv[1])
    jobs = get_workload(all_benchmarks, 0, 1, False)

    delta_ref_check_jobs = [
        job for job in jobs if job.job_type == ExecJobType.DELTA_REF_CHECK
    ]

    delta_ref_check_c_cpp_jvm_jobs = [
        job
        for job in delta_ref_check_jobs
        if job.language not in ["go", "javascript", "python", "rust", "swift"]
    ]

    for job in delta_ref_check_c_cpp_jvm_jobs:
        src_dir_path, diff_tarball_path, repo_tars_path = prepare_sources(
            job.task, job.language, job.benchmark
        )
        diff_dir_path = untar(diff_tarball_path, repo_tars_path)
        diff_path = os.path.join(diff_dir_path, "ref.diff")

        shutil.copy(
            diff_path,
            os.path.join(
                build.get_oss_fuzz_root(),
                "projects",
                "aixcc",
                job.language,
                job.benchmark,
                ".aixcc",
                "ref.diff",
            ),
        )
