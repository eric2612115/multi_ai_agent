# AI 知識森林系統：自我進化的智慧系統

## 項目概述

AI 知識森林是一個基於對話內容自動構建知識圖譜的系統，具有自我進化和自主反思能力。它不僅能夠從用戶與 AI 的對話中提取重要概念、實體和關係，將這些知識組織成一個結構化的圖譜，還能通過自主反思循環優化知識結構，實現知識的有機生長和自然演化。

系統的核心理念是模擬生物系統的有機生長與自我優化過程，透過能量分配、生命週期管理、抽象層級體系和自主反思能力，打造一個真正自我進化的知識生態系統。這種方法使 AI 系統能夠做到：

1. **自我調節**：通過能量分配機制，系統能夠自主決定資源分配優先級
2. **自我修復**：通過反思循環發現並修復知識結構中的缺陷和矛盾
3. **自我提升**：通過抽象生成和概念創新，提升知識圖譜的質量和深度
4. **自我平衡**：通過動態調整知識增長速度和連接密度，保持系統的可持續發展

此系統特別適合長期運行的 AI 助手和知識管理系統，通過持續積累並優化知識結構，隨時間推移提供越來越深入、準確和有洞察力的回應。

## 文檔索引

### 系統概述

- [系統概述](docs/overview/system_overview.md) - AI知识森林系统的功能和特性概览

### 技術文檔

- [系統架構與技術規格](docs/technical/system_architecture.md) - 详细的系统架构、数据模型和API规格

### 開發指南

- [開發者指南](docs/development/developer_guide.md) - 完整的开发环境设置、代码组织、最佳实践和扩展指南

### 功能特性文檔

- [能量系統](docs/features/energy_system.md) - 能量分配和管理
- [生命週期管理](docs/features/lifecycle_system.md) - 节点状态转换和知识淘汰
- [抽象層級管理](docs/features/abstraction_system.md) - 高层次抽象生成和管理
- [反思系統](docs/features/reflection_system.md) - 自主反思和优化
- [創新系統](docs/features/innovation_system.md) - 概念创新和合成
- [認知能力增強](docs/features/cognitive_capabilities.md) - 思考脈衝檢測、知識提煉與跨領域洞察
- [安全通訊系統](docs/features/secure_communication.md) - 系统通讯安全

### 組件文檔

- [反思任務處理器](docs/components/reflection_task_handlers.md) - 反思任务处理框架

### 項目計劃

- [下一步開發計劃](NEXT_STEPS.md) - 未来功能和改进计划

## 最新更新

- **系統文檔重組** (2025年4月)
  - 添加功能特性文檔，便於開發者了解單個功能
  - 创建開發者入門指南，提供清晰的閱讀路徑
  - 添加代碼組織和設計模式說明
  - 添加通用的服務基類和工具模塊

- **自我進化系統整合** (2023年4月)
  - 已完成能量系統、生命週期管理和抽象層級系統的實現
  - 整合反思系統，實現完整的OODA循環
  - 使用策略模式重構反思任務處理機制
  - 建立通用工具類和裝飾器，減少重複代碼
  - 優化錯誤處理，統一日誌格式

## 核心功能

### 已實現功能

- **自動知識提取**：從對話內容中識別和提取關鍵概念、實體和關係
- **智能知識放置**：基於相似度和語義關係，決定將新知識放在知識圖譜的哪個位置
- **知識圖譜管理**：支持節點和邊的創建、更新、刪除和查詢
- **實時通知**：通過 WebSocket 提供知識圖譜更新的實時通知
- **REST API**：提供完整的 REST API 接口以支持前端交互
- **MCP 工具**：支持 Model Context Protocol 擴展 AI 模型功能
- **多模型支持**：整合 Claude、Gemini、Firecrawl 等多種 AI 模型

### 自我進化功能

