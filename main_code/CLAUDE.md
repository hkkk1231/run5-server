# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **student physical education (PE) tracking automation system** for Hunan First Normal University (湖南第一师范学院). The system automates various PE activities including long-distance running, red activities, and online learning/exams through web scraping and API interaction with the university's sports platform (`https://lb.hnfnu.edu.cn`).

### Purpose
- **Long Run Module** (`spider/long_run/long_run.py`): Automates daily running tracking (4km requirement)
- **Red Run Module** (`spider/red_run/red_run.py`): Handles red theme activities/running
- **Study Online Module** (`spider/study_online/`): Manages online video learning and exam completion
- **Core Package** (`spider/package/`): Provides shared authentication, network, data processing, and logging utilities

## Common Development Commands

### Running Individual Modules

**Long Run (Daily 4km Running):**
```bash
cd /root/desktop/run5-server/main_code
python3 -m spider.long_run.long_run
# OR
python3 spider/long_run/long_run.py  # Note: Uses compatibility layer for direct execution
```

**Red Run (Activities):**
```bash
python3 -m spider.red_run.red_run
# OR
python3 spider/red_run/red_run.py
```

**Study Online (Videos & Exams):**
```bash
python3 -m spider.study_online.main
```

### Import Compatibility Note
All modules implement **dual import compatibility**:
- Direct execution support: Adds project root to `sys.path` and uses absolute imports
- Module execution support: Uses relative imports

The code handles both patterns (see `long_run.py:11-40`). When running directly, use absolute imports like `from main_code.spider.package.auth.login import LoginConfig`.

### Python Environment
- **Version**: Python 3.8.10
- **Key Dependencies**: requests, concurrent.futures, datetime, pathlib

## Code Architecture

### Directory Structure
```
main_code/
├── paths.py                           # Unified path management (pathlib-based)
├── spider/
│   ├── package/                       # Core shared modules
│   │   ├── auth/                      # Authentication & session management
│   │   │   ├── session_manager.py     # Unified session manager (HIGH-001 fixed)
│   │   │   ├── error_manager.py       # Error account tracking
│   │   │   └── login.py               # Login functions
│   │   ├── core/                      # Core utilities
│   │   │   ├── logger_manager.py      # Logging configuration
│   │   │   ├── common_utils.py        # Utility functions
│   │   │   └── error_handler.py       # Error handling decorators
│   │   ├── data/                      # Data processing
│   │   │   ├── read_excel.py          # Excel file reading
│   │   │   ├── filter.py              # User filtering logic
│   │   │   └── update_excel_for_computer.py
│   │   ├── network/                   # Network utilities
│   │   │   ├── get_headers.py         # HTTP headers management
│   │   │   └── get_ip_port.py
│   │   └── query_spider.py            # Query utilities
│   ├── long_run/                      # Long distance running automation
│   │   ├── long_run.py                # Main runner script
│   │   └── fake_key.py                # Timestamp encryption for API
│   ├── red_run/                       # Red activities automation
│   │   └── red_run.py
│   ├── study_online/                  # Online learning & exams
│   │   ├── video_spider.py            # Video watching automation
│   │   ├── exam_spider.py             # Exam completion
│   │   ├── completion_status.py       # Status tracking (JSON-based)
│   │   └── main.py                    # Main coordinator
│   └── resource/                      # Data & configuration
│       ├── data/                      # User data (Excel, JSON)
│       │   ├── 2025.9.1_for_computer.xlsx
│       │   ├── account_name.json
│       │   ├── current_mileage.json
│       │   └── file_folder_complete/
│       ├── config/                    # Configuration files
│       │   └── user_agent.json
│       └── logs/                      # Log files
│           ├── longrun_log.txt
│           ├── redrun_log.txt
│           └── exam_log.txt
```

### Key Architectural Patterns

#### 1. Unified Session Management (package/auth/)
- **Purpose**: Centralized session handling for authenticated requests
- **Implementation**: `SessionManager` class (`session_manager.py`) maintains active sessions, tokens, and lifecycle
- **Fix Applied**: Resolved HIGH-001 (session management chaos) - now all modules use consistent session approach
- **Usage**:
  ```python
  from package.auth.session_manager import session_manager
  session = session_manager.get_session(account)
  ```

#### 2. Unified Path Management (paths.py)
- **Purpose**: Single source of truth for all file paths using `pathlib.Path`
- **Implementation**: Defines constants for all directories and files
- **All paths are absolute** and automatically calculated from project root
- **Key Paths**:
  - `SPIDER_LOGS_DIR` - Log directory
  - `SPIDER_DATA_DIR` - Data files
  - `ACCOUNT_NAME_FILE` - User account mappings
  - `CURRENT_MILEAGE_FILE` - Running mileage data

#### 3. Dual Import Pattern (Compatibility Layer)
Every script implements both direct execution and module import:
```python
if __name__ == "__main__":
    # Add project root to sys.path
    project_root = os.path.dirname(os.path.dirname(...))
    sys.path.insert(0, project_root)
    # Use absolute imports
    from main_code.spider.package.auth.login import LoginConfig
else:
    # Use relative imports when imported as module
    from ..package.auth.login import LoginConfig
```

