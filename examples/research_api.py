#!/usr/bin/env python
"""
研究 API 服務 (Research API Service)

這個腳本提供 REST API，用於執行深度研究任務和管理研究報告。
"""
import os
import json
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 使用 FastAPI 建立 API 服務
try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Path, Body
    from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    print("警告: FastAPI 未安裝，請安裝以使用 API 服務: pip install fastapi uvicorn")
    FASTAPI_AVAILABLE = False

# 載入環境變數
load_dotenv()

# 如果 FastAPI 可用，建立 API 應用
if FASTAPI_AVAILABLE:
    from src.multi_ai_agent.agents import DeepResearchAgent
    
    app = FastAPI(
        title="多 AI 代理 研究 API",
        description="提供深度研究服務和研究報告管理的 REST API",
        version="1.0.0"
    )
    
    # 啟用 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 研究任務狀態存儲
    research_tasks = {}
    
    # 模型定義
    class ResearchRequest(BaseModel):
        topic: str = Field(..., description="研究主題")
        depth: int = Field(3, ge=1, le=5, description="研究深度 (1-5)")
        include_images: bool = Field(True, description="是否包含圖片")
        use_advanced_models: bool = Field(False, description="是否使用進階模型")
        max_queries: int = Field(10, ge=1, le=20, description="最大搜尋次數")
        report_format: str = Field("markdown", description="報告格式 (html 或 markdown)")
        use_mongodb: bool = Field(False, description="是否使用 MongoDB 儲存")
    
    class ResearchResponse(BaseModel):
        task_id: str = Field(..., description="任務 ID")
        topic: str = Field(..., description="研究主題")
        status: str = Field(..., description="任務狀態")
        created_at: str = Field(..., description="任務建立時間")
    
    class ResearchResult(BaseModel):
        task_id: str = Field(..., description="任務 ID")
        topic: str = Field(..., description="研究主題")
        status: str = Field(..., description="任務狀態")
        created_at: str = Field(..., description="任務建立時間")
        completed_at: Optional[str] = Field(None, description="任務完成時間")
        report_path: Optional[str] = Field(None, description="報告文件路徑")
        report_id: Optional[str] = Field(None, description="報告 ID (MongoDB)")
        duration: Optional[str] = Field(None, description="研究耗時")
        error: Optional[str] = Field(None, description="錯誤訊息")
    
    
    # 根路徑
    @app.get("/", response_class=HTMLResponse)
    async def root():
        return """
        <html>
            <head>
                <title>多 AI 代理 研究 API</title>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
                    h1 { color: #2c3e50; }
                    a { color: #3498db; }
                    code { background-color: #f8f9fa; padding: 2px 4px; border-radius: 4px; }
                </style>
            </head>
            <body>
                <h1>多 AI 代理 研究 API</h1>
                <p>此 API 提供深度研究服務和研究報告管理功能。</p>
                <h2>API 端點</h2>
                <ul>
                    <li><code>POST /research</code> - 開始新的研究任務</li>
                    <li><code>GET /research/tasks</code> - 列出所有研究任務</li>
                    <li><code>GET /research/tasks/{task_id}</code> - 獲取特定研究任務狀態</li>
                    <li><code>GET /reports</code> - 列出所有研究報告</li>
                    <li><code>GET /reports/{report_id}</code> - 獲取特定研究報告</li>
                </ul>
                <p>詳細 API 文檔: <a href="/docs">/docs</a></p>
            </body>
        </html>
        """
    
    # 開始新的研究
    @app.post("/research", response_model=ResearchResponse)
    async def start_research(request: ResearchRequest, background_tasks: BackgroundTasks):
        # 生成任務 ID
        task_id = f"task_{int(time.time())}_{os.urandom(4).hex()}"
        
        # 建立任務狀態
        task_status = {
            "task_id": task_id,
            "topic": request.topic,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "request": request.dict()
        }
        research_tasks[task_id] = task_status
        
        # 在背景執行研究
        background_tasks.add_task(
            execute_research_task,
            task_id,
            request.dict()
        )
        
        return task_status
    
    # 背景執行研究任務
    async def execute_research_task(task_id: str, request: Dict[str, Any]):
        # 更新任務狀態
        research_tasks[task_id]["status"] = "running"
        
        try:
            # 建立輸出目錄
            output_dir = os.path.join("research_results", task_id)
            os.makedirs(output_dir, exist_ok=True)
            
            # 初始化代理
            agent = DeepResearchAgent(
                output_dir=output_dir,
                report_format=request["report_format"],
                storage_type="mongodb" if request["use_mongodb"] else "filesystem",
                mongodb_uri=os.environ.get("MONGODB_URI")
            )
            
            # 執行研究
            start_time = datetime.now()
            result = agent.research(
                topic=request["topic"],
                depth=request["depth"],
                include_images=request["include_images"],
                use_advanced_models=request["use_advanced_models"],
                max_queries=request["max_queries"]
            )
            end_time = datetime.now()
            
            # 更新任務狀態
            research_tasks[task_id].update({
                "status": "completed",
                "completed_at": end_time.isoformat(),
                "result": result,
                "duration": str(end_time - start_time)
            })
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            
            # 更新任務狀態
            research_tasks[task_id].update({
                "status": "failed",
                "completed_at": datetime.now().isoformat(),
                "error": str(e),
                "error_trace": error_trace
            })
    
    # 列出所有研究任務
    @app.get("/research/tasks", response_model=List[ResearchResult])
    async def list_tasks(
        limit: int = Query(10, description="最大回傳數量"),
        status: Optional[str] = Query(None, description="過濾任務狀態")
    ):
        # 獲取任務列表
        tasks = list(research_tasks.values())
        
        # 過濾狀態
        if status:
            tasks = [t for t in tasks if t["status"] == status]
        
        # 排序並限制數量
        tasks.sort(key=lambda x: x["created_at"], reverse=True)
        tasks = tasks[:limit]
        
        # 轉換為回應格式
        results = []
        for task in tasks:
            result = {
                "task_id": task["task_id"],
                "topic": task["topic"],
                "status": task["status"],
                "created_at": task["created_at"],
                "completed_at": task.get("completed_at"),
                "duration": task.get("duration")
            }
            
            # 添加報告路徑或錯誤（如果有）
            if "result" in task:
                result["report_path"] = task["result"].get("report_path")
                result["report_id"] = task["result"].get("storage_id")
            
            if "error" in task:
                result["error"] = task["error"]
                
            results.append(result)
            
        return results
    
    # 獲取特定研究任務
    @app.get("/research/tasks/{task_id}", response_model=ResearchResult)
    async def get_task(task_id: str = Path(..., description="任務 ID")):
        if task_id not in research_tasks:
            raise HTTPException(status_code=404, detail=f"找不到任務: {task_id}")
        
        task = research_tasks[task_id]
        
        # 轉換為回應格式
        result = {
            "task_id": task["task_id"],
            "topic": task["topic"],
            "status": task["status"],
            "created_at": task["created_at"],
            "completed_at": task.get("completed_at"),
            "duration": task.get("duration")
        }
        
        # 添加報告路徑或錯誤（如果有）
        if "result" in task:
            result["report_path"] = task["result"].get("report_path")
            result["report_id"] = task["result"].get("storage_id")
        
        if "error" in task:
            result["error"] = task["error"]
            
        return result
    
    # 列出所有研究報告
    @app.get("/reports")
    async def list_reports(
        limit: int = Query(10, description="最大回傳數量"),
        topic: Optional[str] = Query(None, description="主題過濾條件"),
        use_mongodb: bool = Query(False, description="是否使用 MongoDB")
    ):
        # 初始化代理
        agent = DeepResearchAgent(
            storage_type="mongodb" if use_mongodb else "filesystem",
            mongodb_uri=os.environ.get("MONGODB_URI")
        )
        
        # 列出報告
        reports = agent.list_reports(limit=limit, topic_filter=topic)
        return {"reports": reports}
    
    # 獲取特定研究報告
    @app.get("/reports/{report_id}")
    async def get_report(
        report_id: str = Path(..., description="報告 ID 或路徑"),
        use_mongodb: bool = Query(False, description="是否使用 MongoDB"),
        format: str = Query("json", description="回應格式 (json, html, markdown, file)")
    ):
        # 初始化代理
        agent = DeepResearchAgent(
            storage_type="mongodb" if use_mongodb else "filesystem",
            mongodb_uri=os.environ.get("MONGODB_URI")
        )
        
        # 獲取報告
        report = agent.get_report(report_id)
        
        if not report:
            raise HTTPException(status_code=404, detail=f"找不到報告: {report_id}")
        
        content = report.get("content", "")
        metadata = report.get("metadata", {})
        
        # 根據請求的格式回應
        if format == "json":
            return {"content": content, "metadata": metadata}
        
        elif format == "html" and metadata.get("format") == "html":
            return HTMLResponse(content=content)
        
        elif format == "markdown" and metadata.get("format") == "markdown":
            return JSONResponse(content={"content": content, "format": "markdown"})
        
        elif format == "file":
            # 如果報告本來就是文件，直接返回
            if "file_path" in metadata and os.path.exists(metadata["file_path"]):
                return FileResponse(
                    path=metadata["file_path"],
                    filename=os.path.basename(metadata["file_path"]),
                    media_type="text/html" if metadata.get("format") == "html" else "text/markdown"
                )
            
            # 否則創建臨時文件
            ext = ".html" if metadata.get("format") == "html" else ".md"
            temp_file = f"temp_report_{report_id}{ext}"
            
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)
            
            return FileResponse(
                path=temp_file,
                filename=f"report_{metadata.get('topic', 'unknown')}{ext}",
                media_type="text/html" if metadata.get("format") == "html" else "text/markdown"
            )
        
        else:
            return {"content": content, "metadata": metadata}
    
    # 如果此文件被直接執行，啟動 API 服務
    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
else:
    # 如果 FastAPI 不可用，提供簡單的錯誤訊息
    if __name__ == "__main__":
        print("錯誤: 無法啟動 API 服務，請安裝必要的依賴: pip install fastapi uvicorn")
