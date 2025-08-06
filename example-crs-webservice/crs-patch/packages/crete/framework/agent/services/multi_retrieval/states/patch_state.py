import difflib
import os
import re
from enum import Enum, auto
from typing import Any

from langchain_core.messages import BaseMessage
from pydantic import BaseModel


class PatchAction(Enum):
    ANALYZE_ISSUE = auto()
    ANALYZE_RETRIEVAL = auto()
    EVALUATE = auto()
    RETRIEVE = auto()
    PATCH = auto()
    DONE = auto()


class PatchStatus(Enum):
    INITIALIZED = auto()
    UNCOMPILABLE = auto()
    COMPILABLE = auto()
    VULNERABLE = auto()
    WRONG = auto()
    TESTS_FAILED = auto()
    SOUND = auto()
    UNKNOWN = auto()


class CodeSnippet(BaseModel):
    repo_path: str = ""
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    content: str = ""

    def __eq__(self, value: Any) -> bool:
        if not isinstance(value, CodeSnippet):
            return False
        return (
            self.repo_path == value.repo_path
            and self.file_path == value.file_path
            and self.line_start == value.line_start
            and self.line_end == value.line_end
            and self.content == value.content
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.repo_path,
                self.file_path,
                self.line_start,
                self.line_end,
                self.content,
            )
        )


class PatchState(BaseModel):
    patch_action: PatchAction = PatchAction.EVALUATE
    patch_status: PatchStatus = PatchStatus.INITIALIZED
    messages: list[BaseMessage] = []
    repo_path: str = ""
    repo_lang: str = ""
    diff: str = ""
    n_evals: int = 0
    issue: str | None = None
    retrieved: str | None = None
    tests_log: str = ""
    applied_patches: list[CodeSnippet] = []


class CodeDiff(BaseModel):
    patches_by_file: dict[str, set[CodeSnippet]] = {}
    full_code_lines_by_file: dict[str, list[str]] = {}
    diff_by_file: dict[str, str] = {}
    failed_patches: set[CodeSnippet] = set()
    applied_patches: list[CodeSnippet] = []

    @property
    def concatenated_diff(self) -> str:
        return "\n".join(self.diff_by_file.values())

    def has_failed_patches(self) -> bool:
        return len(self.failed_patches) > 0

    def clear(self) -> None:
        self.patches_by_file = {}
        self.full_code_lines_by_file = {}
        self.diff_by_file = {}
        self.failed_patches = set()

    def add_patches(
        self, patches: list[CodeSnippet], filter_out_fuzz_files: bool = True
    ) -> None:
        self.full_code_lines_by_file = {}
        self.diff_by_file = {}
        self.failed_patches = set()

        # Filter out and aggregate patches by file
        for patch in patches:
            # Check empty content
            if patch.content == "":
                self.failed_patches.add(patch)
                continue

            # Check file existence
            if patch.repo_path == "" or patch.file_path == "":
                self.failed_patches.add(patch)
                continue
            file_path = os.path.join(patch.repo_path, patch.file_path)
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                self.failed_patches.add(patch)
                continue

            if patch.file_path not in self.full_code_lines_by_file:
                with open(file_path, "rb") as f:
                    full_code_lines = [
                        line.decode(encoding="utf-8", errors="replace")
                        for line in f.readlines()
                    ]
                self.full_code_lines_by_file[patch.file_path] = full_code_lines
            else:
                full_code_lines = self.full_code_lines_by_file[patch.file_path]

            # Check line range
            if patch.line_start < 1 or patch.line_end > len(full_code_lines):
                self.failed_patches.add(patch)
                continue

            if patch.file_path not in self.patches_by_file:
                self.patches_by_file[patch.file_path] = set()
            self.patches_by_file[patch.file_path].add(patch)

        # Generate multiple diffs
        line_number_regex = r"^\d+:"
        for file_path, grouped_patches in self.patches_by_file.items():
            valid_patches: list[CodeSnippet] = []
            for patch in grouped_patches:
                if patch in self.failed_patches:
                    continue
                valid_patches.append(patch)

            if len(valid_patches) == 0:
                continue

            patches_sorted = sorted(valid_patches, key=lambda x: x.line_start)
            if file_path not in self.full_code_lines_by_file:
                valid_patch = patches_sorted[0]
                full_file_path = os.path.join(
                    valid_patch.repo_path, valid_patch.file_path
                )
                if not os.path.exists(full_file_path) or not os.path.isfile(
                    full_file_path
                ):
                    # This case should be already filtered out
                    continue
                with open(full_file_path, "rb") as f:
                    full_code_lines = [
                        line.decode(encoding="utf-8", errors="replace")
                        for line in f.readlines()
                    ]
            else:
                full_code_lines = self.full_code_lines_by_file[file_path]
            patched_full_code_lines: list[str] = []
            last_line_end = 0

            for patch in patches_sorted:
                if patch.line_start <= last_line_end:
                    self.failed_patches.add(patch)
                    continue

                patched_full_code_lines.extend(
                    full_code_lines[last_line_end : patch.line_start - 1]
                )
                patched_code_lines = [f"{line}\n" for line in patch.content.split("\n")]
                if patched_code_lines[-1] == "\n":
                    patched_code_lines = patched_code_lines[:-1]

                if len(patched_code_lines) > 0:
                    # Check line numbers are in the patch and remove them
                    if ":" in patched_code_lines[0]:
                        line_number_matches = [
                            re.match(line_number_regex, line)
                            for line in patched_code_lines
                        ]
                        if all(line_number_matches):
                            patched_code_lines = [
                                line.split(":", 1)[1] for line in patched_code_lines
                            ]

                # NOTE: We handle mixed line endings here for git apply issues.
                if len(full_code_lines) > 0 and full_code_lines[0].endswith("\r\n"):
                    patched_code_lines = [
                        line[:-1] + "\r\n" if line.endswith("\n") else line
                        for line in patched_code_lines
                    ]

                patched_full_code_lines.extend(patched_code_lines)
                last_line_end = patch.line_end

                self.applied_patches.append(patch)

            patched_full_code_lines.extend(full_code_lines[last_line_end:])

            # Unified diff per file
            diff_lines = difflib.unified_diff(
                full_code_lines,
                patched_full_code_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="\n",
            )

            validated_diff_lines: list[str] = []
            for line in diff_lines:
                if line.endswith("\n"):
                    validated_diff_lines.append(line)
                    continue

                # Handle files without trailing newline
                if line.startswith("-"):
                    validated_diff_lines.append(line + "\n")
                    validated_diff_lines.append("\\ No newline at end of file\n")
                elif line.startswith("+"):
                    validated_diff_lines.append(line + "\n")
                elif line.startswith(" "):
                    validated_diff_lines.append("-" + line[1:] + "\n")
                    validated_diff_lines.append("\\ No newline at end of file\n")
                    validated_diff_lines.append("+" + line[1:] + "\n")
                else:
                    validated_diff_lines.append(line)

            diff = "".join(validated_diff_lines)
            if diff == "":
                for patch in patches_sorted:
                    self.failed_patches.add(patch)
                continue

            # Filter out fuzz files if needed
            # NOTE: This is a hardcoded filter for fuzz files.
            if filter_out_fuzz_files and "fuzz" in file_path:
                for patch in patches_sorted:
                    self.failed_patches.add(patch)
                continue

            self.diff_by_file[file_path] = diff


