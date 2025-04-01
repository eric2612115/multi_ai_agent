#!/usr/bin/env python
"""
圖片搜尋範例

這個腳本展示如何使用 ImageSearchService 來搜尋和下載網路圖片，並使用 Gemini 進行分析
"""
import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.multi_ai_agent.services.image_search import ImageSearchService
from src.multi_ai_agent.clients import GeminiClient

def main():
    """主函數"""
    # 載入環境變數
    load_dotenv()
    
    # 創建下載目錄
    download_dir = "downloaded_images"
    os.makedirs(download_dir, exist_ok=True)
    
    # 初始化服務
    search_service = ImageSearchService(
        download_folder=download_dir,
        search_api_key=os.environ.get("SERP_API_KEY"),  # 可選
    )
    
    # 初始化 Gemini 客戶端用於圖片分析
    gemini = GeminiClient()
    
    # 取得命令列參數
    import argparse
    parser = argparse.ArgumentParser(description="圖片搜尋和分析範例")
    parser.add_argument("--query", type=str, default="台北101夜景", help="搜尋關鍵詞")
    parser.add_argument("--count", type=int, default=2, help="下載圖片數量")
    parser.add_argument("--analyze", action="store_true", help="使用 Gemini 分析圖片")
    parser.add_argument("--url", type=str, help="直接從特定 URL 下載圖片")
    args = parser.parse_args()
    
    print(f"搜尋圖片：{args.query}")
    print(f"請求數量：{args.count}")
    print(f"是否分析：{'是' if args.analyze else '否'}")
    print("-" * 40)
    
    downloaded_images = []
    
    # 處理特定 URL 下載
    if args.url:
        print(f"從 URL 下載圖片：{args.url}")
        filename = f"direct_download_{args.query.replace(' ', '_')}"
        image_path = search_service.download_image_from_url(args.url, filename)
        
        if image_path:
            print(f"✓ 成功下載圖片至：{image_path}")
            downloaded_images.append(image_path)
        else:
            print("✗ 下載失敗")
    else:
        # 搜尋並下載圖片
        print("搜尋並下載圖片中...")
        image_paths = search_service.search_and_download_image(
            query=args.query,
            max_results=args.count,
            safe_search=True
        )
        
        if image_paths:
            print(f"✓ 成功下載 {len(image_paths)} 張圖片：")
            for i, path in enumerate(image_paths):
                print(f"  {i+1}. {path}")
            downloaded_images = image_paths
        else:
            print("✗ 沒有找到或下載圖片")
    
    # 分析下載的圖片
    if args.analyze and downloaded_images:
        print("\n使用 Gemini 分析圖片...")
        
        # 暫時切換到支援圖片的模型
        original_model = gemini.model
        gemini.set_model("gemini-2.0-pro-vision")
        
        for i, image_path in enumerate(downloaded_images):
            print(f"\n分析圖片 {i+1}: {image_path}")
            
            try:
                # 分析圖片
                analysis = gemini.client.models.generate_content(
                    model=gemini.model,
                    contents=[
                        f"分析這張關於「{args.query}」的圖片，說明其中包含的主要元素、風格特點和整體內容。如果有文字，請閱讀並轉錄。",
                        gemini.client.genai.types.Part.from_uri(
                            file_uri=f"file://{image_path}", 
                            mime_type="image/jpeg"
                        )
                    ]
                ).text
                
                print("\n分析結果：")
                print("-" * 40)
                print(analysis)
                print("-" * 40)
            except Exception as e:
                print(f"✗ 分析出錯：{str(e)}")
        
        # 恢復原來的模型
        gemini.set_model(original_model)
    
    print("\n完成！")
    
    # 返回下載的圖片路徑列表，以便其他腳本使用
    return downloaded_images


# 直接執行此腳本
if __name__ == "__main__":
    main()
