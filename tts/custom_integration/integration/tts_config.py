"""
IndexTTS2 音色克隆系统配置文件
"""
import os
from pathlib import Path

# 基础路径
BASE_DIR = Path(__file__).parent
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# ==================== 数据库配置 ====================
# TTS系统专用数据库（与论坛数据库分离）
DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "tts_voice_system.db"

# ==================== IndexTTS2 API配置 ====================
# 现有的IndexTTS2服务配置
INDEXTTS2_HOST = os.getenv("INDEXTTS2_HOST", "localhost")
INDEXTTS2_PORT = int(os.getenv("INDEXTTS2_PORT", "9880"))
INDEXTTS2_API_URL = f"http://{INDEXTTS2_HOST}:{INDEXTTS2_PORT}"

# ==================== Web服务配置 ====================
# 新的TTS Web服务端口（避免与现有服务冲突）
TTS_WEB_HOST = os.getenv("TTS_WEB_HOST", "0.0.0.0")
TTS_WEB_PORT = int(os.getenv("TTS_WEB_PORT", "8860"))  # 新端口

# 现有服务端口（保留）
EXISTING_GRADIO_PORT = 7860  # cy_app使用的端口

# ==================== 文件存储配置 ====================
# 复用现有的voices目录
VOICES_DIR = BASE_DIR / "voices"
VOICES_PUBLIC_DIR = VOICES_DIR / "public"      # 公共音色
VOICES_USERS_DIR = VOICES_DIR / "users"        # 用户音色

# 复用现有的outputs目录
OUTPUTS_DIR = BASE_DIR / "outputs"
OUTPUTS_USERS_DIR = OUTPUTS_DIR / "users"      # 用户输出

# 上传临时目录
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_TEMP_DIR = UPLOADS_DIR / "temp"

# 确保目录存在
for dir_path in [DATABASE_DIR, VOICES_PUBLIC_DIR, VOICES_USERS_DIR, 
                 OUTPUTS_USERS_DIR, UPLOADS_TEMP_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ==================== 用户配额配置 ====================
DEFAULT_VOICE_QUOTA = 20           # 默认音色数量配额
DEFAULT_STORAGE_QUOTA_MB = 500     # 默认存储空间配额(MB)
MAX_FILE_SIZE_MB = 100             # 单个文件最大大小(MB)

# ==================== 音频参数配置 ====================
SAMPLE_RATE = 22050                # 采样率
AUDIO_FORMAT = "wav"               # 音频格式
MIN_AUDIO_DURATION = 5             # 最小音频时长(秒)
MAX_AUDIO_DURATION = 60            # 最大音频时长(秒)
RECOMMENDED_MIN_DURATION = 10      # 推荐最小时长(秒)
RECOMMENDED_MAX_DURATION = 25      # 推荐最大时长(秒)

# 支持的音频格式
ALLOWED_AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.m4a', '.aac'}
# 支持的视频格式（用于提取音频）
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}

# ==================== Session配置 ====================
SECRET_KEY = os.getenv("SECRET_KEY", "indextts2-voice-clone-secret-key-change-in-production")
SESSION_LIFETIME_HOURS = 24        # Session有效期(小时)

# ==================== 日志配置 ====================
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_FILE_BACKUP_COUNT = 5

# ==================== API配置 ====================
API_TIMEOUT = 300                  # API请求超时时间(秒)
API_MAX_RETRIES = 3                # API最大重试次数
API_RETRY_DELAY = 2                # 重试延迟(秒)

# ==================== 性能配置 ====================
MAX_CONCURRENT_TASKS = 4           # 最大并发任务数
CACHE_MAX_SIZE = 100               # 缓存最大条目数
CACHE_TTL_SECONDS = 300            # 缓存有效期(秒)

# ==================== 安全配置 ====================
# 密码哈希配置
PASSWORD_HASH_ALGORITHM = "sha256"
PASSWORD_SALT_LENGTH = 16

# 文件上传安全
UPLOAD_SCAN_ENABLED = False        # 是否启用文件扫描
UPLOAD_ALLOWED_MIME_TYPES = [
    'audio/wav', 'audio/mpeg', 'audio/flac', 'audio/mp4',
    'video/mp4', 'video/x-msvideo', 'video/quicktime'
]

# ==================== 功能开关 ====================
ENABLE_USER_REGISTRATION = True    # 是否允许用户注册
ENABLE_PUBLIC_VOICES = True        # 是否启用公共音色库
ENABLE_VOICE_SHARING = False       # 是否允许用户分享音色
ENABLE_USAGE_STATISTICS = True     # 是否启用使用统计

# ==================== 现有系统集成 ====================
# 复用现有的batch_processor
USE_EXISTING_BATCH_PROCESSOR = True

# 现有音色文件路径（用于导入）
EXISTING_VOICES_DIR = VOICES_DIR
EXISTING_VOICE_FILES = [
    "1111.pt",
    "女主播.pt",
    "无底噪.pt",
    "盼盼.pt",
    "舒玥.pt",
    "苏瑶.pt",
    "评书.pt"
]

# ==================== 开发/生产环境 ====================
ENV = os.getenv("ENV", "development")  # development, production
DEBUG = ENV == "development"

# 生产环境额外配置
if ENV == "production":
    # 生产环境使用更严格的配置
    SESSION_LIFETIME_HOURS = 12
    LOG_LEVEL = "WARNING"
    ENABLE_USER_REGISTRATION = False  # 生产环境可能需要审核

# ==================== 显示配置信息 ====================
def print_config():
    """打印当前配置信息（用于调试）"""
    print("=" * 60)
    print("IndexTTS2 音色克隆系统配置")
    print("=" * 60)
    print(f"环境: {ENV}")
    print(f"数据库: {DATABASE_PATH}")
    print(f"IndexTTS2 API: {INDEXTTS2_API_URL}")
    print(f"Web服务: http://{TTS_WEB_HOST}:{TTS_WEB_PORT}")
    print(f"音色目录: {VOICES_DIR}")
    print(f"输出目录: {OUTPUTS_DIR}")
    print(f"日志目录: {LOG_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    print_config()

