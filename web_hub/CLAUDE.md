# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FunClip is a distributed video processing system that automatically processes videos from forum posts. It combines AI-powered content analysis with video editing capabilities. The system operates in a cluster architecture with monitoring nodes and worker nodes.

## Key Commands

### System Startup Commands

**Cluster Monitor Node (Forum monitoring and task distribution):**
```bash
cd cluster_monitor
python start_unified.py --mode production --port 8000
```

**Worker Node (Video processing):**
```bash
python start_lightweight.py --port 8005
python start_lightweight.py --port 8006  # Additional workers
```

**Test System Components:**
```bash
python start_lightweight.py --test --port 8005
```

### Environment Setup

**Install Dependencies (7-layer architecture):**
```bash
# Layer 1: Base system
pip install -r requirements/requirements-01-base.txt

# Layer 2: Platform-specific (choose one)
pip install -r requirements/requirements-02-platform-gpu.txt     # GPU
pip install -r requirements/requirements-02-platform-cpu.txt     # CPU
pip install -r requirements/requirements-02-platform-applem4.txt # Apple M4

# Layers 3-7: Core functionality
pip install -r requirements/requirements-03-text.txt
pip install -r requirements/requirements-04-ai.txt
pip install -r requirements/requirements-05-model-base.txt
pip install -r requirements/requirements-06-models.txt
pip install -r requirements/requirements-07-app.txt
```

**Check Dependencies:**
```bash
python scripts/check_dependencies.py
```

### Configuration

**Edit Machine List:**
```bash
notepad cluster_monitor/machines.txt
```

**Format: IP:PORT:PRIORITY**
```
localhost:8005:1
localhost:8006:2
192.168.1.100:8005:1
```

### API Testing

**Test Monitor Node:**
```bash
curl -X POST http://localhost:8000/api/start-monitoring
curl http://localhost:8000/api/machines/status
curl http://localhost:8000/api/cluster/status
```

**Test Worker Node:**
```bash
curl http://localhost:8005/api/worker/status
curl -X POST -H "Content-Type: application/json" \
  -d '{"url":"https://tts.lrtcai.com/forum.php?mod=viewthread&tid=121"}' \
  http://localhost:8005/api/worker/receive-task
```

## Architecture Overview

### Core System Structure

- **Cluster Architecture**: Master-worker pattern with monitoring and processing nodes
- **Language**: Python 3.8+ with modular design
- **Storage**: File-based with Redis for task queuing
- **AI Integration**: Multiple LLM providers (OpenAI, Qwen, DeepSeek, Kimi)
- **Video Processing**: FFmpeg with GPU acceleration support

### Key Directories

- `cluster_monitor/`: Monitor node implementation with web interface
- `lightweight/`: Worker node system with resource management
- `pre/`: Video processing pipeline with 9-stage workflow
- `funclip/`: Core video processing utilities and LLM integrations
- `requirements/`: 7-layer dependency architecture
- `cluster/`: Cluster deployment configurations

### Processing Pipeline (9 Stages)

1. **stage0.py**: Video transcoding and format standardization
2. **stage1.py**: Silent segment removal and audio optimization
3. **stage2.py**: Video repair and frame correction
4. **stage3.py**: ASR (Automatic Speech Recognition) processing
5. **stage4.py**: AI content analysis and processing
6. **stage5.py**: Video clipping based on AI analysis
7. **stage6.py**: Subtitle generation and embedding
8. **stage7.py**: Final output processing
9. **stage8.py**: File organization and cleanup

### Configuration System

- **Layered Configuration**: Environment variables override config files
- **Forum Integration**: Automatic post monitoring and processing
- **Resource Management**: CPU/GPU detection and allocation
- **Load Balancing**: Priority-based task distribution

## Development Guidelines

### Testing Workflow

1. Always test with `--test` flag first
2. Check Redis connectivity before starting cluster
3. Verify GPU drivers if using hardware acceleration
4. Test API endpoints before production deployment

### Debugging

- **Logs Location**: `logs/` directory with component-specific files
- **State Management**: `output/*/state.json` for process recovery
- **Performance Reports**: `logs/performance_reports/` for detailed analysis

### Configuration Updates

- Forum settings: `cluster_monitor/config.py`
- Worker settings: `lightweight/config.py`
- Video processing: `pre/stage/config.py`
- AI models: `funclip/config.py`

### Cluster Management

- Monitor interface: `http://localhost:8000`
- Worker interface: `http://localhost:8005`
- Add machines: Edit `cluster_monitor/machines.txt`
- Load balancing: Automatic based on priority and availability

## Common Issues

### Redis Connection
Ensure Redis server is running before starting any cluster components.

### GPU Acceleration
Check NVIDIA drivers and CUDA compatibility for h264_nvenc support.

### Network Configuration
Verify ports are not blocked by firewall when running distributed setup.

### Dependency Conflicts
Use the 7-layer installation approach to avoid package conflicts.
