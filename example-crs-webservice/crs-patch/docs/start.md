# Getting Started Guide

## Initial Setup
Run the following commands:

```
uv sync
uv run scripts/setup.py
```

## Required Environment Variables
Set the following environment variables in your shell or `.env` file:
```
LITELLM_API_BASE=litellm_server
LITELLM_API_KEY=sk-...
```

## Prerequisites
- Commit ID of the target repository. For delta mode, provide the commit used for diffing.
- Reproducible information and PoC files. For OSS-Fuzz, reproducible reproduction data must be available.

## Challenge Project Setup

### 1. Create a Detection File
Create a TOML-based detection file using PoV information. Refer to:
```
crs-patch/scripts/benchmark/full/*.toml
```

### 2. Add a Project
Add the project under:
```
crs-patch/packages/python_oss_fuzz/.oss_fuzz/projects/[project_name]
```
Refer to Google OSS-Fuzz project definitions at:
```
https://github.com/google/oss-fuzz/tree/master/projects
```

### 3. Build Project Image
Run:
```bash
python3 crs-patch/packages/python_oss_fuzz/.oss_fuzz/infra/helper.py build_image [project_name]
```

## Running an Agent
```
Usage: python apps/**/[agent].py [OPTIONS]

Options:
  -cp, --challenge-project-directory DIRECTORY   [required]
  -d,  --detection-toml-file FILE               [required]
  -o,  --output-directory DIRECTORY
  -c,  --cache-directory DIRECTORY
  --timeout INTEGER
  --llm-cost-limit FLOAT
  --help                                        Show this message and exit.
```

### Example
```
uv run python apps/prism/prism_o4_mini.py -d detection.toml -cp ../libxml2 -o out
```

## Notes
Additional guides will be added when benchmark data becomes publicly available.