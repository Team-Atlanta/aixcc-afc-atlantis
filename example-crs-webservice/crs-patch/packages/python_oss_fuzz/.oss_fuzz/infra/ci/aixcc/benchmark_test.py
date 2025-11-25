#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Set

import yaml

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, parent_dir)

from aixcc import get_cpvs_in_delta_context, get_harnesses, get_tasks
from benchmark_execution_validator import check_benchmark_execution
from benchmark_file_validator import check_benchmark_files
from utils import ExecJobType, JobContext, TaskMode

import build


def get_modified_benchmarks() -> defaultdict[str, Set[str]]:
    git_output = build.get_changed_files_output()
    changed_files = git_output.split()
    pattern = r".*projects/aixcc/([^/.][^/]*)/([^/.][^/]*)/"

    language_benchmarks: defaultdict[str, Set[str]] = defaultdict(set)

    for changed_file in changed_files:
        match = re.search(pattern, changed_file)
        if match:
            language, benchmark = match.groups()
            language_benchmarks[language].add(benchmark)

    root = build.get_oss_fuzz_root()
    for language, benchmarks in language_benchmarks.items():
        for benchmark in benchmarks:
            benchmark_dir_path = os.path.join(
                root, "projects", "aixcc", language, benchmark
            )
            if not os.path.isdir(benchmark_dir_path):
                raise Exception(
                    f"[Error] {benchmark_dir_path} not a valid benchmark directory"
                )
    return language_benchmarks


def get_all_benchmarks() -> defaultdict[str, Set[str]]:
    root = build.get_oss_fuzz_root()
    aixcc_dir = Path(os.path.join(root, "projects", "aixcc"))

    language_benchmarks: defaultdict[str, Set[str]] = defaultdict(set)

    for language_dir in aixcc_dir.iterdir():
        if not language_dir.is_dir():
            continue
        for project_dir in language_dir.iterdir():
            if not project_dir.is_dir():
                continue
            language_benchmarks[language_dir.name].add(project_dir.name)

    return language_benchmarks


def get_benchmarks_to_test(
    run_mode: str = "modified",
    project: Optional[str] = None,
) -> defaultdict[str, Set[str]]:
    if run_mode == "modified":
        return get_modified_benchmarks()
    elif run_mode == "project":
        if not project:
            raise Exception(
                "[Error]: Project name must be provided when run_mode is 'project'."
            )
        pattern = r"^aixcc/([^/]+)/([^/]+)$"  # Regex pattern to match the format

        match = re.match(pattern, project)
        if not match:
            raise ValueError(
                "Invalid format. Expected format: 'aixcc/{language}/{project}'"
            )

        language, project = match.groups()
        benchmarks_to_test: defaultdict[str, Set[str]] = defaultdict(set)
        benchmarks_to_test[language].add(project)
        return benchmarks_to_test
    else:
        return get_all_benchmarks()


def is_project_disabled(language: str, benchmark: str) -> bool:
    root = build.get_oss_fuzz_root()
    benchmark_yaml_path = os.path.join(
        root, "projects", "aixcc", language, benchmark, "project.yaml"
    )
    with open(benchmark_yaml_path) as file_handle:
        benchmark_yaml = yaml.safe_load(file_handle)

    return benchmark_yaml.get("disabled", False)


def chown_build_dir():
    root = build.get_oss_fuzz_root()
    build_dir_path = os.path.join(root, "build")
    if os.path.exists(build_dir_path) and os.path.isdir(build_dir_path):
        command = "sudo chown -R $(whoami):$(whoami) build"
        subprocess.run(command, shell=True, check=True, text=True, cwd=root)


