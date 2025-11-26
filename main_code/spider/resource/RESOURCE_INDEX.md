# Resource 目录结构说明

## 最终目录结构

### 📂 config/ - 配置文件
- `user_agent.json` - User-Agent 库 (22KB)
  - 存储在线平台识别所需的用户代理头信息

### 📂 data/ - 数据文件
- `2025.9.1_for_computer.xlsx` - Excel 数据源 (24KB)
- `account_name.json` - 账户姓名表 (7KB) | 更新日期: 11-19
- `current_mileage.json` - 里程数据 (5.5KB) | 更新日期: 11-19
- `file_folder_complete/` - 文件夹目录 | 19 个记录文件

### 📂 logs/ - 日志文件
- `exam_log.txt` (63KB) - 考试日志 (运行数据记录)
- `longrun_log.txt` (271B) | 最后更新: 11-20
- `redrun_log.txt` (2KB) | 最后更新: 5月10日
- `video_log.txt` (0KB) - 视频日志 (当前为空)

## 代码引用路径说明

### 核心文件引用
```python
# package/get_headers.py:7
"spider/resource/config/user_agent.json"

# package/query_spider.py:81
"spider/resource/data/account_name.json"

# package/query_spider.py:91
"spider/resource/data/current_mileage.json"

# package/read_excel.py:21
"spider/resource/data/2025.9.1_for_computer.xlsx"

# study_online/exam_spider.py:18
"spider/resource/logs/exam_log.txt"

# long_run/long_run.py:19
"spider/resource/logs/longrun_log.txt"

# red_run/red_run.py:16
"spider/resource/logs/redrun_log.txt"

# package/filter.py:11
"spider/resource/data/file_folder_complete"
```

### 目录分类逻辑
1. **config/** - 在线配置和网络识别
   - user_agent.json - HTTP 协议header代理

2. **data/** - 本地数据文件 (Excel/JSON格式)
   - 账户和名字映射表 (studentId -> studentName)
   - 运行时的用户总路程数据
   - 源Excel文件 (.xlsx)

3. **logs/** - 多层级系统运行日志记录
   - 分层log系统: 考试记录 / 长距离记录 / 视频轨迹记录

4. **data/file_folder_complete/** - 结构化数据
   - JSON格式日志: 已完成事务的JSON备份文件

## 更新日期: 11-22

### 文件变更历史
- 11-21 22:35 - account_name.json 最新更新 (添加4个新账户)
- 11-19 23:56 - current_mileage.json 添加最新里程记录
- 5-10   - redrun_log.txt 最后更新
- 5月6日 - exam_log.txt 初始化 (63KB运行数据)