MULTIPLE_PATCHES_TEMPLATE = """\
<patches>
{patches}
</patches>"""

SINGLE_PATCH_TEMPLATE = """\
<patch>
<original_code>
```
{original_code}
```
</original_code>
<code_lines_to_replace>
{orig_file_path}:{orig_line_start}-{orig_line_end}
</code_lines_to_replace>
<patched_code>
```
{patched_code}
```
</patched_code>
</patch>"""


def format_patches_to_str(
    patches: list[CodeSnippet], add_line_numbers: bool = True
) -> str:
    if len(patches) == 0:
        return ""
    formatted_patches: list[str] = []
    for patch in patches:
        abs_file_path = os.path.join(patch.repo_path, patch.file_path)
        if not os.path.exists(abs_file_path) or not os.path.isfile(abs_file_path):
            continue
        with open(abs_file_path, "r", encoding="utf-8", errors="replace") as f:
            full_code_lines = f.readlines()
        if patch.line_start < 1 or patch.line_end > len(full_code_lines):
            continue
        if patch.line_start > patch.line_end:
            continue
        original_code_lines = full_code_lines[patch.line_start - 1 : patch.line_end]

        if add_line_numbers:
            original_code_lines = [
                f"{line_number}:{line}"
                for line_number, line in enumerate(
                    original_code_lines, start=patch.line_start
                )
            ]
        original_code = "".join(original_code_lines)
        if len(original_code) > 0 and original_code[-1] == "\n":
            original_code = original_code[:-1]
        patched_code = patch.content
        if len(patched_code) > 0 and patched_code[-1] == "\n":
            patched_code = patched_code[:-1]

        # Filter out line numbers from the patched code
        patched_code_lines = patched_code.split("\n")
        if all(":" in line for line in patched_code_lines):
            patched_code_lines = [line.split(":", 1)[1] for line in patched_code_lines]
            patched_code = "\n".join(patched_code_lines)

        formatted_patches.append(
            SINGLE_PATCH_TEMPLATE.format(
                original_code=original_code,
                orig_file_path=patch.file_path,
                orig_line_start=patch.line_start,
                orig_line_end=patch.line_end,
                patched_code=patched_code,
            )
        )
    formatted_patches_str = MULTIPLE_PATCHES_TEMPLATE.format(
        patches="\n".join(formatted_patches)
    )
    return formatted_patches_str
