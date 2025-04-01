#!/usr/bin/env python
"""
多 AI 服務整合範例

這個腳本展示如何整合 Gemini、Claude 和 Firecrawl 服務，以執行複雜的資訊分析任務:
1. 使用 Firecrawl 抓取網頁內容
2. 使用 Gemini 分析內容並生成摘要
3. 使用 Claude 改寫摘要並提出進一步問題
"""
import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.multi_ai_agent.clients import FirecrawlClient, GeminiClient, ClaudeClient

class MultiAIAgent:
    """整合多個 AI 服務的代理"""
    
    def __init__(self):
        """初始化各 AI 服務客戶端"""
        try:
            self.firecrawl = FirecrawlClient()
            self.gemini = GeminiClient()
            self.claude = ClaudeClient()
            
            # 設置智能提取服務
            self.firecrawl.set_extraction_service(gemini_client=self.gemini)
            
            print("✅ 成功初始化所有 AI 服務客戶端")
        except Exception as e:
            print(f"❌ 初始化失敗: {str(e)}")
            raise
    
    def web_research(self, topic, max_urls=3):
        """網頁研究功能
        
        Args:
            topic: 研究主題
            max_urls: 最大處理的 URL 數量
            
        Returns:
            研究結果的摘要
        """
        print(f"\n== 網頁研究: {topic} ==")
        print("-" * 60)
        
        try:
            # 步驟 1: 使用 Gemini 生成合適的網站關鍵詞
            print("\n1. 生成搜尋關鍵詞...")
            search_prompt = f"針對「{topic}」這個主題，提供 3-5 個可以用於網頁搜尋的關鍵詞。只需回覆關鍵詞，不要有其他文字。每個關鍵詞用逗號分隔。"
            keywords = self.gemini.generate_text(search_prompt).strip()
            print(f"生成的關鍵詞: {keywords}")
            
            # 將關鍵詞轉換為列表
            keyword_list = [kw.strip() for kw in keywords.split(',')]
            
            # 步驟 2: 使用 Firecrawl 尋找相關網站
            print("\n2. 搜尋相關網站...")
            # 假設我們已經知道一個好的起始 URL
            base_url = "https://en.wikipedia.org/wiki/"
            found_urls = []
            
            for keyword in keyword_list[:3]:  # 限制只使用前 3 個關鍵詞
                search_term = keyword.replace(' ', '_')
                url = f"{base_url}{search_term}"
                print(f"嘗試 URL: {url}")
                
                try:
                    # 抓取網頁
                    content = self.firecrawl.scrape_url(url)
                    if content:
                        found_urls.append(url)
                        print(f"✓ 成功抓取: {url}")
                    else:
                        print(f"✗ 無法抓取: {url}")
                except Exception as e:
                    print(f"✗ 錯誤: {str(e)}")
            
            if not found_urls:
                return f"無法找到關於「{topic}」的相關網頁。"
            
            # 步驟 3: 使用 Firecrawl 和 Gemini 提取網頁資訊
            print("\n3. 從網頁提取資訊...")
            extracted_info = []
            
            for i, url in enumerate(found_urls[:max_urls]):
                print(f"\n處理 URL ({i+1}/{min(len(found_urls), max_urls)}): {url}")
                
                try:
                    # 使用智能提取
                    result = self.firecrawl.smart_extract(
                        url=url,
                        objective=f"提取關於「{topic}」的主要資訊",
                        use_advanced_model=False
                    )
                    
                    if result and 'data' in result:
                        extracted_info.append(result['data'])
                        print(f"✓ 成功提取資訊")
                    else:
                        # 基本提取
                        content = self.firecrawl.scrape_url(url)
                        
                        if content and 'markdown' in content:
                            # 使用 Gemini 分析內容
                            analysis_prompt = f"""
                            分析以下關於「{topic}」的網頁內容，並提取最重要的資訊，格式為 JSON。
                            
                            網頁內容:
                            {content['markdown'][:4000]}  # 限制內容長度
                            
                            回應應該是 JSON 格式，包含:
                            1. 主要資訊點
                            2. 重要日期或數字
                            3. 核心概念或定義
                            """
                            
                            analysis = self.gemini.generate_text(analysis_prompt)
                            
                            # 嘗試解析 JSON
                            try:
                                # 找出 JSON 部分
                                json_start = analysis.find('{')
                                json_end = analysis.rfind('}') + 1
                                
                                if json_start >= 0 and json_end > json_start:
                                    json_str = analysis[json_start:json_end]
                                    analysis_data = json.loads(json_str)
                                    extracted_info.append(analysis_data)
                                    print(f"✓ 成功使用 Gemini 分析內容")
                                else:
                                    print("✗ 無法找到 JSON 內容")
                            except json.JSONDecodeError:
                                print("✗ JSON 解析錯誤")
                        else:
                            print("✗ 無法抓取或分析內容")
                            
                except Exception as e:
                    print(f"✗ 提取錯誤: {str(e)}")
            
            if not extracted_info:
                return f"無法從找到的網頁中提取關於「{topic}」的有用資訊。"
            
            # 步驟 4: 使用 Gemini 整合資訊並生成摘要
            print("\n4. 整合資訊並生成摘要...")
            
            summary_prompt = f"""
            根據以下提取自網頁的資訊，生成一份關於「{topic}」的詳細摘要。
            
            提取的資訊:
            {json.dumps(extracted_info, ensure_ascii=False, indent=2)}
            
            摘要應該:
            1. 條理清晰地組織資訊
            2. 突出最重要的事實和概念
            3. 避免重複
            4. 使用正式的學術語言
            """
            
            gemini_summary = self.gemini.generate_text(summary_prompt)
            print("✓ Gemini 摘要已生成")
            
            # 步驟 5: 使用 Claude 改寫摘要並提出進一步問題
            print("\n5. 使用 Claude 改寫摘要並提出進一步問題...")
            
            rewrite_prompt = f"""
            以下是關於「{topic}」的資訊摘要:
            
            {gemini_summary}
            
            請執行以下任務:
            1. 改寫上面的摘要，使其更簡潔、更有條理且更容易理解，但保留所有重要資訊
            2. 列出 3-5 個關於「{topic}」值得進一步研究的問題
            
            格式要求:
            - 先提供改寫的摘要
            - 然後標題「進一步研究問題」，列出問題清單
            """
            
            claude_result = self.claude.generate_text(rewrite_prompt)
            print("✓ Claude 改寫和問題已生成")
            
            # 返回最終結果
            return claude_result
            
        except Exception as e:
            return f"研究過程中發生錯誤: {str(e)}"
    
    def analyze_topic(self, topic):
        """使用 Gemini 和 Claude 分析主題，比較兩者結果
        
        Args:
            topic: 要分析的主題
            
        Returns:
            兩個 AI 的分析結果與比較
        """
        print(f"\n== 主題分析比較: {topic} ==")
        print("-" * 60)
        
        try:
            # 步驟 1: 使用 Gemini 分析主題
            print("\n1. Gemini 分析...")
            gemini_prompt = f"""
            提供關於「{topic}」的詳細分析，包括:
            1. 主要概念和定義
            2. 歷史背景或發展
            3. 重要應用或案例
            4. 當前趨勢或爭議
            5. 未來展望
            
            請提供深入且結構化的分析，每個部分至少一段。
            """
            
            gemini_start_time = time.time()
            gemini_analysis = self.gemini.generate_text(gemini_prompt)
            gemini_time = time.time() - gemini_start_time
            print(f"完成! (耗時: {gemini_time:.2f} 秒)")
            
            # 步驟 2: 使用 Claude 分析主題
            print("\n2. Claude 分析...")
            claude_prompt = gemini_prompt  # 使用相同的提示詞以便比較
            
            claude_start_time = time.time()
            claude_analysis = self.claude.generate_text(claude_prompt)
            claude_time = time.time() - claude_start_time
            print(f"完成! (耗時: {claude_time:.2f} 秒)")
            
            # 步驟 3: 使用 Gemini 比較兩者分析
            print("\n3. 比較分析...")
            comparison_prompt = f"""
            以下是兩個 AI 對「{topic}」的分析。請比較它們在內容、深度、結構和風格上的異同。
            
            Gemini 分析 (耗時: {gemini_time:.2f} 秒):
            {gemini_analysis}
            
            Claude 分析 (耗時: {claude_time:.2f} 秒):
            {claude_analysis}
            
            請提供:
            1. 兩者共同點與差異點
            2. 各自優勢與不足
            3. 哪個分析對於不同目的更有用
            4. 整體評估
            """
            
            comparison = self.gemini.generate_text(comparison_prompt)
            
            # 組合結果
            result = f"""
            # 「{topic}」主題分析比較
            
            ## Gemini 分析 (耗時: {gemini_time:.2f} 秒)
            
            {gemini_analysis}
            
            ## Claude 分析 (耗時: {claude_time:.2f} 秒)
            
            {claude_analysis}
            
            ## 比較評估
            
            {comparison}
            """
            
            return result
            
        except Exception as e:
            return f"分析過程中發生錯誤: {str(e)}"
    
    def multimodal_analysis(self, image_path, prompt=None):
        """使用 Gemini 進行多模態分析
        
        Args:
            image_path: 圖片路徑
            prompt: 可選分析提示詞
            
        Returns:
            圖片分析結果
        """
        print(f"\n== 多模態分析: {image_path} ==")
        print("-" * 60)
        
        try:
            # 檢查圖片是否存在
            if not os.path.exists(image_path):
                return f"圖片路徑不存在: {image_path}"
            
            # 使用 Gemini Vision 模型
            self.gemini.set_model("gemini-2.0-pro-vision")
            
            # 預設提示詞
            if not prompt:
                prompt = "分析這張圖片，描述你所看到的內容並解釋其中的重要元素。如果有文字，請閱讀並摘要。"
            
            # 讀取圖片
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            # 使用原始 Gemini 客戶端進行多模態分析
            from google.genai import types
            
            print("\n執行圖片分析...")
            response = self.gemini.client.models.generate_content(
                model=self.gemini.model,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_data, mime_type="image/jpeg")
                ]
            )
            
            # 恢復原來的模型
            self.gemini.set_model("gemini-2.0-flash")
            
            print("✓ 分析完成")
            return response.text
            
        except Exception as e:
            # 恢復原來的模型
            self.gemini.set_model("gemini-2.0-flash")
            return f"圖片分析過程中發生錯誤: {str(e)}"