def is_unexpected_infra_change() -> None:
    git_output = build.get_changed_files_output()
    infra_code_regex = r".*infra/.*\n"
    modifiable_files = [
        "infra/ci/aixcc.py",  # Benchmark CI file
        "infra/ci/benchmark_checker.py",  # Benchmark CI file
        "infra/ci/benchmark_execution_validator.py",  # Benchmark CI file
        "infra/ci/benchmark_file_validator.py",  # Benchmark CI file
        "infra/ci/benchmark_test.py",  # Benchmark CI file
        "infra/ci/prepare_sources.py",  # Benchmark CI file
        "infra/ci/run_helper.py",  # Benchmark CI file
        "infra/ci/utils.py",  # Benchmark CI file
        "infra/ci/README.md",  # Benchmark README file
        "infra/base-images/base-builder/precompile_centipede",  # precompile_centipede has existing error
        "infra/base-images/Dockerfile.atl-jazzer",  # Delete when aixcc releases oss-fuzz with aixcc jazzer
        "infra/base-images/jvm-all.sh",  # Delete when aixcc releases oss-fuzz with aixcc jazzer
    ]

    changed_files = re.findall(infra_code_regex, git_output)

    for file in changed_files:
        if file.strip() not in modifiable_files:
            raise Exception(f"[Error] {file} cannot be modified!")


def run_file_check(
    skip_file_check: bool, benchmarks_to_test: defaultdict[str, Set[str]]
) -> None:
    if not skip_file_check:
        print(
            f"[Info] The following benchmarks will be tested(Total: {sum(len(s) for s in benchmarks_to_test.values())})"
        )
        for language, benchmarks in benchmarks_to_test.items():
            print(f"[Info] {language}: {benchmarks}")

        for language, benchmarks in benchmarks_to_test.items():
            for benchmark in benchmarks:
                if is_project_disabled(language, benchmark):
                    print(f"[Info] Skipping benchmark {language}/{benchmark}")
                    continue
                print(f"[Info] Checking benchmark({benchmark}) files")
                check_benchmark_files(language, benchmark)


def run_execution_check(
    skip_build_pov_patch: bool,
    benchmarks_to_test: defaultdict[str, Set[str]],
    worker_id: int,
    num_workers: int,
    check_default_sanitizer_engine: bool,
) -> None:
    if not skip_build_pov_patch:
        jobs = get_workload(
            benchmarks_to_test, worker_id, num_workers, check_default_sanitizer_engine
        )
        print(f"[Info] Number of jobs: {len(jobs)}")
        for job in jobs:
            print(f"[Info] {job}")

        for job in jobs:
            print(f"[Info] Checking job {job}")
            check_benchmark_execution(job)


def get_workload(
    benchmarks_to_test: defaultdict[str, Set[str]],
    worker_id: int,
    num_workers: int,
    check_default_sanitizer_engine: bool,
) -> List[JobContext]:
    jobs: List[JobContext] = []
    root = build.get_oss_fuzz_root()

    for language, benchmarks in benchmarks_to_test.items():
        for benchmark in benchmarks:
            if is_project_disabled(language, benchmark):
                print(f"[Info] Skipping benchmark {language}/{benchmark}")
                continue
            benchmark_yaml_path = os.path.join(
                root, "projects", "aixcc", language, benchmark, "project.yaml"
            )
            with open(benchmark_yaml_path) as file_handle:
                benchmark_yaml = yaml.safe_load(file_handle)

            sanitizers = benchmark_yaml.get("sanitizers", [])
            fuzzing_engines = benchmark_yaml.get("fuzzing_engines", [])
            benchmark_repo_url = benchmark_yaml.get("main_repo", None)

            tasks = get_tasks(root, language, benchmark, benchmark_repo_url)
            harnesses = get_harnesses(language, benchmark)

            print(f"[Info] tasks")
            for task in tasks:
                print(f"[Info] {task}")
            for task in tasks:
                for engine in fuzzing_engines:
                    for sanitizer in sanitizers:
                        if check_default_sanitizer_engine:
                            if sanitizer not in ["none", "address"]:
                                print(f"[Info] Skipping sanitizer {sanitizer}")
                                continue
                            if engine != "libfuzzer":
                                print(f"[Info] Skipping engine {engine}")
                                continue

                        if task.mode == TaskMode.DELTA:
                            cpvs_in_context = get_cpvs_in_delta_context(
                                language, benchmark, task.base_commit, task.ref_commit
                            )
                            jobs.append(
                                JobContext(
                                    ExecJobType.DELTA_BASE_CHECK,
                                    task,
                                    language,
                                    benchmark,
                                    engine,
                                    sanitizer,
                                    None,
                                    None,
                                    cpvs_in_context,
                                )
                            )
                            jobs.append(
                                JobContext(
                                    ExecJobType.DELTA_REF_CHECK,
                                    task,
                                    language,
                                    benchmark,
                                    engine,
                                    sanitizer,
                                    None,
                                    None,
                                    cpvs_in_context,
                                )
                            )
                        if task.mode == TaskMode.FULL:
                            jobs.append(
                                JobContext(
                                    ExecJobType.FULL_BASE_CHECK,
                                    task,
                                    language,
                                    benchmark,
                                    engine,
                                    sanitizer,
                                    None,
                                    None,
                                    None,
                                )
                            )

                        for harness in harnesses:
                            for cpv in harness.cpvs:
                                if cpv.sanitizer == sanitizer and engine == "libfuzzer":
                                    patch_file = os.path.join(
                                        build.get_oss_fuzz_root(),
                                        "projects",
                                        "aixcc",
                                        language,
                                        benchmark,
                                        ".aixcc",
                                        "patches",
                                        harness.name,
                                        f"{cpv.name}.diff",
                                    )
                                    if not os.path.exists(patch_file):
                                        continue

                                    jobs.append(
                                        JobContext(
                                            ExecJobType.CPV_CHECK,
                                            task,
                                            language,
                                            benchmark,
                                            engine,
                                            sanitizer,
                                            harness,
                                            cpv,
                                            None,
                                        )
                                    )

    sorted_jobs = sorted(jobs)
    total_jobs = len(sorted_jobs)

    base_chunk_size = total_jobs // num_workers
    extra = total_jobs % num_workers

    start_idx = worker_id * base_chunk_size + min(worker_id, extra)
    end_idx = start_idx + base_chunk_size + (1 if worker_id < extra else 0)

    return sorted_jobs[start_idx:end_idx]


