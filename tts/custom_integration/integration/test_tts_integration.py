"""
IndexTTS2 论坛集成系统 - 集成测试
测试端到端的系统功能
"""

import os
import sys
import time
import logging
import unittest
from pathlib import Path

# 确保 shared 可导入
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.forum_config import load_forum_settings

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入模块
from tts_forum_integration_manager import TTSForumIntegrationManager
from tts_forum_crawler_integration import TTSForumCrawlerIntegration
from tts_forum_sync import TTSForumUserSync
from tts_request_parser import TTSRequestParser

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestTTSIntegration(unittest.TestCase):
    """集成测试 - 测试端到端功能"""
    
    def setUp(self):
        """测试前准备"""
        logger.info("\n" + "=" * 80)
        logger.info("🧪 集成测试准备")
        logger.info("=" * 80)
    
    def test_01_crawler_integration(self):
        """测试1：论坛爬虫集成"""
        logger.info("\n📝 测试1：论坛爬虫集成")
        
        settings = load_forum_settings()
        credentials = settings.get('credentials', {})
        forum_cfg = settings.get('forum', {})
        
        integration = TTSForumCrawlerIntegration(
            username=credentials.get('username', ''),
            password=credentials.get('password', ''),
            base_url=forum_cfg.get('base_url', 'https://tts.lrtcai.com'),
            forum_url=forum_cfg.get('target_url', 'https://tts.lrtcai.com/forum-2-1.html')
        )
        
        # 检查爬虫是否初始化
        self.assertIsNotNone(integration.crawler)
        logger.info("  ✅ 爬虫初始化成功")
        
        # 尝试获取新帖子
        new_posts = integration.get_new_posts()
        logger.info(f"  ✅ 获取到 {len(new_posts)} 个新帖子")
    
    def test_02_user_sync(self):
        """测试2：用户同步"""
        logger.info("\n👤 测试2：用户同步")
        
        user_sync = TTSForumUserSync()
        
        # 同步测试用户
        success, message = user_sync.sync_forum_user(
            forum_user_id='test_001',
            forum_username='test_user_001',
            email='test001@example.com'
        )
        
        self.assertTrue(success)
        logger.info(f"  ✅ 用户同步成功: {message}")
        
        # 获取用户配额
        quota = user_sync.get_user_voice_quota('forum_test_001')
        logger.info(f"  ✅ 用户音色配额: {quota}")
    
    def test_03_request_detection(self):
        """测试3：请求类型检测"""
        logger.info("\n🔍 测试3：请求类型检测")
        
        parser = TTSRequestParser()
        
        # 测试TTS请求
        tts_post = {
            'title': '【制作AI声音】测试',
            'content': '【文案】你好世界',
            'tags': ['【制作AI声音】']
        }
        
        result = parser.detect_request_type(tts_post)
        self.assertEqual(result['type'], 'tts')
        logger.info(f"  ✅ TTS请求检测成功 (置信度: {result['confidence']}%)")
        
        # 测试音色克隆请求
        clone_post = {
            'title': '【音色克隆】我的声音',
            'content': '【音色名称】张三的声音',
            'tags': ['【音色克隆】']
        }
        
        result = parser.detect_request_type(clone_post)
        self.assertEqual(result['type'], 'voice_clone')
        logger.info(f"  ✅ 音色克隆请求检测成功 (置信度: {result['confidence']}%)")
    
    def test_04_system_initialization(self):
        """测试4：系统初始化"""
        logger.info("\n⚙️ 测试4：系统初始化")
        
        manager = TTSForumIntegrationManager()
        
        # 检查所有模块是否初始化
        self.assertIsNotNone(manager.crawler_integration)
        self.assertIsNotNone(manager.monitor)
        self.assertIsNotNone(manager.processor)
        self.assertIsNotNone(manager.api_service)
        self.assertIsNotNone(manager.uploader)
        self.assertIsNotNone(manager.user_sync)
        
        logger.info("  ✅ 所有模块初始化成功")
    
    def test_05_system_lifecycle(self):
        """测试5：系统生命周期"""
        logger.info("\n🔄 测试5：系统生命周期")
        
        manager = TTSForumIntegrationManager()
        
        # 启动系统
        logger.info("  启动系统...")
        manager.start()
        self.assertTrue(manager.is_running)
        logger.info("  ✅ 系统已启动")
        
        # 运行一段时间
        logger.info("  运行系统 5 秒...")
        time.sleep(5)
        logger.info("  ✅ 系统运行正常")
        
        # 停止系统
        logger.info("  停止系统...")
        manager.stop()
        self.assertFalse(manager.is_running)
        logger.info("  ✅ 系统已停止")
    
    def test_06_performance(self):
        """测试6：性能测试"""
        logger.info("\n⚡ 测试6：性能测试")
        
        parser = TTSRequestParser()
        
        # 测试请求解析性能
        logger.info("  测试请求解析性能...")
        
        post_data = {
            'title': '【制作AI声音】测试',
            'content': '【文案】你好世界',
            'tags': ['【制作AI声音】']
        }
        
        start_time = time.time()
        for i in range(100):
            parser.detect_request_type(post_data)
        elapsed_time = time.time() - start_time
        
        avg_time = elapsed_time / 100 * 1000  # 转换为毫秒
        logger.info(f"  ✅ 100次请求解析耗时: {elapsed_time:.2f}秒")
        logger.info(f"  ✅ 平均耗时: {avg_time:.2f}毫秒")
        
        # 性能检查
        self.assertLess(avg_time, 10)  # 平均耗时应小于10毫秒
    
    def test_07_error_handling(self):
        """测试7：错误处理"""
        logger.info("\n🛡️ 测试7：错误处理")
        
        # 测试无效的用户ID
        user_sync = TTSForumUserSync()
        
        try:
            quota = user_sync.get_user_voice_quota('invalid_user_id')
            logger.info(f"  ✅ 无效用户ID处理成功: {quota}")
        except Exception as e:
            logger.info(f"  ✅ 异常捕获成功: {str(e)}")
    
    def test_08_concurrent_processing(self):
        """测试8：并发处理"""
        logger.info("\n🔀 测试8：并发处理")
        
        import threading
        
        parser = TTSRequestParser()
        results = []
        
        def process_request():
            post_data = {
                'title': '【制作AI声音】测试',
                'content': '【文案】你好世界',
                'tags': ['【制作AI声音】']
            }
            result = parser.detect_request_type(post_data)
            results.append(result)
        
        # 创建10个线程
        threads = []
        for i in range(10):
            thread = threading.Thread(target=process_request)
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        logger.info(f"  ✅ 并发处理完成: {len(results)} 个请求")
        self.assertEqual(len(results), 10)


def run_integration_tests():
    """运行集成测试"""
    logger.info("=" * 80)
    logger.info("🧪 IndexTTS2 论坛集成系统 - 集成测试")
    logger.info("=" * 80)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestTTSIntegration)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出总结
    logger.info("\n" + "=" * 80)
    logger.info("📊 集成测试总结")
    logger.info("=" * 80)
    logger.info(f"运行测试数: {result.testsRun}")
    logger.info(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    logger.info(f"失败: {len(result.failures)}")
    logger.info(f"错误: {len(result.errors)}")
    logger.info("=" * 80)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