def main():
    """主函數"""
    load_dotenv()
    
    # 建立多 AI 代理
    agent = MultiAIAgent()
    
    # 選擇功能
    print("\n歡迎使用多 AI 代理系統!")
    print("\n可用功能:")
    print("1. 網頁研究 - 使用多個 AI 服務研究指定主題")
    print("2. 主題分析比較 - 比較 Gemini 和 Claude 的分析結果")
    print("3. 多模態分析 - 使用 Gemini 分析圖片")
    print("4. 退出")
    
    while True:
        choice = input("\n請選擇功能 (1-4): ")
        
        if choice == "1":
            topic = input("\n請輸入研究主題: ")
            max_urls = input("最多處理幾個網址 (預設 3): ")
            max_urls = int(max_urls) if max_urls.isdigit() else 3
            
            result = agent.web_research(topic, max_urls)
            print("\n====== 研究結果 ======")
            print(result)
            
            # 儲存結果到檔案
            filename = f"research_{topic.replace(' ', '_')}.md"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# {topic} 研究報告\n\n")
                f.write(result)
            print(f"\n研究結果已儲存至 {filename}")
            
        elif choice == "2":
            topic = input("\n請輸入要分析的主題: ")
            
            result = agent.analyze_topic(topic)
            print("\n====== 分析比較結果 ======")
            print(result)
            
            # 儲存結果到檔案
            filename = f"analysis_{topic.replace(' ', '_')}.md"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"\n分析結果已儲存至 {filename}")
            
        elif choice == "3":
            image_path = input("\n請輸入圖片路徑: ")
            prompt = input("請輸入分析提示詞 (可留空使用預設): ")
            
            result = agent.multimodal_analysis(image_path, prompt if prompt else None)
            print("\n====== 圖片分析結果 ======")
            print(result)
            
            # 儲存結果到檔案
            filename = f"image_analysis_{os.path.basename(image_path).split('.')[0]}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# 圖片分析: {os.path.basename(image_path)}\n\n")
                f.write(result)
            print(f"\n分析結果已儲存至 {filename}")
            
        elif choice == "4":
            print("\n感謝使用多 AI 代理系統，再見!")
            break
            
        else:
            print("\n請輸入有效的選項 (1-4)")

if __name__ == "__main__":
    main()
