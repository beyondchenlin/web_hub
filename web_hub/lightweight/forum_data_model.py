#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
论坛数据模型 - 统一的数据结构定义

这个模块提供了论坛数据的标准化数据模型，确保整个系统中数据格式的一致性。
"""

from typing import List, Dict, Optional, Any
import json


class CoverTitle:
    """封面标题的数据模型"""
    
    def __init__(self, text: str, position: str):
        self.text = text.strip() if text else ""
        self.position = position  # 'up', 'middle', 'down'
    
    def to_dict(self) -> Dict[str, str]:
        """转换为字典格式"""
        return {
            'text': self.text,
            'position': self.position
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'CoverTitle':
        """从字典创建实例"""
        return cls(
            text=data.get('text', ''),
            position=data.get('position', '')
        )
    
    def __bool__(self) -> bool:
        """判断是否有有效内容"""
        return bool(self.text)


class ForumPostInfo:
    """论坛帖子信息的数据模型"""
    
    def __init__(self):
        self.post_id = ""
        self.title = ""
        self.author_id = ""
        self.original_filename = ""
        self.post_url = ""
        self.source = "forum"
        self.content = ""
        self.core_text = ""
        self.cover_titles: List[CoverTitle] = []
        
        # 保留旧字段用于向后兼容
        self.cover_title_up = ""
        self.cover_title_middle = ""
        self.cover_title_down = ""
    
    def add_cover_title(self, text: str, position: str):
        """添加封面标题"""
        if text and text.strip():
            self.cover_titles.append(CoverTitle(text, position))
            
            # 同时更新旧字段以保持兼容性
            if position == 'up':
                self.cover_title_up = text.strip()
            elif position == 'middle':
                self.cover_title_middle = text.strip()
            elif position == 'down':
                self.cover_title_down = text.strip()
    
    def get_cover_titles_by_position(self) -> Dict[str, str]:
        """按位置获取封面标题的字典"""
        result = {}
        for title in self.cover_titles:
            if title.text:
                result[title.position] = title.text
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（包含新旧格式以保持兼容性）"""
        return {
            # 基础信息
            'post_id': self.post_id,
            'title': self.title,
            'author_id': self.author_id,
            'original_filename': self.original_filename,
            'post_url': self.post_url,
            'source': self.source,
            'content': self.content,
            'core_text': self.core_text,
            
            # 新格式：语义化的封面标题
            'cover_titles': [title.to_dict() for title in self.cover_titles if title],
            
            # 旧格式：保持向后兼容
            'cover_title_up': self.cover_title_up,
            'cover_title_middle': self.cover_title_middle,
            'cover_title_down': self.cover_title_down
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ForumPostInfo':
        """从字典创建实例（支持新旧格式）"""
        instance = cls()
        
        # 基础信息
        instance.post_id = data.get('post_id', '')
        instance.title = data.get('title', '')
        instance.author_id = data.get('author_id', '')
        instance.original_filename = data.get('original_filename', '')
        instance.post_url = data.get('post_url', '')
        instance.source = data.get('source', 'forum')
        instance.content = data.get('content', '')
        instance.core_text = data.get('core_text', '')
        
        # 优先使用新格式
        if 'cover_titles' in data and isinstance(data['cover_titles'], list):
            for title_data in data['cover_titles']:
                if isinstance(title_data, dict) and title_data.get('text'):
                    instance.cover_titles.append(CoverTitle.from_dict(title_data))
                    # 同时更新旧字段
                    position = title_data.get('position', '')
                    if position == 'up':
                        instance.cover_title_up = title_data['text']
                    elif position == 'middle':
                        instance.cover_title_middle = title_data['text']
                    elif position == 'down':
                        instance.cover_title_down = title_data['text']
        else:
            # 从旧格式转换
            for position in ['up', 'middle', 'down']:
                key = f'cover_title_{position}'
                if key in data and data[key]:
                    instance.add_cover_title(data[key], position)
        
        return instance
    
    def save_to_file(self, filepath: str):
        """保存到JSON文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'ForumPostInfo':
        """从JSON文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


def normalize_forum_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    归一化论坛信息数据
    
    将旧格式的数据转换为新格式，同时保持向后兼容性。
    这是一个轻量级的转换函数，不创建完整的对象。
    """
    # 如果已经包含新格式，直接返回
    if 'cover_titles' in data and isinstance(data['cover_titles'], list):
        return data
    
    # 构建新格式的封面标题
    cover_titles = []
    for position in ['up', 'middle', 'down']:
        key = f'cover_title_{position}'
        if key in data and data[key] and data[key].strip():
            cover_titles.append({
                'text': data[key].strip(),
                'position': position
            })
    
    # 添加新格式字段
    data['cover_titles'] = cover_titles
    
    return data


def extract_cover_titles_for_display(forum_info: Dict[str, Any]) -> List[str]:
    """
    从论坛信息中提取封面标题用于显示
    
    返回一个字符串列表，每个字符串是一行标题文本
    """
    # 优先使用新格式
    if 'cover_titles' in forum_info and isinstance(forum_info['cover_titles'], list):
        titles = []
        for title_data in forum_info['cover_titles']:
            if isinstance(title_data, dict) and title_data.get('text'):
                titles.append(title_data['text'])
        return titles
    
    # 回退到旧格式
    titles = []
    for position in ['up', 'middle', 'down']:
        key = f'cover_title_{position}'
        if key in forum_info and forum_info[key] and forum_info[key].strip():
            titles.append(forum_info[key].strip())
    
    return titles


def extract_semantic_positions(forum_info: Dict[str, Any]) -> List[str]:
    """
    从论坛信息中提取语义位置信息
    
    返回位置列表，如 ['up', 'down'] 或 ['up', 'middle', 'down']
    """
    # 优先使用新格式
    if 'cover_titles' in forum_info and isinstance(forum_info['cover_titles'], list):
        positions = []
        for title_data in forum_info['cover_titles']:
            if isinstance(title_data, dict) and title_data.get('text') and title_data.get('position'):
                positions.append(title_data['position'])
        return positions
    
    # 回退到旧格式
    positions = []
    for position in ['up', 'middle', 'down']:
        key = f'cover_title_{position}'
        if key in forum_info and forum_info[key] and forum_info[key].strip():
            positions.append(position)
    
    return positions