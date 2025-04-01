#!/usr/bin/env python
"""
研究應用程式 (Research App)

這個腳本提供命令行接口，用於執行深度研究任務和管理研究報告。
"""
import os
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

import os
import sys

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.multi_ai_agent.agents import DeepResearchAgent

def main():
    """主函數，處理命令行參數並執行相應操作"""
    # 加載環境變數
    load_dotenv()
    
    # 創建參數解析器
    parser = argparse.ArgumentParser(description="多 AI 代理深度研究應用程式")
    
    # 創建子命令
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 研究命令
    research_parser = subparsers.add_parser("research", help="執行深度研究")
    research_parser.add_argument("--topic", "-t", type=str, required=True, help="研究主題")
    research_parser.add_argument("--depth", "-d", type=int, default=3, choices=range(1, 6), help="研究深度 (1-5)")
    research_parser.add_argument("--no-images", action="store_true", help="不包含圖片")
    research_parser.add_argument("--advanced", "-a", action="store_true", help="使用進階模型")
    research_parser.add_argument("--max-queries", "-q", type=int, default=10, help="最大搜尋次數")
    research_parser.add_argument("--output-dir", "-o", type=str, default="research_results", help="輸出目錄")
    research_parser.add_argument("--format", "-f", type=str, choices=["html", "markdown"], default="markdown", help="報告輸出格式")
    research_parser.add_argument("--use-mongodb", action="store_true", help="使用 MongoDB 儲存報告")
    research_parser.add_argument("--mongodb-uri", type=str, help="MongoDB 連接字串")
    research_parser.add_argument("--mongodb-db", type=str, default="research_db", help="MongoDB 資料庫名稱")
    research_parser.add_argument("--mongodb-collection", type=str, default="research_reports", help="MongoDB 集合名稱")
    research_parser.add_argument("--debug-mongodb", action="store_true", help="顯示 MongoDB 連接詳細資訊")
    
    # 列出報告命令
    list_parser = subparsers.add_parser("list", help="列出研究報告")
    list_parser.add_argument("--limit", "-l", type=int, default=10, help="最大回傳數量")
    list_parser.add_argument("--topic", "-t", type=str, help="主題過濾條件")
    list_parser.add_argument("--output-dir", "-o", type=str, default="research_results", help="輸出目錄")
    list_parser.add_argument("--use-mongodb", action="store_true", help="使用 MongoDB 列出報告")
    list_parser.add_argument("--mongodb-uri", type=str, help="MongoDB 連接字串")
    list_parser.add_argument("--mongodb-db", type=str, default="research_db", help="MongoDB 資料庫名稱")
    list_parser.add_argument("--mongodb-collection", type=str, default="research_reports", help="MongoDB 集合名稱")
    list_parser.add_argument("--debug-mongodb", action="store_true", help="顯示 MongoDB 連接詳細資訊")
    
    # 獲取報告命令
    get_parser = subparsers.add_parser("get", help="獲取研究報告")
    get_parser.add_argument("report_id", type=str, help="報告 ID 或路徑")
    get_parser.add_argument("--output-dir", "-o", type=str, default="research_results", help="輸出目錄")
    get_parser.add_argument("--use-mongodb", action="store_true", help="從 MongoDB 獲取報告")
    get_parser.add_argument("--mongodb-uri", type=str, help="MongoDB 連接字串")
    get_parser.add_argument("--mongodb-db", type=str, default="research_db", help="MongoDB 資料庫名稱")
    get_parser.add_argument("--mongodb-collection", type=str, default="research_reports", help="MongoDB 集合名稱")
    get_parser.add_argument("--debug-mongodb", action="store_true", help="顯示 MongoDB 連接詳細資訊")
    get_parser.add_argument("--save-to", "-s", type=str, help="保存報告到文件")
    
    args = parser.parse_args()
    
    # 根據命令執行相應操作
    if args.command == "research":
        execute_research(args)
    elif args.command == "list":
        list_reports(args)
    elif args.command == "get":
        get_report(args)
    else:
        parser.print_help()


