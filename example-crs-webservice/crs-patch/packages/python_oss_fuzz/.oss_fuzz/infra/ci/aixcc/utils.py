import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, parent_dir)

import build


class TaskMode(Enum):
    FULL = 1
    DELTA = 2

    def __lt__(self, other):
        return self.value < other.value


@dataclass
class Task:
    mode: TaskMode
    github_repo: str
    base_commit: str
    ref_commit: str

    def __lt__(self, other):
        return self.mode < other.mode


@dataclass
class CPV:
    name: str
    sanitizer: str
    error_token: str

    def __lt__(self, other):
        return self.name < other.name


@dataclass
class Harness:
    name: str
    cpvs: List[CPV]

    def __lt__(self, other):
        return self.name < other.name


class ExecJobType(Enum):
    DELTA_BASE_CHECK = 1
    DELTA_REF_CHECK = 2
    FULL_BASE_CHECK = 3
    CPV_CHECK = 4

    def __lt__(self, other):
        return self.value < other.value


@dataclass
class JobContext:
    job_type: ExecJobType
    task: Task
    language: str
    benchmark: str
    engine: str
    sanitizer: str
    harness: Optional[Harness]
    cpv: Optional[CPV]
    cpvs_in_context: Optional[List[str]]

    def __lt__(self, other):
        if not isinstance(other, JobContext):
            return NotImplemented

        return (
            self.language,
            self.benchmark,
            self.engine,
            (
                self.sanitizer
                if isinstance(self.sanitizer, str)
                else list(self.sanitizer.keys())[0]
            ),
            self.task,
            self.job_type,
            self.harness or Harness("", []),
            self.cpv or CPV("", "", ""),
        ) < (
            other.language,
            other.benchmark,
            other.engine,
            (
                other.sanitizer
                if isinstance(other.sanitizer, str)
                else list(other.sanitizer.keys())[0]
            ),
            other.task,
            other.job_type,
            other.harness or Harness("", []),
            other.cpv or CPV("", "", ""),
        )


def get_workdir() -> str:
    root = build.get_oss_fuzz_root()
    workdir = os.path.join(root, "build", "work")
    os.makedirs(workdir, exist_ok=True)
    return workdir
