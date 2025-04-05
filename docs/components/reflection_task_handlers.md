# 反思任務處理器架構

## 概述

反思任務處理器（Reflection Task Handlers）是AI知識森林系統中負責執行OODA循環（觀察-定向-決策-行動）中"行動"階段的組件。每個處理器專注於處理特定類型的任務，如主題擴展、抽象生成、關係發現等。

本架構採用工廠模式和策略模式，使得系統能夠根據任務類型動態創建和調用相應的處理器，從而實現高度的可擴展性和靈活性。

## 主要組件

### 1. 任務處理器基類 (TaskHandler)

所有任務處理器的抽象基類，定義了通用接口和基礎功能：

- **task_type屬性**：處理器處理的任務類型
- **handle方法**：執行任務的核心邏輯
- **共享依賴**：storage、text_model等依賴項

### 2. 任務執行器 (TaskExecutor)

負責協調和調度不同的任務處理器：

- 維護處理器緩存
- 管理能量消耗和分配
- 提供錯誤處理和日誌記錄
- 使用工廠模式動態創建處理器實例

### 3. 具體處理器實現

系統包含以下主要處理器：

| 處理器類 | 任務類型 | 主要功能 |
|---------|--------|--------|
| TopicExpansionHandler | topic_expansion | 擴展現有主題或創建新主題 |
| AbstractionGenerationHandler | abstraction_generation | 從相關節點生成更高層次的抽象 |
| KnowledgePruningHandler | knowledge_pruning | 識別和歸檔低價值節點 |
| RelationDiscoveryHandler | relation_discovery | 發現節點間的隱含關係 |
| ContentVerificationHandler | content_verification | 驗證節點內容的一致性和準確性 |
| ImportanceRedistributionHandler | importance_redistribution | 重新分配節點重要性分數 |
| LifecycleManagementHandler | knowledge_lifecycle_management | 管理節點生命週期 |
| StrategyAdaptationHandler | learning_strategy_adaptation | 調整學習策略參數 |

## 工作流程

1. **任務創建**：反思系統的規劃器創建任務
2. **處理器選擇**：任務執行器根據任務類型選擇合適的處理器
3. **能量檢查**：檢查是否有足夠的能量執行任務
4. **任務執行**：處理器執行任務，生成結果
5. **能量消耗**：記錄消耗的能量
6. **結果返回**：返回執行結果給反思系統

## 任務處理示例

以主題擴展任務為例：

1. 反思系統識別知識覆蓋度缺口
2. 規劃器創建主題擴展任務
3. 任務執行器選擇TopicExpansionHandler
4. TopicExpansionHandler使用AI提取主題名稱，生成相關概念
5. 創建新的知識節點和關聯關係
6. 返回結果，包括創建的節點和邊的數量

## 擴展性

添加新的任務類型和處理器非常簡單：

1. 創建新的處理器類，繼承TaskHandler
2. 實現task_type屬性和handle方法
3. 在handlers/__init__.py中註冊新處理器

系統會自動發現和使用新添加的處理器，無需修改其他代碼。

## 依賴注入

處理器使用依賴注入模式，通過構造函數接收依賴項：

- 依賴從TaskExecutor傳遞給處理器
- 處理器不直接創建依賴項
- 使測試更容易，可以提供模擬依賴

## 錯誤處理

使用裝飾器統一處理錯誤：

- @handle_errors裝飾器捕獲並記錄異常
- 提供統一的錯誤結構
- 詳細記錄日誌以便調試

## 檔案結構

```
src/forest/reflection/
├── handlers/
│   ├── __init__.py                   # 處理器註冊和映射
│   ├── base.py                       # 處理器基類
│   ├── topic_expansion.py            # 主題擴展處理器
│   ├── abstraction_generation.py     # 抽象生成處理器
│   ├── knowledge_pruning.py          # 知識修剪處理器
│   ├── relation_discovery.py         # 關係發現處理器
│   ├── content_verification.py       # 內容驗證處理器
│   ├── importance_redistribution.py  # 重要性重分配處理器
│   ├── lifecycle_management.py       # 生命週期管理處理器
│   └── strategy_adaptation.py        # 策略適應處理器
├── task_executor.py                  # 任務執行器
└── ...
```

## 能量管理

任務處理器與能量系統深度整合：

- 每個處理器追踪自身消耗的能量
- 執行器在執行任務前檢查能量預算
- 不同任務類型使用不同的能量池
- 當能量不足時，低優先級任務會被跳過

## 未來擴展方向

1. **處理器結果緩存**：為相似參數的任務緩存結果，減少重複計算
2. **自適應能量分配**：基於過去執行效果動態調整任務能量分配
3. **並行任務執行**：同時執行多個獨立任務，提高處理效率
4. **智能排序**：根據當前知識圖譜狀態動態調整任務優先級
5. **處理器組合**：支持複合任務，協調多個處理器協同工作
6. **可配置處理器**：通過配置文件調整處理器行為，無需修改代碼

## 實現考量

1. **性能優化**：關注大量節點操作時的性能，實施批量處理和高效查詢
2. **記憶體管理**：處理大量數據時避免不必要的記憶體使用
3. **測試策略**：每個處理器應有完整的單元測試，包括正常和邊緣情況
4. **版本兼容性**：隨著系統演進，保持API兼容性
5. **日誌和監控**：詳細記錄處理器行為，便於調試和性能分析

## 與其他組件的關係

- **反思系統**：提供任務執行環境，接收執行結果
- **能量系統**：提供能量管理和消耗記錄
- **生命週期管理**：提供節點狀態轉換和管理功能
- **抽象生成系統**：提供抽象節點創建和管理功能
- **AI模型**：提供自然語言處理和理解能力