def main(
    run_mode: str = "modified",
    check_default_sanitizer_engine: bool = False,
    skip_file_check: bool = False,
    skip_build_pov_patch: bool = False,
    exit_on_error: bool = False,
    project: Optional[str] = None,
    worker_id: int = 0,
    num_workers: int = 1,
) -> int:
    ret_code = 0
    try:
        chown_build_dir()
        # is_unexpected_infra_change()
        benchmarks_to_test = get_benchmarks_to_test(run_mode, project)

        run_file_check(skip_file_check, benchmarks_to_test)
        run_execution_check(
            skip_build_pov_patch,
            benchmarks_to_test,
            worker_id,
            num_workers,
            check_default_sanitizer_engine,
        )

        print("[Info] Building benchmarks finished")

    except Exception as e:
        print(f"[Error] main error occurred {e}")
        traceback.print_exc()
        ret_code = 1
    finally:
        chown_build_dir()
        return ret_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benckmark test arguments.")

    parser.add_argument(
        "--run_mode",
        choices=["all", "modified", "project"],
        default="modified",
        help="Run mode: all, modified (default), or project",
    )

    parser.add_argument(
        "--check_default_sanitizer_engine",
        action="store_true",
        help="Enable quick check mode that only uses default sanitizer and engine (default: False)",
    )

    parser.add_argument(
        "--skip_file_check",
        action="store_true",
        help="Disable build, pov, and patch check (default: False)",
    )

    parser.add_argument(
        "--skip_build_pov_patch",
        action="store_true",
        help="Disable build, pov, and patch check (default: False)",
    )

    parser.add_argument(
        "--exit_on_error",
        action="store_true",
        help="Enable exit on error (default: False)",
    )

    parser.add_argument(
        "--project",
        type=str,
        help="Project (required if run_mode is 'project')",
    )

    parser.add_argument(
        "--num_workers",
        type=int,
        default=1,
        help="[CI] Total number of worker processes (default: 1)",
    )

    parser.add_argument(
        "--worker_id",
        type=int,
        default=0,
        help="[CI] Worker ID (default: 0, must be less than num_workers)",
    )

    args = parser.parse_args()

    if args.worker_id >= args.num_workers:
        raise Exception(
            f"worker_id {args.worker_id} should be less than num_workers {args.num_workers}"
        )

    sys.exit(
        main(
            run_mode=args.run_mode,
            check_default_sanitizer_engine=args.check_default_sanitizer_engine,
            skip_file_check=args.skip_file_check,
            skip_build_pov_patch=args.skip_build_pov_patch,
            exit_on_error=args.exit_on_error,
            project=args.project,
            worker_id=args.worker_id,
            num_workers=args.num_workers,
        )
    )
