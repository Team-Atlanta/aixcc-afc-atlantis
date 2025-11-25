import os
import sys

import yaml

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, parent_dir)

from aixcc import check_aixcc_impl

import build


def _check_project_yaml(language: str, benchmark: str) -> None:
    root = build.get_oss_fuzz_root()

    benchmark_yaml_path = os.path.join(
        root, "projects", "aixcc", language, benchmark, "project.yaml"
    )
    with open(benchmark_yaml_path) as file_handle:
        benchmark_yaml = yaml.safe_load(file_handle)

    sanitizers = benchmark_yaml.get("sanitizers", [])
    fuzzing_engines = benchmark_yaml.get("fuzzing_engines", [])
    benchmark_repo_url = benchmark_yaml.get("main_repo", None)

    if not sanitizers:
        raise Exception(f"[Error] Sanitizers not provided for {language}/{benchmark}")
    if not fuzzing_engines:
        raise Exception(
            f"[Error] Fuzzing Engines not provided for {language}/{benchmark}"
        )
    if not benchmark_repo_url:
        raise Exception(f"[Error] Main Repo not provided for {language}/{benchmark}")


def _check_aixcc_directory(language: str, benchmark: str) -> None:
    print(f"[Info] Checking aixcc directory for {language}/{benchmark}")
    check_aixcc_impl(language, benchmark)


def _check_dockerfile(language: str, benchmark: str) -> None:
    root = build.get_oss_fuzz_root()

    dockerfile_path = os.path.join(
        root, "projects", "aixcc", language, benchmark, "Dockerfile"
    )
    if not os.path.exists(dockerfile_path) or not os.path.isfile(dockerfile_path):
        raise Exception(f"[Error] {dockerfile_path} must exist and must be a file")

    with open(dockerfile_path, "rt") as file:
        content = file.read()
        lines = content.splitlines()

        if "WORKDIR" not in content:
            raise ValueError(
                f"The file '{dockerfile_path}' does not contain the string 'WORKDIR'."
            )

        from_line: Optional[str] = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("FROM"):
                from_line = stripped
                break

        if from_line is None:
            raise ValueError(
                f"The file '{dockerfile_path}' does not contain an uncommented FROM instruction."
            )

        if "aixcc-finals" not in from_line:
            raise ValueError(
                f"The FROM instruction in '{dockerfile_path}' does not contain 'aixcc-finals'."
            )

        if "v1.3.0" not in from_line:
            raise ValueError(
                f"The FROM instruction in '{dockerfile_path}' does not contain 'v1.3.0'."
            )


def _check_build_script(language: str, benchmark: str) -> None:
    root = build.get_oss_fuzz_root()

    build_script_path = os.path.join(
        root, "projects", "aixcc", language, benchmark, "build.sh"
    )
    if os.path.exists(build_script_path):
        if not os.path.isfile(build_script_path):
            raise Exception(f"[Error] {build_script_path} should be a file")
        with open(build_script_path, "rt") as file:
            content = file.read()
            if "git clone" in content:
                raise ValueError(
                    f"The file '{build_script_path}' must not contain the string 'WORKDIR'."
                )


def check_benchmark_files(
    language: str,
    benchmark: str,
) -> None:
    _check_project_yaml(language, benchmark)
    _check_aixcc_directory(language, benchmark)
    _check_dockerfile(language, benchmark)
    _check_build_script(language, benchmark)
