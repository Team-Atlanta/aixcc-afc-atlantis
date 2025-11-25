import os
import shutil
import sys
from typing import List, Optional

import yaml
from git import Repo

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, parent_dir)

from utils import CPV, Harness, Task, TaskMode, get_workdir

import build


def get_tasks(
    ossfuzz_root: str,
    language: str,
    benchmark: str,
    benchmark_repo_url: str,
) -> List[Task]:
    workdir = get_workdir()
    temp_repo_path = os.path.join(workdir, "temp-repo")
    shutil.rmtree(temp_repo_path, ignore_errors=True)

    tasks: List[Task] = []
    Repo.clone_from(benchmark_repo_url, temp_repo_path)
    print(f"[Info] benchmark repository cloned to {temp_repo_path}")

    config_file = os.path.join(
        ossfuzz_root,
        "projects",
        "aixcc",
        language,
        benchmark,
        ".aixcc",
        "config.yaml",
    )
    with open(config_file) as file_handle:
        config_yaml = yaml.safe_load(file_handle)

    tasks.append(
        Task(
            mode=TaskMode.FULL,
            github_repo=benchmark_repo_url,
            base_commit=config_yaml["full_mode"]["base_commit"],
            ref_commit="",
        )
    )

    if "delta_mode" in config_yaml:
        for entry in config_yaml["delta_mode"]:
            tasks.append(
                Task(
                    mode=TaskMode.DELTA,
                    github_repo=benchmark_repo_url,
                    base_commit=entry["base_commit"],
                    ref_commit=entry["ref_commit"],
                )
            )

    return tasks


def get_harnesses(language: str, benchmark: str) -> List[Harness]:
    root = build.get_oss_fuzz_root()
    config_file = os.path.join(
        root,
        "projects",
        "aixcc",
        language,
        benchmark,
        ".aixcc",
        "config.yaml",
    )
    with open(config_file) as file_handle:
        aixcc_config_yaml = yaml.safe_load(file_handle)

    harnesses: List[Harness] = []
    for harness_entry in aixcc_config_yaml["harness_files"]:
        harness = Harness(harness_entry["name"], [])
        harnesses.append(harness)

        if "cpvs" in harness_entry:
            for cpv in harness_entry["cpvs"]:
                harness.cpvs.append(
                    CPV(cpv["name"], cpv["sanitizer"], cpv["error_token"])
                )

    return harnesses


def get_cpvs_in_delta_context(
    language: str, benchmark: str, base_commit: str, ref_commit: str
) -> Optional[List[str]]:
    root = build.get_oss_fuzz_root()
    config_file = os.path.join(
        root,
        "projects",
        "aixcc",
        language,
        benchmark,
        ".aixcc",
        "config.yaml",
    )
    with open(config_file) as file_handle:
        aixcc_config_yaml = yaml.safe_load(file_handle)

    if "delta_mode" not in aixcc_config_yaml:
        return None

    for entry in aixcc_config_yaml["delta_mode"]:
        if entry["base_commit"] == base_commit and entry["ref_commit"] == ref_commit:
            if "cpvs" not in entry:
                return None
            return [cpv["name"] for cpv in entry["cpvs"]]

    assert False, "This line should never be reached"


def check_aixcc_impl(language: str, benchmark: str) -> None:
    root = build.get_oss_fuzz_root()

    project_path = os.path.join(root, "projects", "aixcc", language, benchmark)
    benchmark_yaml_path = os.path.join(project_path, "project.yaml")
    with open(benchmark_yaml_path) as file_handle:
        benchmark_yaml = yaml.safe_load(file_handle)
    sanitizers: List[str] = benchmark_yaml.get("sanitizers", [])

    aixcc_path = os.path.join(root, "projects", "aixcc", language, benchmark, ".aixcc")

    if not os.path.exists(aixcc_path) or not os.path.isdir(aixcc_path):
        raise Exception(
            f"[Error] '.aixcc' directory does not exist at path: {aixcc_path}"
        )

    _check_aixcc_config_yaml(aixcc_path, sanitizers)
    harnesses = get_harnesses(language, benchmark)
    _check_aixcc_required_directories(aixcc_path, harnesses)