- **自主反思系統** ✅：基於 OODA 循環 (觀察-定向-決策-行動) 的自我評估和優化機制
- **知識生命週期管理** ✅：實現知識節點的狀態管理，包括萌芽、成長、成熟、演化、衰退、休眠和歸檔
- **多層次抽象機制** ✅：支持從具體到抽象的知識層次結構，促進知識的壓縮和泛化
- **知識能量恆定原則** ✅：模擬生物系統的能量恆定，智能分配計算資源
- **概念創新機制** ✅：通過類比、整合、轉化等方式合成新概念
- **上下文增強生成** ✅：實現完整的RAG系統，在生成回應時融合相關知識
- **結構化導航能力** ✅：支持知識圖譜的多維度遍歷和語義+結構化混合檢索
- **品質監控系統** ✅：通過靜態分析確保知識結構的一致性和可靠性
- **思考脈衝/聲納檢測** ✅：模擬人類思維中的關聯性探索，實時展示思考路徑
- **知識提煉與萃取** ✅：從具體知識中提煉高層次原則和規律，促進知識壓縮
- **跨領域洞察發現** ✅：自動發現不同領域間的共同模式和啟發性連接
- **互動式思考引導** ✅：允許用戶實時干預和引導AI的思考過程，共同探索想法

## 技術堆疊

- **FastAPI**：後端 Web 框架（使用最新的 lifespan 事件管理）
- **MongoDB**：數據存儲及向量搜索，支持知識圖譜的高效存取和查詢
- **Redis**：高性能緩存、訊息佇列和實時事件傳播
- **外部 AI 模型整合**：
  - **Claude** (Anthropic)：高級文本理解和生成
  - **Gemini** (Google)：多模態內容處理和知識提取
  - **Firecrawl**：網頁爬取和外部知識獲取
- **WebSocket**：提供實時通信和思考過程可視化
- **asyncio**：非阻塞異步處理框架，提高系統吞吐量
- **MCP（Model Context Protocol）**：擴展 AI 模型能力的工具集成
- **向量嵌入和相似度搜索**：支持語義理解和知識關聯建立
- **設計模式**：觀察者模式、策略模式、裝飾器模式等，確保代碼可維護性和可擴展性

## 系統架構

### 應用生命週期

應用的生命週期由 FastAPI 的 lifespan 事件管理器控制：

1. **啟動階段**
   - 初始化事件總線和任務隊列
   - 啟動知識森林任務處理器
   - 設置 WebSocket 通知
   - 註冊 MCP 工具
   - 初始化反思系統和能量管理器

2. **運行階段**
   - 處理 API 請求
   - 異步處理知識提取和圖譜更新
   - 提供實時通知
   - 執行定期反思循環
   - 管理知識節點生命週期

3. **關閉階段**
   - 停止知識森林任務處理器
   - 停止反思系統
   - 停止任務隊列
   - 釋放資源

### 核心檔案結構

```
src/
|-- api/                       # API 層
|   |-- rest/                  # REST API 端點
|   |-- websocket/             # WebSocket 支持
|   |-- mcp/                   # MCP 工具
|
|-- forest/                    # 知識森林核心
|   |-- extraction/            # 知識提取
|   |-- placement/             # 知識放置
|   |-- graph/                 # 圖譜管理
|   |-- reflection/            # 自主反思系統
|   |-- lifecycle/             # 生命週期管理
|   |-- abstraction/           # 抽象層級管理
|   |-- energy/                # 能量系統
|   |-- innovation/            # 創新機制
|   |-- balance/               # 自我平衡機制
|   |-- evaluation/            # 系統評估與優化
|   |-- acquisition/           # 主動知識獲取
|
|-- services/                  # 共享服務
|   |-- event_bus.py           # 事件總線
|   |-- task_queue.py          # 任務隊列
|
|-- common/                    # 共享工具和模式
|   |-- base_service.py        # 服務基類
|   |-- decorators.py          # 通用裝飾器
|   |-- factory.py             # 工廠模式
|   |-- strategy.py            # 策略模式
|   |-- observer.py            # 觀察者模式
|
|-- app.py                     # 主 FastAPI 應用
```

## 數據模型

主要數據模型包括：

1. **知識節點 (Node)**：表示概念、實體、關鍵詞等
2. **關係邊 (Edge)**：連接知識節點
3. **主題群組 (Topic Cluster)**：將相關節點組織成主題
4. **反思循環 (ReflectionCycle)**：記錄完整的反思過程
5. **知識缺口 (KnowledgeGap)**：表示知識結構中的問題

## API 接口

### REST 端點

