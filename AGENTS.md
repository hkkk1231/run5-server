# Repository Guidelines

This project automates HNFNU PE requirements, so contributions must keep scraping logic, credential handling, and logging aligned with existing modules.

## Project Structure & Module Organization
- All runnable code lives in `main_code/`; `paths.py` exposes absolute `Path` objects and must be the single source for filesystem references.
- Automation modules sit under `main_code/spider/`: `long_run/`, `red_run/`, and `study_online/` each contain entry scripts plus helpers; cross-cutting utilities reside in `spider/package/` (`auth`, `core`, `data`, `network`).
- Shared assets live in `spider/resource/` (`data/` for Excel/JSON inputs, `config/` for UA pools, `logs/` for module logs); keep sensitive files out of commits when possible.
- Currently there are no committed integration tests; when you add targeted tests, keep them beside the module they exercise (e.g., under `spider/red_run/`) and follow the existing log/fixture conventions.

## Build, Test, and Development Commands
Run from `/root/desktop/run5-server/main_code`:
```bash
python3 -m spider.long_run.long_run      # simulate daily 4 km runs
python3 -m spider.red_run.red_run        # process red activity queue
python3 -m spider.study_online.main      # orchestrate video + exam automation
```
Each script supports both `-m` execution and direct invocation via the built-in `sys.path` bootstrap; prefer the module form when integrating with tooling.

## Coding Style & Naming Conventions
- Target Python 3.8; use four-space indentation and type hints where practical.
- Apply `snake_case` for functions/modules, `CamelCase` for classes, and descriptive constants in `UPPER_SNAKE_CASE`.
- Always import paths via `from paths import ...` instead of hardcoding strings, and use `SessionManager` from `spider.package.auth.session_manager` to obtain authenticated sessions.
- Configure loggers through `spider.package.core.logger_manager.setup_logger` so output lands in `spider/resource/logs/`.

## Testing Guidelines
- Favor deterministic integration tests that hit staging accounts; store helpers beside the module they exercise.
- Name test files `test_<feature>.py`, emit structured logs, and write outputs to the module-specific log file for later inspection.
- Before opening a PR, execute the relevant module(s) (long-run, red-run, study-online) and verify their log files reflect expected success paths with no stack traces; add/update targeted tests under the corresponding module if you introduce new scenarios.

## Commit & Pull Request Guidelines
- Follow the existing history of short, present-tense summaries (often Chinese, e.g., “修复红色跑404错误”), and mention the affected module when possible.
- Pull requests should describe the scenario, modules touched, data files required, and include sanitized log snippets or screenshots of successful runs. Link related tracking issues and note any manual steps for reviewers.

## Security & Configuration Tips
- Treat everything under `spider/resource/data/` as sensitive; mask student identifiers and tokens before sharing logs or diffs.
- Do not commit environment-specific secrets—store them in ignored JSON/Excel files and reference them via `paths.py`.
- When modifying scraping endpoints or headers, update `spider/package/network/get_headers.py` or config files instead of scattering literals.