def execute_research(args):
    """執行研究"""
    print(f"執行深度研究: {args.topic}")
    
    # 如果啟用MongoDB詳細資訊
    if args.use_mongodb and args.debug_mongodb:
        print("MongoDB 連接詳細資訊:")
        print(f"  URI: {args.mongodb_uri or os.environ.get('MONGODB_URI') or '(未設置)'}")
        print(f"  資料庫: {args.mongodb_db}")
        print(f"  集合: {args.mongodb_collection}")
    
    # 初始化代理
    try:
        agent = DeepResearchAgent(
            output_dir=args.output_dir,
            report_format=args.format,
            storage_type="mongodb" if args.use_mongodb else "filesystem",
            mongodb_uri=args.mongodb_uri,
            mongodb_db=args.mongodb_db,
            mongodb_collection=args.mongodb_collection
        )
    except (ImportError, ConnectionError, ValueError) as e:
        print(f"\n初始化存儲管理器失敗: {e}")
        print("關閉應用程序")
        sys.exit(1)
    
    # 執行研究
    try:
        start_time = datetime.now()
        result = agent.research(
            topic=args.topic,
            depth=args.depth,
            include_images=not args.no_images,
            use_advanced_models=args.advanced,
            max_queries=args.max_queries
        )
        end_time = datetime.now()
        
        # 顯示結果
        print("\n" + "=" * 60)
        print(f"研究完成！")
        
        if "report_path" in result:
            print(f"報告已保存至: {result['report_path']}")
            
        if "storage_id" in result:
            print(f"報告 ID: {result['storage_id']}")
            
        print(f"研究耗時: {end_time - start_time}")
        print("=" * 60)
    except Exception as e:
        print(f"研究過程中發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()


def list_reports(args):
    """列出報告"""
    print(f"列出研究報告 (限制: {args.limit})")
    
    # 顯示MongoDB連接詳細資訊
    if args.use_mongodb and args.debug_mongodb:
        print("MongoDB 連接詳細資訊:")
        print(f"  URI: {args.mongodb_uri or os.environ.get('MONGODB_URI') or '(未設置)'}")
        print(f"  資料庫: {args.mongodb_db}")
        print(f"  集合: {args.mongodb_collection}")
    
    # 初始化代理
    try:
        agent = DeepResearchAgent(
            output_dir=args.output_dir,
            storage_type="mongodb" if args.use_mongodb else "filesystem",
            mongodb_uri=args.mongodb_uri,
            mongodb_db=args.mongodb_db,
            mongodb_collection=args.mongodb_collection
        )
    except (ImportError, ConnectionError, ValueError) as e:
        print(f"\n初始化存儲管理器失敗: {e}")
        print("關閉應用程序")
        sys.exit(1)
    
    # 列出報告
    reports = agent.list_reports(limit=args.limit, topic_filter=args.topic)
    
    # 顯示結果
    if reports:
        print(f"\n找到 {len(reports)} 個報告:")
        print("=" * 60)
        
        for i, report in enumerate(reports):
            topic = report.get("topic", "未知主題")
            format_type = report.get("format", "未知格式")
            created_at = report.get("created_at", "未知時間")
            
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            
            print(f"{i+1}. {topic}")
            print(f"   ID: {report.get('_id', report.get('report_id', '未知'))}")
            print(f"   格式: {format_type}")
            print(f"   建立時間: {created_at}")
            
            if "file_path" in report:
                print(f"   檔案路徑: {report['file_path']}")
                
            print(f"   摘要: {report.get('summary', '')[:100]}...")
            print()
    else:
        print("\n未找到報告")


def get_report(args):
    """獲取報告"""
    report_id = args.report_id
    print(f"獲取報告: {report_id}")
    
    # 顯示MongoDB連接詳細資訊
    if args.use_mongodb and args.debug_mongodb:
        print("MongoDB 連接詳細資訊:")
        print(f"  URI: {args.mongodb_uri or os.environ.get('MONGODB_URI') or '(未設置)'}")
        print(f"  資料庫: {args.mongodb_db}")
        print(f"  集合: {args.mongodb_collection}")
    
    # 初始化代理
    try:
        agent = DeepResearchAgent(
            output_dir=args.output_dir,
            storage_type="mongodb" if args.use_mongodb else "filesystem",
            mongodb_uri=args.mongodb_uri,
            mongodb_db=args.mongodb_db,
            mongodb_collection=args.mongodb_collection
        )
    except (ImportError, ConnectionError, ValueError) as e:
        print(f"\n初始化存儲管理器失敗: {e}")
        print("關閉應用程序")
        sys.exit(1)
    
    # 獲取報告
    report = agent.get_report(report_id)
    
    # 顯示結果
    if report:
        content = report.get("content", "")
        metadata = report.get("metadata", {})
        
        print("\n" + "=" * 60)
        print(f"報告主題: {metadata.get('topic', '未知主題')}")
        print(f"格式: {metadata.get('format', '未知格式')}")
        created_at = metadata.get("created_at", "未知時間")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at).strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        print(f"建立時間: {created_at}")
        print("=" * 60)
        
        # 如果指定了保存路徑，保存報告內容
        if args.save_to:
            with open(args.save_to, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\n報告已保存至: {args.save_to}")
        else:
            # 預覽報告內容（僅顯示前200個字符）
            print("\n內容預覽:")
            preview = content[:200] + "..." if len(content) > 200 else content
            print(preview)
            print("\n使用 --save-to 參數保存完整報告")
    else:
        print(f"\n找不到報告: {report_id}")


if __name__ == "__main__":
    main()
