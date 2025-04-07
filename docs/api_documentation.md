# AI Knowledge Forest - API 文檔

本文檔詳細描述了AI Knowledge Forest系統的API和WebSocket接口，供前端開發人員參考。

## 基本信息

- **基礎URL**: `http://<server_host>:8001`
- **WebSocket URL**: `ws://<server_host>:8001/ws/chat/ws`
- **API版本**: v1
- **內容類型**: 所有請求和響應均使用`application/json`，除非另有說明

## 身份驗證

除非特別註明為公共API，所有API都需要進行身份驗證。

### 登錄獲取Token

```
POST /api/auth/login
```

**請求體**:
```json
{
  "username": "user123",
  "password": "your_password"
}
```

**響應**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "user123",
    "username": "user123",
    "email": "user@example.com"
  }
}
```

### 使用Token進行身份驗證

在請求頭中加入Authorization字段:

```
Authorization: Bearer <your_access_token>
```

## REST API 端點

### 用戶會話

#### 1. 創建新會話

```
POST /api/public/conversations/
```

**請求體**:
```json
{
  "user_id": "user123",
  "title": "新的對話主題"
}
```

**響應**:
```json
{
  "id": "574a1657-b583-4c61-a8a5-931a7db7bf45",
  "user_id": "user123",
  "title": "新的對話主題",
  "created_at": "2025-04-08T01:24:41.537Z",
  "updated_at": "2025-04-08T01:24:41.537Z"
}
```

#### 2. 獲取用戶會話列表

```
GET /api/public/conversations/user/{user_id}
```

**查詢參數**:
- `limit` (可選): 返回結果數量限制，默認10
- `skip` (可選): 跳過前N個結果，用於分頁

**響應**:
```json
{
  "conversations": [
    {
      "id": "574a1657-b583-4c61-a8a5-931a7db7bf45",
      "user_id": "user123",
      "title": "新的對話主題",
      "created_at": "2025-04-08T01:24:41.537Z",
      "updated_at": "2025-04-08T01:24:41.537Z",
      "message_count": 5,
      "tags": ["AI", "知識圖譜"]
    },
    {
      "id": "1b04d333-4e54-4db0-a4bd-2fb3eedacec5",
      "user_id": "user123",
      "title": "關於環境保護的討論",
      "created_at": "2025-04-07T15:30:22.124Z",
      "updated_at": "2025-04-07T15:45:18.761Z",
      "message_count": 8,
      "tags": ["環境", "可持續性"]
    }
  ],
  "total": 2
}
```

#### 3. 獲取會話詳情

```
GET /api/public/conversations/{conversation_id}
```

**查詢參數**:
- `include_messages` (可選): 布爾值，是否包含消息內容，默認true

**響應**:
```json
{
  "id": "574a1657-b583-4c61-a8a5-931a7db7bf45",
  "user_id": "user123",
  "title": "新的對話主題",
  "created_at": "2025-04-08T01:24:41.537Z",
  "updated_at": "2025-04-08T01:24:41.537Z",
  "messages": [
    {
      "id": "668bdde9-455e-4986-aeda-64aef4c75f3c",
      "speaker": "agent",
      "text": "我是AI知識森林助手。我能幫助您構建和管理知識網絡。我可以回答問題，自動整合回答到您的知識森林中，識別概念之間的連接，並將複雜信息總結為結構化知識。今天我能如何幫助您擴展知識？",
      "timestamp": "2025-04-08T01:27:14.071Z",
      "message_type": "normal"
    },
    {
      "id": "7890abcd-efgh-ijkl-mnop-qrstuvwxyz",
      "speaker": "user",
      "text": "你好，請介紹一下知識森林是什麼",
      "timestamp": "2025-04-08T01:28:22.543Z",
      "message_type": "normal"
    }
  ],
  "tags": ["AI", "知識圖譜"]
}
```

#### 4. 刪除會話

```
DELETE /api/public/conversations/{conversation_id}
```

**請求體**:
```json
{
  "user_id": "user123"
}
```

**響應**:
```json
{
  "success": true,
  "message": "會話已刪除"
}
```

### 知識圖譜

#### 1. 獲取知識圖譜

```
GET /api/public/knowledge/graph
```

**查詢參數**:
- `user_id` (必填): 用戶ID
- `topic_cluster_id` (可選): 特定主題集群ID
- `include_dormant` (可選): 布爾值，是否包含休眠節點，默認false

**響應**:
```json
{
  "nodes": [
    {
      "id": "node1",
      "user_id": "user123",
      "label": "人工智能",
      "type": "concept",
      "summary": "人工智能（AI）是指計算機系統執行通常需要人類智能的任務的能力",
      "status": "active",
      "importance_score": 0.85,
      "abstraction_level": 3
    },
    {
      "id": "node2",
      "user_id": "user123",
      "label": "機器學習",
      "type": "concept",
      "summary": "機器學習是AI的一個子集，專注於讓系統從數據中學習",
      "status": "active",
      "importance_score": 0.78,
      "abstraction_level": 2
    }
  ],
  "edges": [
    {
      "id": "edge1",
      "source_node_id": "node1",
      "target_node_id": "node2",
      "relationship_type": "part_of",
      "strength": 0.9
    }
  ],
  "metadata": {
    "total_nodes": 2,
    "total_edges": 1,
    "active_nodes": 2,
    "dormant_nodes": 0
  }
}
```

#### 2. 檢索節點詳情

```
GET /api/public/knowledge/node/{node_id}
```

**查詢參數**:
- `user_id` (必填): 用戶ID
- `include_neighbors` (可選): 布爾值，是否包含相鄰節點，默認false

**響應**:
```json
{
  "id": "node1",
  "user_id": "user123",
  "label": "人工智能",
  "type": "concept",
  "summary": "人工智能（AI）是指計算機系統執行通常需要人類智能的任務的能力",
  "content": "人工智能（AI）指的是設計用於執行通常需要人類智能的任務的計算機系統。這些任務包括學習、推理、解決問題、感知和語言理解。人工智能在各個領域都有應用，從自動駕駛汽車到醫療診斷，再到智能助手和推薦系統。",
  "created_at": "2025-04-01T10:15:22.124Z",
  "updated_at": "2025-04-05T18:30:45.761Z",
  "status": "active",
  "abstraction_level": 3,
  "importance_score": 0.85,
  "conversation_ids": ["574a1657-b583-4c61-a8a5-931a7db7bf45"],
  "neighbors": [
    {
      "id": "node2",
      "label": "機器學習",
      "type": "concept",
      "relationship": "part_of",
      "relationship_strength": 0.9
    }
  ]
}
```

#### 3. 搜索知識

```
GET /api/public/knowledge/search
```

**查詢參數**:
- `user_id` (必填): 用戶ID
- `query` (必填): 搜索查詢字符串
- `limit` (可選): 結果數量限制，默認10
- `min_similarity` (可選): 最小相似度閾值，默認0.6

**響應**:
```json
{
  "results": [
    {
      "id": "node1",
      "label": "人工智能",
      "type": "concept",
      "summary": "人工智能（AI）是指計算機系統執行通常需要人類智能的任務的能力",
      "score": 0.92,
      "context": "本節點提到了人工智能的基本定義和應用領域"
    },
    {
      "id": "node3",
      "label": "深度學習",
      "type": "concept",
      "summary": "深度學習是機器學習的一個專門形式，使用具有多層（因此是"深度"）的神經網絡來分析數據的各種因素",
      "score": 0.78,
      "context": "與搜索的AI主題高度相關"
    }
  ],
  "total": 2,
  "query_embedding_available": true
}
```

#### 4. 提取知識

```
POST /api/public/knowledge/extract
```

**請求體**:
```json
{
  "user_id": "user123",
  "conversation_id": "574a1657-b583-4c61-a8a5-931a7db7bf45",
  "content": "人工智能（AI）指的是設計用於執行通常需要人類智能的任務的計算機系統。這些任務包括學習、推理、解決問題、感知和語言理解。機器學習（ML）是AI的一個子集，專注於使系統能夠從數據中學習而無需顯式編程。深度學習是ML的一種專門形式，使用具有多層（因此是"深度"）的神經網絡來分析數據的各種因素。"
}
```

**響應**:
```json
{
  "task_id": "knowledge_extraction_1744018034.095528",
  "status": "scheduled",
  "message": "知識提取任務已安排，處理中"
}
```

#### 5. 檢查任務狀態

```
GET /api/public/knowledge/task/{task_id}
```

**響應**:
```json
{
  "task_id": "knowledge_extraction_1744018034.095528",
  "status": "completed",
  "message": "知識提取已完成",
  "result": {
    "nodes_created": 3,
    "nodes_updated": 0,
    "edges_created": 2
  },
  "updated_at": "2025-04-08T01:27:29.307Z"
}
```

#### 6. 獲取知識質量指標

```
GET /api/knowledge/quality
```

**查詢參數**:
- `user_id` (必填): 用戶ID

**響應**:
```json
{
  "overall_quality": 0.78,
  "metrics": {
    "node_count": 150,
    "edge_count": 215,
    "topic_count": 12,
    "avg_node_degree": 2.87,
    "graph_density": 0.023,
    "connected_components": 3,
    "avg_certainty_score": 0.81,
    "verified_node_ratio": 0.35,
    "dormant_node_ratio": 0.08,
    "topic_entropy": 0.76
  },
  "rules": {
    "passed": 12,
    "failed": 3,
    "warnings": 2
  },
  "improvements": [
    "增加節點之間的連接性",
    "提高關鍵主題的覆蓋深度",
    "重新驗證低確定性的節點"
  ]
}
```

### 反思系統

#### 1. 觸發反思循環

```
POST /api/reflection/trigger
```

**請求體**:
```json
{
  "user_id": "user123",
  "energy_budget": 100,
  "priorities": ["connectivity", "depth", "verification"]
}
```

**響應**:
```json
{
  "cycle_id": "reflection_cycle_1744018034.095528",
  "status": "started",
  "message": "反思循環已開始"
}
```

#### 2. 檢查反思循環狀態

```
GET /api/reflection/cycle/{cycle_id}
```

**查詢參數**:
- `user_id` (必填): 用戶ID

**響應**:
```json
{
  "cycle_id": "reflection_cycle_1744018034.095528",
  "status": "completed",
  "start_time": "2025-04-08T01:27:29.307Z",
  "end_time": "2025-04-08T01:30:12.543Z",
  "energy_consumed": 78.5,
  "summary": "本次反思循環識別了3個知識差距，執行了5個優化任務，創建了2個新的抽象概念",
  "identified_gaps": [
    {
      "type": "connectivity",
      "description": "環保科技和可再生能源主題之間的連接不足",
      "severity": 0.75
    }
  ],
  "executed_tasks": [
    {
      "type": "relation_discovery",
      "priority": 2,
      "energy_cost": 15.3,
      "result": "識別並添加了7個新的節點關係"
    }
  ],
  "quality_check_results": {
    "quality_score": 0.82,
    "improvement": 0.04,
    "rule_results": [
      {
        "rule_name": "connectivity_density",
        "passes": true,
        "explanation": "知識圖譜連接密度在理想範圍內"
      }
    ]
  }
}
```

## WebSocket API

### 聊天WebSocket

#### 連接

```
WebSocket: ws://<server_host>:8001/ws/chat/ws?user_id=user123&conversation_id=574a1657-b583-4c61-a8a5-931a7db7bf45
```

**查詢參數**:
- `user_id` (必填): 用戶ID
- `conversation_id` (可選): 會話ID，如果提供則加入現有會話

#### 消息格式

##### 1. 服務器發送的歡迎消息

```json
{
  "id": "668bdde9-455e-4986-aeda-64aef4c75f3c",
  "sender": "agent",
  "text": "我是AI知識森林助手。我能幫助您構建和管理知識網絡。我可以回答問題，自動整合回答到您的知識森林中，識別概念之間的連接，並將複雜信息總結為結構化知識。今天我能如何幫助您擴展知識？",
  "message_type": "normal",
  "timestamp": "2025-04-08T01:27:14.071Z",
  "format_version": "1.0.0",
  "metadata": {}
}
```

##### 2. 客戶端發送查詢

```json
{
  "query": "請解釋什麼是知識森林？",
  "options": {
    "conversation_id": "574a1657-b583-4c61-a8a5-931a7db7bf45",
    "enhanced": false,
    "thinking": false
  }
}
```

**options字段**:
- `conversation_id` (可選): 如果在URL中未提供，則在這裡指定
- `enhanced` (可選): 布爾值，是否使用增強模型，默認false
- `thinking` (可選): 布爾值，是否啟用思考模式，默認false

##### 3. 服務器回應 - 思考過程 (僅當thinking=true時)

```json
{
  "id": "thinking-1744018034.095528",
  "message_type": "thinking",
  "text": "知識森林是一個基於圖形結構的知識表示系統，可以將信息組織成節點和邊...",
  "timestamp": "2025-04-08T01:28:24.123Z"
}
```

##### 4. 服務器回應 - 最終回答

```json
{
  "id": "7a1b2c3d-4e5f-6g7h-8i9j-0k1l2m3n4o5p",
  "sender": "agent",
  "text": "知識森林是一種自組織的知識管理系統，它使用圖形結構來表示和組織信息。在這個系統中：\n\n1. **節點**代表概念、實體或關鍵詞\n2. **邊**表示這些節點之間的關係\n3. **主題集群**將相關的知識組織在一起\n\n與傳統知識庫不同，知識森林能夠：\n\n- 自動從對話中提取知識\n- 建立概念之間的連接\n- 生成更高級別的抽象\n- 隨著時間進化和自我優化\n\n系統會隨著您與AI的互動不斷豐富，形成一個個性化的知識網絡，反映您的興趣和學習軌跡。",
  "message_type": "normal",
  "timestamp": "2025-04-08T01:28:29.456Z",
  "format_version": "1.0.0",
  "metadata": {
    "processing_time": 5.335,
    "knowledge_extracted": true,
    "model_used": "gemini-pro"
  }
}
```

##### 5. 心跳消息 (定期發送)

```json
{
  "type": "heartbeat",
  "timestamp": "2025-04-08T01:28:45.789Z"
}
```

##### 6. 錯誤消息

```json
{
  "message_type": "error",
  "error_code": "PROCESSING_TIMEOUT",
  "text": "請求處理超時。請嘗試較短或較簡單的請求。",
  "timestamp": "2025-04-08T01:30:00.123Z"
}
```

### 可能的錯誤狀態碼

| 錯誤碼 | 描述 |
|--------|------|
| `PROCESSING_TIMEOUT` | 請求處理超時 |
| `AUTHENTICATION_ERROR` | 身份驗證失敗 |
| `INVALID_REQUEST` | 無效的請求格式 |
| `SERVER_ERROR` | 服務器內部錯誤 |
| `TOO_MANY_REQUESTS` | 請求頻率過高 |
| `CONNECTION_CLOSED` | WebSocket連接已關閉 |

## 通知WebSocket

```
WebSocket: ws://<server_host>:8001/ws/notifications?user_id=user123
```

### 通知類型

#### 1. 知識提取完成

```json
{
  "type": "knowledge_extraction_complete",
  "task_id": "knowledge_extraction_1744018034.095528",
  "timestamp": "2025-04-08T01:28:29.456Z",
  "data": {
    "conversation_id": "574a1657-b583-4c61-a8a5-931a7db7bf45",
    "nodes_created": 3,
    "edges_created": 2
  }
}
```

#### 2. 反思循環更新

```json
{
  "type": "reflection_cycle_update",
  "cycle_id": "reflection_cycle_1744018034.095528",
  "timestamp": "2025-04-08T01:29:15.789Z",
  "data": {
    "stage": "DECIDE",
    "progress": 0.65,
    "energy_consumed": 45.2,
    "message": "識別了3個知識差距，正在規劃優化任務"
  }
}
```

#### 3. 連接跨域通知

```json
{
  "type": "cross_link_detected",
  "timestamp": "2025-04-08T01:30:20.456Z",
  "data": {
    "source_node_id": "node1",
    "target_node_id": "node42",
    "source_topic": "AI技術",
    "target_topic": "環境可持續性",
    "relationship_type": "cross_links",
    "strength": 0.82,
    "context": "AI技術應用於環境監測和可持續發展"
  }
}
```

## 注意事項

1. **錯誤處理**: 所有端點在發生錯誤時都會返回適當的HTTP狀態碼和錯誤詳情。

2. **速率限制**: API有速率限制以防止過度使用。超出限制將返回429狀態碼。

3. **版本管理**: 目前使用的是v1版本的API。未來版本更新將在URL路徑中指明版本。

4. **WebSocket重連**: 如果WebSocket連接中斷，客戶端應實現指數退避重連策略。

5. **數據類型**:
   - 所有ID均為字符串
   - 時間戳使用ISO 8601格式
   - 分數和權重在0.0到1.0之間
   - 向量嵌入為浮點數組

6. **安全建議**:
   - 對敏感操作使用HTTPS
   - 定期刷新認證Token
   - 妥善處理用戶敏感信息

## 開發工具和資源

- **Postman集合**: [下載鏈接] - 包含所有API端點的Postman集合
- **WebSocket測試客戶端**: `/test_client.py` - 可用於測試WebSocket連接
- **範例代碼**: 查看GitHub倉庫中的`/examples`目錄

## 聯繫支持

如有任何問題或需要幫助，請聯繫開發團隊或提交GitHub issue。