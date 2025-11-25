#!/usr/bin/env python3

import os
import shutil
import sys
import pathlib
import re
import yaml
from git import Repo

from benchmark_test import get_benchmarks_to_test, get_workload
from prepare_sources import prepare_sources, untar
from run_helper import build_benchmark, run_pov
from utils import ExecJobType, get_workdir
from aixcc import get_harnesses

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, parent_dir)

import build

if __name__ == "__main__":
    assert len(sys.argv) > 1, f"Usage: {sys.argv[0]} aixcc/c/mock-c"
    project = sys.argv[1]
    oss_fuzz_root = pathlib.Path(build.get_oss_fuzz_root())
    project_dir = oss_fuzz_root / 'projects' / project
    assert project_dir.exists(), f'{project_dir} does not exist.'

    pattern = r"^aixcc/([^/]+)/([^/]+)$"  # Regex pattern to match the format

    match = re.match(pattern, project)
    if not match:
        raise ValueError(
            "Invalid format. Expected format: 'aixcc/{language}/{project}'"
        )

    language, project = match.groups()

    aixcc_dir = project_dir / '.aixcc'
    aixcc_dir.mkdir(parents=False, exist_ok=True)

    project_yaml_path = project_dir / 'project.yaml'
    aixcc_config_yaml_path = aixcc_dir / 'config.yaml'

    assert project_yaml_path.exists()

    with open(project_yaml_path) as file_handle:
        project_yaml = yaml.safe_load(file_handle)

    if aixcc_config_yaml_path.exists():
        with open(aixcc_config_yaml_path) as file_handle:
            aixcc_config_yaml = yaml.safe_load(file_handle)
        harnesses = get_harnesses(language, project)
        for harness in harnesses:
            name = harness.name
            cpvs = harness.cpvs
            # always create povs dir
            povs_dir = aixcc_dir / 'povs' / name
            povs_dir.mkdir(parents=True, exist_ok=True)
            if len(cpvs) > 0:
                patches_dir = aixcc_dir / 'patches' / name
                crash_logs_dir = aixcc_dir / 'crash_logs' / name
                patches_dir.mkdir(parents=True, exist_ok=True)
                crash_logs_dir.mkdir(parents=True, exist_ok=True)
    else:
        povs_dir = aixcc_dir / 'povs'
        patches_dir = aixcc_dir / 'patches'
        crash_logs_dir = aixcc_dir / 'crash_logs'
        povs_dir.mkdir(parents=True, exist_ok=True)
        patches_dir.mkdir(parents=True, exist_ok=True)
        crash_logs_dir.mkdir(parents=True, exist_ok=True)

        print("[Info] generate config.yaml from benchmark repository")
        config_template = {
            "full_mode": {
                "base_commit": "6fb247fb71831b650a038bd79f103b662e311fdc"  # Replace with appropriate commit hash.
            },
            "delta_mode": [
                {
                    "base_commit": "b2337dffea1153052087279ceb17c32610ce5a67",  # Replace with appropriate commit hash.
                    "ref_commit": "6fb247fb71831b650a038bd79f103b662e311fdc"   # Replace with appropriate commit hash.
                }
            ],
            "harness_files": [
                {
                    "name": "ossfuzz-1",
                    "path": "$PROJECT/fuzz/ossfuzz-1.c",
                    "cpvs": [
                        {
                            "name": "cpv_0",
                            "sanitizer": "address",
                            "error_token": "ERROR: AddressSanitizer: stack-buffer-overflow"
                        }
                    ]
                },
            ]
        }
   

        workdir = get_workdir()
        temp_repo_path = os.path.join(workdir, "temp-repo")
        shutil.rmtree(temp_repo_path, ignore_errors=True)
        benchmark_repo_url = project_yaml.get("main_repo", None)
        assert benchmark_repo_url is not None, f"main_repo not found in {project_yaml}"
        print(f"[Info] Cloning benchmark repository from {benchmark_repo_url}")
        Repo.clone_from(benchmark_repo_url, temp_repo_path)
        print(f"[Info] benchmark repository cloned to {temp_repo_path}")

        repo = Repo(temp_repo_path)
        base_commit = repo.head.commit
        # full mode
        config_template["full_mode"]["base_commit"] = base_commit.hexsha
        if base_commit.parents:
            ref_commit = base_commit
            base_commit = ref_commit.parents[0]
            # delta mode
            config_template["delta_mode"][0]["base_commit"] = base_commit.hexsha
            config_template["delta_mode"][0]["ref_commit"] = ref_commit.hexsha

        with open(aixcc_config_yaml_path, "w") as outfile:
            yaml.dump(config_template, outfile, default_flow_style=False, sort_keys=False)
        print(f"Template configuration written to {aixcc_config_yaml_path}")

        
