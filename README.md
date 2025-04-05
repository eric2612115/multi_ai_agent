# AI 知識森林系統：自我進化的智慧系統

## 項目概述

AI 知識森林是一個基於對話內容自動構建知識圖譜的系統，具有自我進化和自主反思能力。它不僅能夠從用戶與 AI 的對話中提取重要概念、實體和關係，將這些知識組織成一個結構化的圖譜，還能通過自主反思循環優化知識結構，實現知識的有機生長和自然演化。

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

## 技術堆疊

- **FastAPI**：後端 Web 框架（使用最新的 lifespan 事件管理）
- **MongoDB**：數據存儲及向量搜索
- **Redis**：緩存和訊息佇列
- **外部 AI 模型**：Claude、Gemini、Firecrawl 等
- **WebSocket**：實時通信
- **asyncio**：異步處理
- **MCP**：Model Context Protocol 集成

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
- `POST /api/reflection/trigger` - 觸發反思循環
- `GET /api/reflection/cycles` - 獲取反思循環列表
- `GET /api/reflection/cycles/{cycle_id}` - 獲取特定反思循環詳情
- `GET /api/reflection/gaps` - 獲取識別的知識缺口

### WebSocket 端點

- `WebSocket /ws/knowledge/notifications` - 接收知識圖譜更新通知
- `WebSocket /ws/reflection/status` - 接收反思循環狀態更新

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
   pip install poetry
   poetry install
   ```

   c. 配置環境變量:
   ```bash
   cp .env.example .env
   # 編輯.env文件，設置必要的API密鑰和配置
   ```

   d. 啟動服務:
   ```bash
   python -m src.app
   ```

4. 訪問API文檔:
   ```
   http://localhost:8000/docs
   ```

### 運行測試

運行自我進化系統測試:
```bash
python test_self_evolving.py
```

## 未來展望

1. **HTTPS/WSS 安全通道實現**：設置 SSL 證書、配置 WSS 通訊(Done)
   1. by using GCP services
2. **外部感知能力增強**：實時數據流整合、優化数据存储和处理(Done)
   1. by using firecrawl
3. **可靠的外部通訊流程**：修復通訊漏洞、實現分布式系統支持
   1. read [docs/NextSteps.md](docs/NextSteps.md) for more details
4. **多模態知識整合**：擴展到支持圖像、音頻、視頻等多模態知識(Pending)
5. **群體智能與知識森林互聯**：讓多個知識森林系統能夠互相學習和交流(Pending)
6. **自主探索能力增強**：實現主動獲取和探索新知識的能力(Done)
    1. 这部分确实已经实现了基础功能，如 acquisition/manager.py 所示。

## 主要項目文件

- [pyproject.toml](pyproject.toml) - 项目依赖和配置
- [.env.example](.env.example) - 环境变量示例
- [docker-compose.yml](docker-compose.yml) - Docker配置

## 貢獻

我們歡迎各種形式的貢獻！請先閱讀[開發者指南](docs/development/developer_guide.md)了解系統架構和代碼組織。

## 許可證

此項目根據MIT許可證授權。
