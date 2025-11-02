"""
IndexTTS2 论坛集成系统 - 单元测试
测试各个模块的功能
"""

import os
import sys
import unittest
import logging
from pathlib import Path

# 确保 shared 可导入
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.forum_config import load_forum_settings

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入模块
from tts_forum_sync import TTSForumUserSync
from tts_forum_processor import TTSForumProcessor
from tts_request_parser import TTSRequestParser
from tts_permission_manager import PermissionManager
from tts_forum_crawler_integration import TTSForumCrawlerIntegration

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestTTSForumSync(unittest.TestCase):
    """测试用户同步模块"""
    
    def setUp(self):
        """测试前准备"""
        self.user_sync = TTSForumUserSync()
    
    def test_sync_forum_user(self):
        """测试同步论坛用户"""
        logger.info("\n测试1：同步论坛用户")
        
        success, message = self.user_sync.sync_forum_user(
            forum_user_id='123',
            forum_username='test_user',
            email='test@example.com'
        )
        
        logger.info(f"  结果: {message}")
        self.assertTrue(success)
    
    def test_get_user_voice_quota(self):
        """测试获取用户音色配额"""
        logger.info("\n测试2：获取用户音色配额")
        
        # 先同步用户
        self.user_sync.sync_forum_user('456', 'test_user2')
        
        quota = self.user_sync.get_user_voice_quota('forum_456')
        logger.info(f"  音色配额: {quota}")
        self.assertIsNotNone(quota)


class TestTTSRequestParser(unittest.TestCase):
    """测试请求解析模块"""
    
    def setUp(self):
        """测试前准备"""
        self.parser = TTSRequestParser()
    
    def test_detect_tts_request(self):
        """测试识别TTS请求"""
        logger.info("\n测试3：识别TTS请求")
        
        post_data = {
            'title': '【制作AI声音】测试',
            'content': '【文案】你好世界',
            'tags': ['【制作AI声音】']
        }
        
        result = self.parser.detect_request_type(post_data)
        logger.info(f"  识别类型: {result['type']}")
        logger.info(f"  置信度: {result['confidence']}%")
        logger.info(f"  原因: {result['reason']}")
        
        self.assertEqual(result['type'], 'tts')
        self.assertGreaterEqual(result['confidence'], 90)
    
    def test_detect_voice_clone_request(self):
        """测试识别音色克隆请求"""
        logger.info("\n测试4：识别音色克隆请求")
        
        post_data = {
            'title': '【音色克隆】我的声音',
            'content': '【音色名称】张三的声音',
            'tags': ['【音色克隆】']
        }
        
        result = self.parser.detect_request_type(post_data)
        logger.info(f"  识别类型: {result['type']}")
        logger.info(f"  置信度: {result['confidence']}%")
        logger.info(f"  原因: {result['reason']}")
        
        self.assertEqual(result['type'], 'voice_clone')
        self.assertGreaterEqual(result['confidence'], 90)


class TestPermissionManager(unittest.TestCase):
    """测试权限管理模块"""
    
    def setUp(self):
        """测试前准备"""
        self.permission_manager = PermissionManager()
    
    def test_check_voice_permission(self):
        """测试检查音色权限"""
        logger.info("\n测试5：检查音色权限")
        
        # 创建测试用户和音色
        user_sync = TTSForumUserSync()
        user_sync.sync_forum_user('789', 'test_user3')
        
        # 检查权限
        has_permission = self.permission_manager.check_voice_permission(
            user_id='forum_789',
            voice_name='default_voice'
        )
        
        logger.info(f"  权限检查结果: {has_permission}")
        self.assertIsNotNone(has_permission)


class TestTTSForumCrawlerIntegration(unittest.TestCase):
    """测试论坛爬虫集成模块"""
    
    def setUp(self):
        """测试前准备"""
        settings = load_forum_settings()
        credentials = settings.get('credentials', {})
        forum_cfg = settings.get('forum', {})

        self.integration = TTSForumCrawlerIntegration(
            username=credentials.get('username', ''),
            password=credentials.get('password', ''),
            base_url=forum_cfg.get('base_url', 'https://tts.lrtcai.com'),
            forum_url=forum_cfg.get('target_url', 'https://tts.lrtcai.com/forum-2-1.html')
        )
    
    def test_crawler_initialization(self):
        """测试爬虫初始化"""
        logger.info("\n测试6：爬虫初始化")
        
        self.assertIsNotNone(self.integration.crawler)
        logger.info("  ✅ 爬虫初始化成功")
    
    def test_get_new_posts(self):
        """测试获取新帖子"""
        logger.info("\n测试7：获取新帖子")
        
        new_posts = self.integration.get_new_posts()
        logger.info(f"  获取到 {len(new_posts)} 个新帖子")
        
        if new_posts:
            for post in new_posts[:3]:
                logger.info(f"    - {post['title']} (ID: {post['thread_id']})")


class TestTTSForumProcessor(unittest.TestCase):
    """测试论坛处理模块"""
    
    def setUp(self):
        """测试前准备"""
        self.processor = TTSForumProcessor()
    
    def test_process_forum_post(self):
        """测试处理论坛帖子"""
        logger.info("\n测试8：处理论坛帖子")
        
        post_data = {
            'thread_id': 'test_thread_001',
            'title': '【制作AI声音】测试',
            'content': '【文案】你好世界',
            'author': 'test_user',
            'author_id': '123',
            'tags': ['【制作AI声音】']
        }
        
        success, result = self.processor.process_forum_post(post_data)
        logger.info(f"  处理结果: {success}")
        logger.info(f"  结果信息: {result}")


def run_tests():
    """运行所有测试"""
    logger.info("=" * 80)
    logger.info("🧪 IndexTTS2 论坛集成系统 - 单元测试")
    logger.info("=" * 80)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestTTSForumSync))
    suite.addTests(loader.loadTestsFromTestCase(TestTTSRequestParser))
    suite.addTests(loader.loadTestsFromTestCase(TestPermissionManager))
    suite.addTests(loader.loadTestsFromTestCase(TestTTSForumCrawlerIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestTTSForumProcessor))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出总结
    logger.info("\n" + "=" * 80)
    logger.info("📊 测试总结")
    logger.info("=" * 80)
    logger.info(f"运行测试数: {result.testsRun}")
    logger.info(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    logger.info(f"失败: {len(result.failures)}")
    logger.info(f"错误: {len(result.errors)}")
    logger.info("=" * 80)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
