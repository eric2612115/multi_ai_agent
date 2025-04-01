#!/usr/bin/env python
"""
報告生成器 (ReportGenerator)

這個模組提供不同格式的研究報告生成功能。
"""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

class BaseReportGenerator(ABC):
    """基礎報告生成器"""
    
    def __init__(self, output_dir: Path):
        """
        初始化報告生成器
        
        Args:
            output_dir: 輸出目錄
        """
        self.output_dir = output_dir
    
    @abstractmethod
    def generate_report(self, research_state: Dict[str, Any]) -> str:
        """
        生成報告
        
        Args:
            research_state: 研究狀態數據
            
        Returns:
            報告檔案路徑
        """
        pass


class MarkdownReportGenerator(BaseReportGenerator):
    """Markdown 報告生成器"""
    
    def generate_report(self, research_state: Dict[str, Any]) -> str:
        """
        生成 Markdown 格式的研究報告
        
        Args:
            research_state: 研究狀態數據
            
        Returns:
            報告檔案路徑
        """
        # 創建安全的檔名
        safe_topic = re.sub(r'[^\w\-_]', '_', research_state["topic"])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"report_{safe_topic}_{timestamp}.md"
        
        # 處理圖片部分
        images_md = ""
        if research_state.get("images", []):
            images_md = "## 視覺資料分析\n\n"
            for i, img in enumerate(research_state.get("images", [])):
                img_path = img.get("path", "")
                if os.path.exists(img_path):
                    rel_path = os.path.relpath(img_path, start=str(self.output_dir))
                    analysis = img.get("analysis", "無分析")
                    images_md += f"### 圖片 {i+1}\n\n![{research_state['topic']} 圖片 {i+1}]({rel_path})\n\n"
                    images_md += f"**分析**：{analysis}\n\n"
        else:
            images_md = "## 視覺資料分析\n\n無圖片資料\n\n"
            
        # 處理後續問題部分
        questions_md = "## 後續研究問題\n\n"
        for i, q in enumerate(research_state.get("follow_up_questions", ["無後續研究問題"])):
            questions_md += f"{i+1}. {q}\n"
            
        # 生成 Markdown 內容
        markdown = f"""# 研究報告: {research_state['topic']}

**研究深度**: {research_state.get('depth', 3)}/5  
**生成時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**研究耗時**: {research_state.get('duration', '未知')}  

## 研究總結

{research_state.get('summary', '無研究總結')}

## 詳細發現

{research_state.get('integrated_findings', '無詳細發現')}

{images_md}
{questions_md}

---

*此報告由多 AI 代理深度搜尋系統自動生成*

*免責聲明: 此報告基於網絡搜尋資訊，可能會有不完整或不準確的地方。請自行驗證重要資訊。*
"""
        
        # 寫入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        return str(report_path)


class HtmlReportGenerator(BaseReportGenerator):
    """HTML 報告生成器"""
    
    def generate_report(self, research_state: Dict[str, Any]) -> str:
        """
        生成 HTML 格式的研究報告
        
        Args:
            research_state: 研究狀態數據
            
        Returns:
            報告檔案路徑
        """
        # 創建安全的檔名
        safe_topic = re.sub(r'[^\w\-_]', '_', research_state["topic"])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"report_{safe_topic}_{timestamp}.html"
        
        # 圖片 HTML
        images_html = ""
        for i, img in enumerate(research_state.get("images", [])):
            img_path = img.get("path", "")
            if os.path.exists(img_path):
                rel_path = os.path.relpath(img_path, start=str(self.output_dir))
                analysis = img.get("analysis", "無分析")
                images_html += f"""
                <div class="image-container">
                    <img src="{rel_path}" alt="{research_state["topic"]} 圖片 {i+1}">
                    <div class="image-analysis">
                        <h4>圖片 {i+1} 分析</h4>
                        <p>{analysis}</p>
                    </div>
                </div>
                """
        
        # 生成報告 HTML
        html = f"""<!DOCTYPE html>
        <html lang="zh-TW">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>研究報告: {research_state["topic"]}</title>
            <style>
                body {{ font-family: 'Microsoft JhengHei', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; }}
                h1, h2, h3 {{ color: #2c3e50; }}
                .header {{ background-color: #f5f7fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                .findings {{ margin-bottom: 30px; }}
                .image-container {{ display: flex; margin: 20px 0; border: 1px solid #eee; padding: 15px; border-radius: 5px; }}
                .image-container img {{ max-width: 300px; max-height: 300px; object-fit: contain; margin-right: 20px; }}
                .image-analysis {{ flex: 1; }}
                .follow-up {{ background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin-top: 30px; }}
                .footer {{ margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; color: #7f8c8d; font-size: 0.9em; }}
                pre {{ white-space: pre-wrap; background: #f8f8f8; padding: 10px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>研究報告: {research_state["topic"]}</h1>
                <p>研究深度: {research_state.get("depth", 3)}/5</p>
                <p>生成時間: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                <p>研究耗時: {research_state.get("duration", "未知")}</p>
            </div>
            
            <div class="summary">
                <h2>研究總結</h2>
                <p>{research_state.get("summary", "無研究總結")}</p>
            </div>
            
            <div class="findings">
                <h2>詳細發現</h2>
                {research_state.get("integrated_findings", "無詳細發現")}
            </div>
            
            <div class="images">
                <h2>視覺資料分析</h2>
                {images_html if images_html else "<p>無圖片資料</p>"}
            </div>
            
            <div class="follow-up">
                <h2>後續研究問題</h2>
                <ol>
                    {"".join([f"<li>{q}</li>" for q in research_state.get("follow_up_questions", ["無後續研究問題"])])}
                </ol>
            </div>
            
            <div class="footer">
                <p>此報告由多 AI 代理深度搜尋系統自動生成</p>
                <p>免責聲明: 此報告基於網絡搜尋資訊，可能會有不完整或不準確的地方。請自行驗證重要資訊。</p>
            </div>
        </body>
        </html>
        """
        
        # 寫入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return str(report_path)


def get_report_generator(format_type: str, output_dir: Path) -> BaseReportGenerator:
    """
    獲取報告生成器實例
    
    Args:
        format_type: 報告格式類型 ('html' 或 'markdown')
        output_dir: 輸出目錄
        
    Returns:
        報告生成器實例
    """
    format_type = format_type.lower()
    if format_type == 'markdown' or format_type == 'md':
        return MarkdownReportGenerator(output_dir)
    else:
        return HtmlReportGenerator(output_dir)