- `POST /api/knowledge/extract` - 提取知識
- `GET /api/knowledge/graph` - 獲取知識圖譜
- `POST /api/knowledge/nodes` - 創建節點
- `PUT /api/knowledge/nodes/{node_id}` - 更新節點
- `DELETE /api/knowledge/nodes/{node_id}` - 刪除節點
- `POST /api/knowledge/edges` - 創建關係邊
- `DELETE /api/knowledge/edges/{edge_id}` - 刪除關係邊
- `POST /api/knowledge/search` - 搜索知識圖譜
- `POST /api/knowledge/distill` - 從知識節點提煉高層次原則
- `POST /api/knowledge/insights` - 發現跨領域知識關聯和洞察
- `POST /api/reflection/trigger` - 觸發反思循環
- `GET /api/reflection/cycles` - 獲取反思循環列表
- `GET /api/reflection/cycles/{cycle_id}` - 獲取特定反思循環詳情
- `GET /api/reflection/gaps` - 獲取識別的知識缺口

### WebSocket 端點

- `WebSocket /ws/knowledge/notifications` - 接收知識圖譜更新通知
- `WebSocket /ws/reflection/status` - 接收反思循環狀態更新
- `WebSocket /ws/thinking` - 互動式思考過程實時交互

## 設置與運行

### 環境設置

1. 克隆儲存庫:
   ```bash
   git clone <repository-url>
   cd multi_ai_agent
   ```

2. 使用Docker (推薦):
   ```bash
   docker-compose up -d
   ```
   這將啟動所有必要的服務，包括MongoDB和Redis。

