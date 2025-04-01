#!/usr/bin/env python
"""
獨立測試腳本 - MCP 客戶端功能
這個腳本測試通過 MCP 協議與 Multi-AI Agent 進行通信。
"""
import os
import sys
import json
import argparse
import asyncio
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def run_mcp_test(tool_name, arguments):
    """通過 MCP 協議運行特定工具"""
    print(f"測試 MCP 客戶端連接: {tool_name}")
    print(f"參數: {json.dumps(arguments, indent=2)}")
    print("-" * 40)
    
    # 建立 MCP 伺服器參數
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.multi_ai_agent.main"],
        env=None,  # 使用目前環境
    )
    
    try:
        # 連接到 MCP 伺服器
        print("連接到 Multi-AI Agent MCP 伺服器...")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # 初始化連接
                print("初始化連接...")
                await session.initialize()
                
                # 列出可用工具
                print("查詢可用工具...")
                tools = await session.list_tools()
                available_tools = [tool.name for tool in tools]
                
                if tool_name not in available_tools:
                    print(f"\n❌ 工具 '{tool_name}' 不存在!")
                    print(f"可用工具: {', '.join(available_tools)}")
                    return False
                
                # 呼叫指定工具
                print(f"呼叫工具: {tool_name}")
                result = await session.call_tool(tool_name, arguments=arguments)
                
                # 顯示結果
                print("\n工具呼叫結果:")
                if isinstance(result, dict):
                    print(json.dumps(result, indent=2))
                else:
                    print(result)
                
                print("\n✅ MCP 客戶端測試成功!")
                return True
                
    except Exception as e:
        print(f"\n❌ MCP 客戶端測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_resources():
    """測試讀取 MCP 資源"""
    print("測試 MCP 資源讀取")
    print("-" * 40)
    
    # 建立 MCP 伺服器參數
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.multi_ai_agent.main"],
        env=None,
    )
    
    try:
        # 連接到 MCP 伺服器
        print("連接到 Multi-AI Agent MCP 伺服器...")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # 初始化連接
                print("初始化連接...")
                await session.initialize()
                
                # 列出可用資源
                print("查詢可用資源...")
                resources = await session.list_resources()
                
                if not resources:
                    print("\n⚠️ 沒有可用資源!")
                    return False
                
                # 顯示可用資源
                print("\n可用資源:")
                for resource in resources:
                    print(f"- {resource.uri}: {resource.description}")
                
                # 讀取其中一個資源
                if resources:
                    resource_uri = resources[0].uri
                    print(f"\n讀取資源: {resource_uri}")
                    content, mime_type = await session.read_resource(resource_uri)
                    
                    print(f"MIME 類型: {mime_type}")
                    print("資源內容:")
                    print(content if isinstance(content, str) else json.dumps(content, indent=2))
                
                print("\n✅ MCP 資源測試成功!")
                return True
                
    except Exception as e:
        print(f"\n❌ MCP 資源測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="測試 MCP 客戶端功能")
    subparsers = parser.add_subparsers(dest="command", help="測試指令")
    
    # 資源測試
    resources_parser = subparsers.add_parser("resources", help="測試 MCP 資源功能")
    
    # 生成文字測試
    generate_parser = subparsers.add_parser("generate", help="測試文字生成功能")
    generate_parser.add_argument("--prompt", type=str, default="寫一首關於春天的短詩", help="提示詞")
    generate_parser.add_argument("--service", type=str, choices=["gemini", "claude"], help="AI 服務名稱")
    generate_parser.add_argument("--model", type=str, help="模型名稱")
    
    # 網頁爬取測試
    scrape_parser = subparsers.add_parser("scrape", help="測試網頁爬取功能")
    scrape_parser.add_argument("--url", type=str, default="https://modelcontextprotocol.io", help="爬取 URL")
    
    # 智能萃取測試
    extract_parser = subparsers.add_parser("extract", help="測試智能萃取功能")
    extract_parser.add_argument("--url", type=str, default="https://modelcontextprotocol.io", help="網站 URL")
    extract_parser.add_argument("--objective", type=str, default="MCP 協議的主要功能是什麼", help="萃取目標")
    extract_parser.add_argument("--advanced", action="store_true", help="使用進階模型")
    
    args = parser.parse_args()
    
    if args.command == "resources":
        await test_resources()
    elif args.command == "generate":
        arguments = {
            "prompt": args.prompt
        }
        if args.service:
            arguments["service"] = args.service
        if args.model:
            arguments["model"] = args.model
            
        await run_mcp_test("generate_text", arguments)
    elif args.command == "scrape":
        await run_mcp_test("scrape_url", {"url": args.url, "formats": ["markdown"]})
    elif args.command == "extract":
        await run_mcp_test("smart_extract_from_website", {
            "url": args.url,
            "objective": args.objective,
            "use_advanced_model": args.advanced
        })
    else:
        parser.print_help()

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
