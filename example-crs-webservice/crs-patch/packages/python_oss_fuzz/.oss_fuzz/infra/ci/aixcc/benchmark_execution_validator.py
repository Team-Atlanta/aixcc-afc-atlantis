from aixcc import get_harnesses
from prepare_sources import apply_patches, apply_ref_diff, prepare_sources
from run_helper import build_benchmark, run_pov
from utils import ExecJobType, JobContext, TaskMode


def _delta_base_check(job: JobContext) -> None:
    harnesses = get_harnesses(job.language, job.benchmark)

    src_dir_path, _, _ = prepare_sources(job.task, job.language, job.benchmark)
    if job.task.mode == TaskMode.DELTA:
        build_benchmark(
            job.language, job.benchmark, job.engine, job.sanitizer, src_dir_path
        )

        for harness in harnesses:
            for cpv in harness.cpvs:
                if job.cpvs_in_context is not None:
                    if cpv.name not in job.cpvs_in_context:
                        continue
                if cpv.sanitizer == job.sanitizer and job.engine == "libfuzzer":
                    run_pov(
                        job.language,
                        job.benchmark,
                        harness.name,
                        cpv.name,
                        cpv.error_token,
                        True,
                    )


def _delta_ref_check(
    job: JobContext,
) -> None:
    harnesses = get_harnesses(job.language, job.benchmark)

    src_dir_path, diff_tarball_path, repo_tars_path = prepare_sources(
        job.task, job.language, job.benchmark
    )
    apply_ref_diff(diff_tarball_path, repo_tars_path, src_dir_path)
    build_benchmark(
        job.language, job.benchmark, job.engine, job.sanitizer, src_dir_path, True
    )

    for harness in harnesses:
        for cpv in harness.cpvs:
            if job.cpvs_in_context is not None:
                if cpv.name not in job.cpvs_in_context:
                    continue
            if cpv.sanitizer == job.sanitizer and job.engine == "libfuzzer":
                run_pov(
                    job.language,
                    job.benchmark,
                    harness.name,
                    cpv.name,
                    cpv.error_token,
                    False,
                )


def _full_base_check(
    job: JobContext,
) -> None:
    harnesses = get_harnesses(job.language, job.benchmark)

    src_dir_path, _, _ = prepare_sources(job.task, job.language, job.benchmark)
    build_benchmark(
        job.language, job.benchmark, job.engine, job.sanitizer, src_dir_path, True
    )

    for harness in harnesses:
        for cpv in harness.cpvs:
            if cpv.sanitizer == job.sanitizer and job.engine == "libfuzzer":
                run_pov(
                    job.language,
                    job.benchmark,
                    harness.name,
                    cpv.name,
                    cpv.error_token,
                    False,
                )


def _cpv_check(
    job: JobContext,
) -> None:
    src_dir_path, diff_tarball_path, repo_tars_path = prepare_sources(
        job.task, job.language, job.benchmark
    )
    if job.task.mode == TaskMode.DELTA:
        apply_ref_diff(diff_tarball_path, repo_tars_path, src_dir_path)

    apply_patches(
        job.language,
        job.benchmark,
        job.harness.name,
        f"{job.cpv.name}.diff",
        src_dir_path,
        False,
    )
    build_benchmark(
        job.language, job.benchmark, job.engine, job.sanitizer, src_dir_path
    )
    run_pov(
        job.language,
        job.benchmark,
        job.harness.name,
        job.cpv.name,
        job.cpv.error_token,
        True,
    )
    apply_patches(
        job.language,
        job.benchmark,
        job.harness.name,
        f"{job.cpv.name}.diff",
        src_dir_path,
        True,
    )


def check_benchmark_execution(job: JobContext) -> None:
    if job.job_type == ExecJobType.DELTA_BASE_CHECK:
        _delta_base_check(job)
    elif job.job_type == ExecJobType.DELTA_REF_CHECK:
        _delta_ref_check(job)
    elif job.job_type == ExecJobType.FULL_BASE_CHECK:
        _full_base_check(job)
    elif job.job_type == ExecJobType.CPV_CHECK:
        _cpv_check(job)
    else:
        raise Exception(f"[Error] Unknown Job Type {job.job_type}")
