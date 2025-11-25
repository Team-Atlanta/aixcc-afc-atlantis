import os
import shutil
import subprocess
import sys
from typing import List, Tuple

from git import Repo

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, parent_dir)

from run_helper import run_cmd
from utils import Task, TaskMode, get_workdir

import build


def _get_gct_path() -> str:
    workdir = get_workdir()
    gct_path = os.path.join(workdir, "generate-challenge-task")

    return gct_path


def _clone_generate_challenge_task() -> None:
    gct_path = _get_gct_path()
    gct_repo_url = "git@github.com:Team-Atlanta/generate-challenge-task.git"

    if os.path.exists(gct_path):
        command = f"sudo chown -R $(whoami):$(whoami) {gct_path}"
        subprocess.run(command, shell=True, check=True, text=True)

        shutil.rmtree(gct_path)
    repo = Repo.clone_from(gct_repo_url, gct_path)
    repo.git.checkout("0f12df1f758579fd1f8412a56414b24c7f48f89b")
    run_cmd(["cp", "example.env", ".env"], gct_path)
    print(f"[Info] generate_challenge_task repository cloned to {gct_path}")


def untar(tarball: str, tar_directory: str) -> str:
    existing_files = os.listdir(tar_directory)
    src_untar_cmd = ["tar", "-xvzf", tarball]
    run_cmd(src_untar_cmd, tar_directory)
    created_dirs = [
        os.path.join(tar_directory, d)
        for d in os.listdir(tar_directory)
        if os.path.isdir(os.path.join(tar_directory, d)) and d not in existing_files
    ]
    if len(created_dirs) != 1:
        raise Exception(f"[Error] Created Directories: {created_dirs}")
    return os.path.join(tar_directory, created_dirs[0])


def prepare_sources(
    task: Task,
    language: str,
    benchmark: str,
) -> Tuple[str, str, str]:
    gct_path = _get_gct_path()
    _clone_generate_challenge_task()
    repo_tars_path = os.path.join(gct_path, "repo-tars")
    shutil.rmtree(repo_tars_path, ignore_errors=True)

    gct_cmd: List[str] = [
        os.path.join(gct_path, "generate-challenge-task.sh"),
        "-c",
        "temp",
        "-t",
        task.github_repo,
        "-p",
        f"aixcc/{language}/{benchmark}",
        "-b",
        task.base_commit,
        "-l",
    ]
    if task.mode == TaskMode.DELTA:
        gct_cmd.insert(-1, "-r")
        gct_cmd.insert(-1, task.ref_commit)

    run_cmd(gct_cmd, gct_path)

    os.remove(os.path.join(repo_tars_path, "oss-fuzz.tar.gz"))
    generated_files = os.listdir(repo_tars_path)
    tarballs = [f for f in generated_files if f.endswith(".tar.gz")]

    src_tarballs = [f for f in tarballs if not f.startswith("diff")]
    if len(src_tarballs) != 1:
        raise Exception(f"[Error] Tarballs: {src_tarballs}")
    src_tarball = src_tarballs[0]

    src_dir_path = untar(src_tarball, repo_tars_path)

    if task.mode == TaskMode.DELTA:
        diff_tarballs = [f for f in tarballs if f.startswith("diff")]
        if len(diff_tarballs) != 1:
            raise Exception(f"[Error] Tarballs: {diff_tarballs}")
        diff_tarball = diff_tarballs[0]
        return src_dir_path, diff_tarball, repo_tars_path

    return src_dir_path, "", repo_tars_path


def apply_ref_diff(
    diff_tarball: str,
    repo_tars_path: str,
    src_dir_path: str,
) -> None:
    diff_dir_path = untar(diff_tarball, repo_tars_path)
    diff_path = os.path.join(diff_dir_path, "ref.diff")

    repo = Repo.init(src_dir_path)
    repo.git.add(all=True)
    repo.git.execute(
        ["git", "apply", "--reject", diff_path],
        with_extended_output=True,
        with_exceptions=False,
    )

    if not repo.is_dirty(untracked_files=True):
        raise Exception(f"[Error] applying ref.diff failed!")

    git_dir = os.path.join(src_dir_path, ".git")
    if os.path.isdir(git_dir):
        shutil.rmtree(git_dir)


def apply_patches(
    language: str,
    benchmark: str,
    harness_name: str,
    patch_name: str,
    src_dir_path: str,
    revert: bool,
) -> None:
    print(
        f"[Info] Applying patches {language}/{benchmark}/{harness_name}/{patch_name}. Revert({revert})"
    )
    root = build.get_oss_fuzz_root()
    patch_dir = os.path.join(
        root, "projects", "aixcc", language, benchmark, ".aixcc", "patches"
    )

    patch_file = os.path.join(patch_dir, harness_name, patch_name)
    with open(patch_file, "rb") as diff_file:
        patch_cmd = ["patch", "-p1"]
        if revert:
            patch_cmd.append("-R")
        subprocess.check_call(patch_cmd, cwd=src_dir_path, stdin=diff_file)
