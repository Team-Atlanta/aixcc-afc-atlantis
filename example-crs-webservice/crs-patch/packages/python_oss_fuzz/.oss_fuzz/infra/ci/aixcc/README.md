# Benchmark Test

## Overview
This program is designed to run benchmark tests with various configurations. It allows users to execute tests across different modes, and enable or disable specific checks.

## Usage
To run the benchmark test, execute the script with the desired arguments.

### Command-line Arguments
The program accepts the following arguments:

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--run_mode` | `str` | `modified` | Specifies the benchmark execution mode. Options: `all`, `modified`, or `project`. |
| `--check_default_sanitizer_engine` | `flag` | `False` | Enables the quick check mode that uses only default sanitizer and engine. |
| `--skip_build_pov_patch` | `flag` | `False` | Skips the build, PoV (Proof of Vulnerability), and patch verification steps. |
| `--exit_on_error` | `flag` | `False` | Stops execution immediately if an error occurs. |
| `--project` | `str` | `None` | Specifies the project name. Required if `--run_mode` is set to `project`. |

### Example Command
Run the benchmark:
```
python3 infra/ci/benchmark_test.py <args>
```
