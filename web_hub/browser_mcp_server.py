#!/usr/bin/env python3

import asyncio
import json
import sys
from typing import Any, Sequence
from mcp.server import Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
from mcp.server.models import InitializationOptions
import mcp.server.stdio
from playwright.async_api import async_playwright
import base64
import os

app = Server("browser-control")

# 全局浏览器实例
browser = None
page = None

@app.list_resources()
async def handle_list_resources() -> list[Resource]:
    """列出可用的资源"""
    return [
        Resource(
            uri="browser://current-page",
            name="Current Browser Page",
            description="Currently open browser page",
            mimeType="text/html",
        )
    ]

@app.read_resource()
async def handle_read_resource(uri: str) -> str:
    """读取资源内容"""
    if uri == "browser://current-page":
        if page:
            content = await page.content()
            return content
        else:
            return "No browser page is currently open"
    
    raise ValueError(f"Unknown resource: {uri}")

@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    """列出可用的工具"""
    return [
        Tool(
            name="open_browser",
            description="打开浏览器并导航到指定URL",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要访问的URL"
                    },
                    "headless": {
                        "type": "boolean",
                        "description": "是否以无头模式运行浏览器",
                        "default": False
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="take_screenshot",
            description="截取当前页面的屏幕截图",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "保存截图的路径(可选)",
                        "default": None
                    }
                }
            }
        ),
        Tool(
            name="get_page_source",
            description="获取当前页面的HTML源代码",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="click_element",
            description="点击页面上的元素",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS选择器或XPath"
                    }
                },
                "required": ["selector"]
            }
        ),
        Tool(
            name="refresh_page",
            description="刷新当前页面",
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "description": "是否强制刷新（忽略缓存）",
                        "default": False
                    }
                }
            }
        ),
        Tool(
            name="close_browser",
            description="关闭浏览器",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent | ImageContent | EmbeddedResource]:
    """处理工具调用"""
    global browser, page
    
    if name == "open_browser":
        url = arguments.get("url") if arguments else "about:blank"
        headless = arguments.get("headless", False) if arguments else False
        
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=headless)
            page = await browser.new_page()
            await page.goto(url)
            
            return [
                TextContent(
                    type="text",
                    text=f"浏览器已打开并导航到: {url}"
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"打开浏览器失败: {str(e)}"
                )
            ]
    
    elif name == "take_screenshot":
        if not page:
            return [
                TextContent(
                    type="text",
                    text="没有打开的浏览器页面"
                )
            ]
        
        try:
            path = arguments.get("path") if arguments else None
            if not path:
                path = "screenshot.png"
            
            await page.screenshot(path=path)
            
            # 读取截图并转换为base64
            with open(path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
            
            return [
                TextContent(
                    type="text",
                    text=f"截图已保存到: {path}"
                ),
                ImageContent(
                    type="image",
                    data=image_data,
                    mimeType="image/png"
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"截图失败: {str(e)}"
                )
            ]
    
    elif name == "get_page_source":
        if not page:
            return [
                TextContent(
                    type="text",
                    text="没有打开的浏览器页面"
                )
            ]
        
        try:
            content = await page.content()
            return [
                TextContent(
                    type="text",
                    text=f"页面源代码:\n{content}"
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"获取页面源代码失败: {str(e)}"
                )
            ]
    
    elif name == "click_element":
        if not page:
            return [
                TextContent(
                    type="text",
                    text="没有打开的浏览器页面"
                )
            ]
        
        selector = arguments.get("selector") if arguments else None
        if not selector:
            return [
                TextContent(
                    type="text",
                    text="需要提供选择器"
                )
            ]
        
        try:
            await page.click(selector)
            return [
                TextContent(
                    type="text",
                    text=f"已点击元素: {selector}"
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"点击元素失败: {str(e)}"
                )
            ]
    
    elif name == "refresh_page":
        if not page:
            return [
                TextContent(
                    type="text",
                    text="没有打开的浏览器页面"
                )
            ]
        
        try:
            force = arguments.get("force", False) if arguments else False
            if force:
                await page.reload()
            else:
                await page.reload()
            
            return [
                TextContent(
                    type="text",
                    text="页面已刷新"
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"刷新页面失败: {str(e)}"
                )
            ]
    
    elif name == "close_browser":
        try:
            if browser:
                await browser.close()
                browser = None
                page = None
            
            return [
                TextContent(
                    type="text",
                    text="浏览器已关闭"
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"关闭浏览器失败: {str(e)}"
                )
            ]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    # 运行MCP服务器
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="browser-control",
                server_version="1.0.0",
                capabilities=app.get_capabilities(),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())