#### 4. User Filtering System (package/data/filter.py)
- **Purpose**: Filter users based on completion status and requirements
- **Key Functions**:
  - `main()` - Get users needing long run
  - `get_online_learning_and_exam_users()` - Get users needing study/exam
- **Data Sources**: Reads from `account_name.json`, `current_mileage.json`, Excel file

#### 5. Error Account Management (package/auth/error_manager.py)
- **Purpose**: Track and manage failed accounts
- **Classification**:
  - Password errors (permanent skip)
  - Temporary errors (retry)
- **Fix Applied**: Resolved HIGH-002 (inconsistent error handling)

#### 6. Logging System (package/core/logger_manager.py)
- **Purpose**: Unified logging across all modules
- **Implementation**: `setup_logger()` function with module-specific log files
- **Fix Applied**: Resolved LOW-003 (unified logging)

### Module-Specific Architecture

#### Long Run Module (long_run/long_run.py)
- **Flow**: Login → Start Running → End Running → Query Result
- **Key Features**:
  - Random but logical parameter generation (speed, distance, time)
  - Geographic coordinates within school stadium
  - Timestamp encryption for API requests (via `fake_key.py`)
  - Retry mechanism (up to 10 attempts)
  - Status tracking in `current_mileage.json`
- **API Endpoints**:
  - `POST /school/student/addLMRanking` - Start running
  - `POST /school/student/longMarchSpeed` - End running

#### Red Run Module (red_run/red_run.py)
- **Purpose**: Automated red theme activities
- **Features**:
  - Concurrent processing with ThreadPoolExecutor
  - Queue-based task management
  - Session management integration

#### Study Online Module (study_online/)
- **Components**:
  - `video_spider.py` - Automates video watching
  - `exam_spider.py` - Handles exam completion
  - `completion_status.py` - JSON-based status tracking
- **Status Management**: Uses JSON files to track completion (avoiding concurrent write issues)

### Resource Management

#### Data Files (resource/data/)
- **2025.9.1_for_computer.xlsx**: Source of truth for all users
- **account_name.json**: Student ID → Name mapping
- **current_mileage.json**: Daily running records
- **file_folder_complete/**: Date-stamped completion logs

#### Configuration (resource/config/)
- **user_agent.json**: HTTP User-Agent library for request rotation

#### Logs (resource/logs/)
- **Separate log files per module**: `longrun_log.txt`, `redrun_log.txt`, `exam_log.txt`
- **Structured logging**: INFO, WARNING, ERROR, CRITICAL levels

### Recent Refactoring (修复清单.md)

#### Completed Fixes (HIGH priority):
- **HIGH-001**: Session management chaos → Unified SessionManager
- **HIGH-002**: Error account handling inconsistency → Centralized error tracking
- **HIGH-003**: File path handling → Unified path management with pathlib
- **LOW-001**: Code duplication → Common utilities extracted
- **LOW-003**: Inconsistent logging → Centralized logger setup

#### Known Issues (MEDIUM/LOW priority):
- **MEDIUM-001**: No request rate limiting (affects red_run.py concurrency)
- **MEDIUM-002**: No file locking for status files (completion_status.py)
- **LOW-002**: Hardcoded configuration values
- **LOW-004**: Incomplete exception handling in some network requests

## Development Workflow

### Adding New Features
1. **Check package structure**: Most functionality should go in `spider/package/`
2. **Use SessionManager**: For any authenticated requests, use the centralized session manager
3. **Follow dual import pattern**: Support both direct execution and module import
4. **Use paths.py**: Never hardcode paths; use constants from `paths.py`
5. **Add logging**: Use `setup_logger()` from `common_utils.py`

### Testing
```bash
# Test path configuration
python3 /root/desktop/run5-server/test_file_path.py

# Test import compatibility
python3 /root/desktop/run5-server/test_import.py
```

### Key Entry Points
- **Long run**: `spider/long_run/long_run.py::main()`
- **Red run**: `spider/red_run/red_run.py::main()` (check line 214)
- **Study online**: `spider/study_online/main.py::video_and_exam()`

## Important Notes

### API Integration
- **Base URL**: `https://lb.hnfnu.edu.cn`
- **Authentication**: Bearer token (retrieved via login)
- **Headers**: Rotated User-Agent from `user_agent.json`
- **Geographic Constraints**: Coordinates limited to school stadium (28.195932-28.197426 lat, 112.86050-112.86125 lon)

### Data Flow
1. Read Excel → JSON state files
2. Filter users based on requirements
3. For each user: Login → Perform action → Update status
4. Log results to module-specific log files

### Security Considerations
- **Password management**: Stored in Excel, loaded at runtime
- **Token storage**: In-memory (cleared on exit)
- **Error tracking**: Failed accounts logged for analysis

### Performance Characteristics
- **Long run**: Sequential processing (one user at a time)
- **Red run**: Concurrent with ThreadPoolExecutor
- **Study online**: Sequential with status checks

## References

- **Resource Index**: `spider/resource/RESOURCE_INDEX.md` - Detailed file inventory
- **Fix List**: `spider/resource/list/修复清单.md` - Known issues and resolutions
- **Architecture**: Centralized package structure (`spider/package/`) for shared utilities
