# Repository Guidelines

## Project Structure & Module Organization
- `web_hub/`: 集群框架核心，含监控节点 (`cluster_monitor/`)、轻量工作节点 (`lightweight/`)、模块适配层 (`modules/`) 及依赖脚本。
- `services/`: 面向任务调度的服务封装，例如 `services/tts_service/` 对接自研 TTS 集成。
- `tts/`: TTS 相关代码。`indextts2/` 保留原开源版本；`custom_integration/` 提供论坛集成与启动脚本。
- `shared/`: 预留的共享组件目录；`docs/`、`logs/`、`web_hub/data/` 主要存放文档与运行数据（多为忽略文件）。

## Build, Test, and Development Commands
- `python web_hub/cluster_monitor/start_unified.py --mode production --port 8000`：启动监控节点。
- `python web_hub/start_lightweight.py --port 8005`：启动轻量工作节点进行视频任务。
- `python tts/custom_integration/run_tts_system.py`：单独运行论坛 TTS 集成流程。
- `python -m pytest tts/custom_integration/integration/test_tts_system.py`：示例单测入口，可按需扩展。

## Coding Style & Naming Conventions
- Python 全局使用 4 空格缩进，遵循 PEP 8 与类型提示；模块名使用小写下划线，类名遵循 PascalCase。
- 日志使用 `logging` 标准库，日志文件写入 `logs/`（已在 `.gitignore` 中忽略）。
- 文档文件命名以中文或英文说明结尾，存放于 `docs/` 或对应模块的 `docs/` 子目录。

## Testing Guidelines
- 当前单元测试位于 `tts/custom_integration/integration/test_*.py`，使用 `pytest`。
- 新增测试文件命名为 `test_<module>.py`，放在对应模块同级目录的 `tests/` 或 `test_*.py` 中。
- 关键业务逻辑需覆盖正常流程与异常路径；提交前运行 `pytest` 并确保通过。

## Commit & Pull Request Guidelines
- 提交信息遵循简洁动词风格，如 `Add TTS adapter skeleton`、`Fix forum crawler login`.
- 每个 PR 应说明变更摘要、测试结果及受影响模块，必要时附带运行截图或日志。
- 若涉及配置或文档更新，务必同步改动 `docs/` 并在 PR 描述中注明。

## Security & Configuration Tips
- 环境变量使用 `.env` 或系统环境配置，示例见 `web_hub/.env.example`；勿将真实凭证提交仓库。
- 大型模型权重与数据库备份存放于 `tts/indextts2/`、`web_hub/data/`，已默认忽略，请勿手动加入版本控制。
