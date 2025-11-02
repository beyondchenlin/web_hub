"""
IndexTTS2 论坛集成系统 - 启动脚本
启动完整的TTS和音色克隆论坛集成系统
"""

import os
import sys
import logging
import signal
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入系统模块
from tts_forum_integration_manager import TTSForumIntegrationManager
from tts_config import DATABASE_PATH

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/tts_system.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TTSSystemStarter:
    """TTS系统启动器"""
    
    def __init__(self):
        """初始化启动器"""
        logger.info("=" * 80)
        logger.info("🚀 IndexTTS2 论坛集成系统启动器")
        logger.info("=" * 80)
        
        self.manager = None
        self.running = False
    
    def setup_environment(self):
        """设置环境"""
        logger.info("\n📋 设置环境...")
        
        # 创建必要的目录
        directories = [
            'logs',
            'database',
            'output',
            'data'
        ]
        
        for directory in directories:
            Path(directory).mkdir(exist_ok=True)
            logger.info(f"  ✅ 目录已创建: {directory}")
        
        # 检查数据库
        if os.path.exists(DATABASE_PATH):
            logger.info(f"  ✅ 数据库已存在: {DATABASE_PATH}")
        else:
            logger.warning(f"  ⚠️ 数据库不存在: {DATABASE_PATH}")
            logger.info("  💡 请先运行 tts_forum_migration.py 初始化数据库")
        
        # 检查论坛凭证
        username = os.getenv('FORUM_USERNAME', 'AI剪辑助手')
        password = os.getenv('FORUM_PASSWORD', '594188@lrtcai')
        
        logger.info(f"\n🔐 论坛凭证:")
        logger.info(f"  用户名: {username}")
        logger.info(f"  密码: {'*' * len(password)}")
        
        logger.info("\n✅ 环境设置完成")
    
    def initialize_system(self):
        """初始化系统"""
        logger.info("\n🔧 初始化系统...")
        
        try:
            self.manager = TTSForumIntegrationManager()
            logger.info("✅ 系统初始化完成")
            return True
        
        except Exception as e:
            logger.error(f"❌ 系统初始化失败: {str(e)}")
            return False
    
    def start_system(self):
        """启动系统"""
        logger.info("\n▶️ 启动系统...")
        
        try:
            if not self.manager:
                logger.error("❌ 系统未初始化")
                return False
            
            self.manager.start()
            self.running = True
            
            logger.info("✅ 系统已启动")
            logger.info("\n" + "=" * 80)
            logger.info("📊 系统运行中...")
            logger.info("=" * 80)
            logger.info("\n功能:")
            logger.info("  ✅ 监控论坛新帖子")
            logger.info("  ✅ 自动识别TTS和音色克隆请求")
            logger.info("  ✅ 自动处理用户和权限")
            logger.info("  ✅ 调用TTS API生成音频")
            logger.info("  ✅ 自动上传结果到论坛")
            logger.info("\n按 Ctrl+C 停止系统")
            logger.info("=" * 80 + "\n")
            
            return True
        
        except Exception as e:
            logger.error(f"❌ 启动系统失败: {str(e)}")
            return False
    
    def run(self):
        """运行系统"""
        try:
            # 1. 设置环境
            self.setup_environment()
            
            # 2. 初始化系统
            if not self.initialize_system():
                logger.error("❌ 系统初始化失败，退出")
                return False
            
            # 3. 启动系统
            if not self.start_system():
                logger.error("❌ 系统启动失败，退出")
                return False
            
            # 4. 保持运行
            self._keep_running()
            
            return True
        
        except KeyboardInterrupt:
            logger.info("\n⏹️ 收到停止信号...")
            self.stop_system()
        
        except Exception as e:
            logger.error(f"❌ 系统运行异常: {str(e)}")
            self.stop_system()
            return False
    
    def _keep_running(self):
        """保持系统运行"""
        try:
            while self.running:
                time.sleep(1)
        
        except KeyboardInterrupt:
            pass
    
    def stop_system(self):
        """停止系统"""
        logger.info("\n⏹️ 停止系统...")
        
        try:
            if self.manager:
                self.manager.stop()
                self.running = False
            
            logger.info("✅ 系统已停止")
            logger.info("\n" + "=" * 80)
            logger.info("🎉 IndexTTS2 论坛集成系统已关闭")
            logger.info("=" * 80)
        
        except Exception as e:
            logger.error(f"❌ 停止系统异常: {str(e)}")
    
    def signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info("\n📢 收到信号，准备停止...")
        self.stop_system()
        sys.exit(0)


def main():
    """主函数"""
    starter = TTSSystemStarter()
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, starter.signal_handler)
    signal.signal(signal.SIGTERM, starter.signal_handler)
    
    # 运行系统
    success = starter.run()
    
    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