3. 或者手動設置:

   a. 創建並激活虛擬環境:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # 在Windows上使用 .venv\Scripts\activate
   ```

   b. 安裝依賴:
   ```bash
   pip install -e .
   # 或使用 poetry
   pip install poetry
   poetry install
   ```

   c. 配置環境變量:
   ```bash
   cp .env.example .env
   # 編輯.env文件，設置必要的API密鑰和配置
   ```

   d. 初始化導入修復:
   ```bash
   python import_fix.py
   ```
   這將確保所有模塊導入路徑正確，避免循環依賴問題。

   e. 啟動服務:
   ```bash
   # 啟動主 FastAPI 服務器 (8000是默認端口)
   python -m src.app --port 8000
   
   # 啟動 MCP 服務器 (Model Context Protocol)
   python -m src.main
   ```

4. 訪問服務:
   - API文檔: http://localhost:8000/docs
   - 知識圖譜視覺化: http://localhost:8000/visualize
   - WebSocket聊天測試: http://localhost:8000/chat

### 測試工具

系統提供多種測試工具：

1. 基本功能測試:
   ```bash
   # 運行交互式客戶端進行功能測試
   python test_client.py --test all
   ```

2. 自我進化系統測試:
   ```bash
   # 測試反思、生命週期和抽象系統
   python test_self_evolving.py
   ```

3. 向量搜索測試:
   ```bash
   # 測試向量嵌入和相似度搜索功能
   python test_vector_search.py
   ```

4. 控制台互動測試:
   ```bash
   # 運行控制台互動測試，直接與知識系統對話
   python tests/run_console_test.py
   ```

5. AI模型集成測試:
   ```bash
   # 測試各個集成的AI模型功能
   python tests/test_claude.py
   python tests/test_gemini.py
   python tests/test_firecrawl.py
   ```

## 系統進化路線圖與未來展望

### 已完成功能

1. ✅ **核心知識結構**：知識圖譜的基本節點、邊緣與主題群組模型
2. ✅ **知識提取與放置系統**：能夠從對話中自動提取知識並恰當放置
3. ✅ **自主反思循環**：完整實現 OODA (觀察-定向-決策-行動) 反思循環
4. ✅ **能量系統**：模擬生物系統的能量分配、消耗與再生機制
5. ✅ **生命週期管理**：知識節點的狀態轉換和自然演化
6. ✅ **抽象層級體系**：支持從具體事例到抽象原則的分層知識結構
7. ✅ **HTTPS/WSS 安全通訊**：通過 GCP 服務實現加密通訊
8. ✅ **外部感知能力**：通過 Firecrawl 支持獲取外部知識
9. ✅ **自主探索能力**：主動獲取和探索新知識，如 acquisition/manager.py

### 近期發展方向

1. **語意理解能力優化**：整合先進的視覺智能系統(VI)來提升認知能力
   - 實現文字與視覺信息的融合理解
   - 開發基於視覺推理的知識關聯發現機制
   - 建立多模態知識表示方法

2. **思維能力進階優化**：擴展已實現的認知模式
   - 優化思考脈衝檢測的精確度和效率
   - 增強互動式思考引導的用戶體驗
   - 開發多層次思考路徑的智能分析功能

3. **知識評估系統**：增強對知識可靠性、準確性和實用性的評估能力
   - 實現多維度知識評分機制
   - 基於反思結果優化抽象層級分配
   - 添加知識源可信度評估

4. **自適應用戶模型**：為每個用戶建立專屬的知識偏好和興趣模型
   - 個性化知識推薦機制
   - 基於用戶互動調整知識提取和展示策略
   - 實現自適應對話風格調整

5. **知識圖譜可視化增強**：提升知識圖譜的可視化和互動體驗
   - 多視角知識導航
   - 知識節點連接強度可視化
   - 知識演化歷史回溯功能

### 長期願景

1. **多模態知識整合**：擴展支持圖像、音頻、視頻等多模態知識
   - 支持圖像與文本知識關聯
   - 音頻內容自動提取和知識整合
   - 視頻內容場景理解與知識映射

2. **群體智能與知識森林互聯**：讓多個知識森林系統能夠互相學習和交流
   - 跨實例知識同步與對比
   - 分布式反思和優化機制
   - 知識社區共建模式

3. **符號推理與隱含知識發現**：強化系統的邏輯推理能力
   - 基於已有知識推導隱含關係
   - 發現並填補知識網絡中的邏輯缺失
   - 實現知識圖譜的自我修復與一致性維護

## 主要項目文件

- [src/app.py](src/app.py) - 主要 FastAPI 應用入口
- [src/main.py](src/main.py) - MCP 服務入口
- [src/forest/](src/forest/) - 知識森林核心功能目錄
- [src/ai/](src/ai/) - AI 模型整合目錄
- [src/api/](src/api/) - API 端點和通訊接口
- [pyproject.toml](pyproject.toml) - 項目依賴和配置
- [.env.example](.env.example) - 環境變量示例
- [docker-compose.yml](docker-compose.yml) - Docker配置
- [tests/](tests/) - 測試案例和腳本
- [docs/](docs/) - 詳細技術文檔

## 系統啟動與初始化流程

1. **環境變量載入**：通過 `env_loader.py` 載入配置
2. **資料庫連接**：建立 MongoDB 和 Redis 連接
3. **服務初始化**：按照依賴順序初始化各組件
   - 事件總線 → 任務隊列 → 訊息存儲服務
   - 知識圖管理器 → 知識提取服務 → 知識放置服務
   - 能量管理器 → 生命週期管理器 → 抽象生成器
   - 反思系統 → 平衡管理器 → 評估系統
4. **任務調度器啟動**：設置定期任務和周期性維護
5. **WebSocket 通知設置**：建立實時通訊通道
6. **MCP 工具註冊**：向 AI 模型註冊知識工具
7. **默認用戶初始化**：在開發環境中創建測試用戶

## 故障排查與常見問題

- **導入錯誤**：運行 `python import_fix.py` 修復導入路徑
- **AI 模型初始化失敗**：檢查環境變量設置，確保 API 密鑰正確
- **MongoDB 連接問題**：確保 MongoDB 服務運行且配置正確
- **WebSocket 連接失敗**：檢查端口和網絡設置
- **性能問題**：調整 settings.py 中的能量和反思周期配置

## 貢獻

我們歡迎各種形式的貢獻！請先閱讀[開發者指南](docs/development/developer_guide.md)了解系統架構和代碼組織。開發時請遵循以下原則：

1. **模塊化設計**：每個功能應該有明確的職責邊界
2. **接口優先**：實現前先定義清晰的接口
3. **異步優先**：儘可能使用 async/await 以提高性能
4. **設計模式**：合理運用設計模式，但避免過度工程化
5. **詳細註釋**：關鍵邏輯需有充分註釋，保持文檔和代碼同步更新

## 許可證

此項目根據MIT許可證授權。版權所有 © 2023-2025