def _check_aixcc_required_directories(
    aixcc_path: str, harnesses: List[Harness]
) -> None:
    required = [("povs", ""), ("crash_logs", ".log")]

    for harness in harnesses:
        for cpv in harness.cpvs:
            for dir, ext in required:
                filepath = os.path.join(
                    aixcc_path, dir, harness.name, f"{cpv.name}{ext}"
                )
                if not os.path.exists(filepath):
                    raise FileNotFoundError(f"[Error] file {filepath} does not exist")
                if not os.path.isfile(filepath):
                    raise ValueError(f"[Error] file {filepath} is not a file")

                if ext == ".log":
                    with open(filepath, "rb") as f:
                        content = f.read()
                        if cpv.error_token.encode() not in content:
                            raise Exception(
                                f"[Error] error token {cpv.error_token} is not found in crash log"
                            )


def _check_aixcc_config_yaml(aixcc_path: str, sanitizers: List[str]) -> None:
    aixcc_config_path = os.path.join(aixcc_path, "config.yaml")

    if not os.path.exists(aixcc_config_path) or not os.path.isfile(aixcc_config_path):
        raise Exception(f"[Error] {aixcc_config_path} must exist and must be a file")

    with open(aixcc_config_path) as file_handle:
        aixcc_config_yaml = yaml.safe_load(file_handle)

    if "full_mode" not in aixcc_config_yaml:
        raise ValueError(f"[Error] 'full_mode' or 'base_commit' missing.")

    if "delta_mode" in aixcc_config_yaml:
        if (
            not isinstance(aixcc_config_yaml["delta_mode"], list)
            or len(aixcc_config_yaml["delta_mode"]) == 0
        ):
            raise ValueError(f"[Error] 'delta_mode' must be a non-empty list.")

        for commit_info in aixcc_config_yaml["delta_mode"]:
            if "base_commit" not in commit_info or "ref_commit" not in commit_info:
                raise ValueError(
                    f"[Error] Each item in 'delta_mode' must contain 'base_commit' and 'ref_commit'."
                )

        if len(aixcc_config_yaml["delta_mode"]) != 1:
            raise ValueError(f"[Error] For now we are only allowing one 'delta_mode'")

        if (
            aixcc_config_yaml["full_mode"]["base_commit"]
            != aixcc_config_yaml["delta_mode"][0]["ref_commit"]
        ):
            raise ValueError(
                f"[Error] full mode's base commit({aixcc_config_yaml['full_mode']['base_commit']}) does not match delta mode's ref commit {aixcc_config_yaml['delta_mode'][0]['ref_commit']}"
            )

        ref_diff_path = os.path.join(aixcc_path, "ref.diff")
        if not os.path.exists(ref_diff_path) or not os.path.isfile(ref_diff_path):
            raise Exception(
                f"[Error] {ref_diff_path} must exist for delta mode and must be a file"
            )

    if "harness_files" not in aixcc_config_yaml:
        raise ValueError(f"[Error] 'harness_files' missing.")
    if (
        not isinstance(aixcc_config_yaml["harness_files"], list)
        or len(aixcc_config_yaml["harness_files"]) == 0
    ):
        raise ValueError(f"[Error] 'harness_files' must be a non-empty list.")

    for harness_entry in aixcc_config_yaml["harness_files"]:
        if "name" not in harness_entry or "path" not in harness_entry:
            raise ValueError(
                f"[Error] Each item in 'harness_files' must contain 'name' and 'path'."
            )
        if not harness_entry["path"].startswith("$REPO") and not harness_entry[
            "path"
        ].startswith("$PROJECT"):
            raise ValueError(
                "[Error] harness path must start with either $REPO or $PROJECT"
            )

        if "cpvs" in harness_entry:
            if (
                not isinstance(harness_entry["cpvs"], list)
                or len(harness_entry["cpvs"]) == 0
            ):
                raise ValueError(f"[Error] 'cpvs' must be a non-empty list.")

            for cpv in harness_entry["cpvs"]:
                if (
                    "name" not in cpv
                    or "sanitizer" not in cpv
                    or "error_token" not in cpv
                ):
                    raise ValueError(
                        f"[Error] Each cpv must contain 'name', 'sanitizer' and 'error_token'."
                    )

                if cpv["sanitizer"] not in [
                    "address",
                    "memory",
                    "undefined",
                    "thread",
                    "none",
                ]:
                    raise ValueError(
                        f"[Error] sanitizer {cpv['sanitizer']} does not exist"
                    )

                if cpv["sanitizer"] not in sanitizers:
                    raise ValueError(
                        f"[Error] sanitizer {cpv['sanitizer']} not in project.yaml"
                    )
