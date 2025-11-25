import os
import re
import subprocess
import sys
from typing import Any, List, Optional, Tuple

import yaml
from utils import CPV, Harness

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, parent_dir)

import build


def run_cmd(
    cmd: List[str],
    cwd: Optional[str] = None,
    expect_fail: bool = False,
    exception: bool = True,
) -> Tuple[str, str]:
    print(f"[Info] Running command(cwd: {cwd}): {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    stdout, stderr = process.communicate()

    if expect_fail:
        if process.returncode == 0 and exception:
            raise RuntimeError(
                f"Command '{' '.join(cmd)}' succeeded with return code {process.returncode}\n"
                f"stdout: {stdout}\n"
                f"stderr: {stderr}"
            )
    else:
        if process.returncode != 0 and exception:
            raise RuntimeError(
                f"Command '{' '.join(cmd)}' failed with return code {process.returncode}\n"
                f"stdout: {stdout}\n"
                f"stderr: {stderr}"
            )

    return stdout, stderr


def _run_helper(
    helper_command: List[str], expect_fail: bool = False, exception: bool = True
) -> Tuple[str, str]:
    root = build.get_oss_fuzz_root()
    script_path = os.path.join(root, "infra", "helper.py")
    command = ["python", script_path] + helper_command
    return run_cmd(command, expect_fail=expect_fail, exception=exception)


def build_benchmark(
    language: str,
    benchmark: str,
    engine: str,
    sanitizer: Any,
    src_dir_path: str,
    check_blob_size: bool = False,
) -> None:
    print(
        f"[Info] Building Benchmark {language}/{benchmark} engine: {engine} sanitizer: {sanitizer}"
    )
    helper_command = [
        "build_fuzzers",
        "--engine",
        engine,
        "--sanitizer",
        (sanitizer if isinstance(sanitizer, str) else list(sanitizer.keys())[0]),
        "--architecture",
        "x86_64",
        "--clean",
        f"aixcc/{language}/{benchmark}",
        f"{src_dir_path}",
        #'-e "MAVEN_OPTS=-Dmaven.repo.local=/work/mavencache"',
    ]
    _run_helper(helper_command)
    _check_build(language, benchmark, engine, sanitizer)

    if check_blob_size:
        _check_blob_sizes(language, benchmark)


def _check_build(language: str, benchmark: str, engine: str, sanitizer: Any) -> None:
    print(f"[Info] Running check_build {language}/{benchmark}")
    helper_command = [
        "check_build",
        "--engine",
        engine,
        "--sanitizer",
        (sanitizer if isinstance(sanitizer, str) else list(sanitizer.keys())[0]),
        f"aixcc/{language}/{benchmark}",
    ]
    _run_helper(helper_command)


def _check_blob_sizes(language: str, benchmark: str) -> None:
    root = build.get_oss_fuzz_root()
    project_path = os.path.join(root, "projects", "aixcc", language, benchmark)
    aixcc_path = os.path.join(project_path, ".aixcc")
    config_file = os.path.join(aixcc_path, "config.yaml")

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

    for harness in harnesses:
        options_path = os.path.join(
            root,
            "build",
            "out",
            "aixcc",
            language,
            benchmark,
            f"{harness.name}.options",
        )
        max_len = 4096

        if os.path.exists(options_path) and os.path.isfile(options_path):
            with open(options_path, "r") as f:
                for line in f:
                    if line.strip().startswith("max_len"):
                        try:
                            max_len = int(line.strip().split("=", 1)[1].strip())
                        except ValueError:
                            raise ValueError(
                                f"[Error] Invalid max_len in {options_path}"
                            )
                        break

        for cpv in harness.cpvs:
            filepath = os.path.join(aixcc_path, "povs", harness.name, f"{cpv.name}")
            filesize = os.path.getsize(filepath)
            if filesize > max_len:
                raise ValueError(
                    f"[Error] harness {harness.name}, file {filepath} is too large ({filesize} bytes), must be <= {max_len} bytes"
                )


def _strip_ansi(text: str):
    ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", text)


def run_pov(
    language: str,
    benchmark: str,
    harness_name: str,
    cpv_name: str,
    error_token: str,
    is_patched: bool,
) -> Tuple[str, str]:
    print(
        f"[Info] Running pov {language}/{benchmark}/{harness_name}/{cpv_name} patched: {is_patched}"
    )
    root = build.get_oss_fuzz_root()
    pov_dir = os.path.join(
        root, "projects", "aixcc", language, benchmark, ".aixcc", "povs"
    )

    helper_command = [
        "reproduce",
        f"aixcc/{language}/{benchmark}",
        f"{harness_name}",
        f"{pov_dir}/{harness_name}/{cpv_name}",
    ]
    stdout, stderr = _run_helper(helper_command, not is_patched, not is_patched)
    stdout_clean = _strip_ansi(stdout)

    if not is_patched:
        if error_token not in stdout_clean:
            raise Exception(f"[Error] {error_token} is not in reproduce log")
    else:
        if error_token in stdout_clean:
            raise Exception(f"[Error] {error_token} is in reproduce log")
    return stdout_clean, stderr
