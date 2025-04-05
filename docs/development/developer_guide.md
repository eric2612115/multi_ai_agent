# AI知识森林系统开发者指南

## 欢迎

欢迎加入AI知识森林系统的开发团队！本指南将帮助你快速入门，了解系统架构、代码组织、开发最佳实践以及未来开发计划。

## 开发环境设置

### 系统要求

- Python 3.11+
- MongoDB 6.0+
- Redis 7.0+
- Docker & Docker Compose (推荐)

### 设置开发环境

#### 方法1: 使用Docker (推荐)

1. 克隆代码库:
   ```bash
   git clone <repository-url>
   cd multi_ai_agent
   ```

2. 启动Docker容器:
   ```bash
   docker-compose up -d
   ```
   这将启动所有必要的服务，包括MongoDB和Redis。

3. 访问API文档:
   ```
   http://localhost:8000/docs
   ```

#### 方法2: 手动设置

1. 克隆代码库:
   ```bash
   git clone <repository-url>
   cd multi_ai_agent
   ```

2. 创建并激活虚拟环境:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # 在Windows上使用 .venv\Scripts\activate
   ```

3. 安装依赖:
   ```bash
   pip install poetry
   poetry install
   ```

4. 配置环境变量:
   ```bash
   cp .env.example .env
   # 编辑.env文件，设置必要的API密钥和配置
   ```

5. 启动MongoDB和Redis:
   确保MongoDB和Redis服务已启动并可访问。

6. 启动服务:
   ```bash
   python -m src.main
   ```

7. 访问API文档:
   ```
   http://localhost:8000/docs
   ```

### 运行测试

运行所有测试:
```bash
pytest tests/
```

测试自我进化系统:
```bash
python test_self_evolving.py
```

测试特定组件:
```bash
pytest tests/test_<component_name>.py
```

## 代码组织和架构

### 系统架构概览

AI知识森林系统采用模块化架构，各组件通过事件总线和依赖注入进行交互。核心架构分为以下几层:

1. **数据层**: MongoDB存储、Redis缓存、向量索引
2. **基础服务层**: 事件总线、任务队列、WebSocket服务
3. **知识处理层**: 知识提取、知识放置、知识图谱管理
4. **自我进化层**: 反思系统、能量系统、生命周期管理、抽象层级系统等
5. **交互层**: REST API、WebSocket、MCP工具集成

### 目录结构

```
src/
|-- api/                    # API层
|   |-- rest/               # REST端点
|   |-- websocket/          # WebSocket服务
|   |-- mcp/                # MCP工具集成
|
|-- forest/                 # 知识森林核心
|   |-- extraction/         # 知识提取
|   |-- placement/          # 知识放置
|   |-- graph/              # 图谱管理
|   |-- reflection/         # 反思系统
|   |-- lifecycle/          # 生命周期管理
|   |-- abstraction/        # 抽象层级管理
|   |-- energy/             # 能量系统
|   |-- innovation/         # 概念创新机制
|   |-- balance/            # 自我平衡机制
|   |-- evaluation/         # 系统评估与优化
|   |-- acquisition/        # 主动知识获取
|
|-- services/               # 共享服务
|   |-- event_bus.py        # 事件总线
|   |-- task_queue.py       # 任务队列
|
|-- common/                 # 共享工具和模式
|   |-- base_service.py     # 服务基类
|   |-- decorators.py       # 通用装饰器
|   |-- factory.py          # 工厂模式
|   |-- strategy.py         # 策略模式
|   |-- observer.py         # 观察者模式
|
|-- storage/                # 存储层
|   |-- mongodb.py          # MongoDB实现
|
|-- config/                 # 配置相关
```

### 核心组件

1. **知识提取与放置**
   - `KnowledgeExtractor`: 从文本中提取实体、关系和向量
   - `KnowledgePlacementService`: 决定知识放置位置
   - 文件: `src/forest/extraction.py`, `src/forest/placement.py`

2. **知识图谱管理**
   - `KnowledgeGraphManager`: 管理图谱操作和查询
   - 文件: `src/forest/graph.py`

3. **反思系统**
   - `ReflectionSystem`: 协调OODA循环
   - 文件: `src/forest/reflection/core.py`

4. **能量系统**
   - `EnergyManager`: 管理能量分配和消耗
   - 文件: `src/forest/energy/manager_combined.py`

5. **生命周期管理**
   - `LifecycleManager`: 管理节点状态转换
   - 文件: `src/forest/lifecycle/manager_combined.py`

6. **抽象层级系统**
   - `AbstractionGenerator`: 生成和管理抽象概念
   - 文件: `src/forest/abstraction/generator_combined.py`

更多组件详情请查看`docs/technical/system_architecture.md`。

## 设计模式和最佳实践

### 设计模式

系统使用以下设计模式确保代码的可维护性和可扩展性:

#### 1. 服务基类模式

所有服务继承自`BaseService`基类，提供统一的生命周期管理:

```python
class MyService(BaseService):
    async def _initialize(self):
        # 服务特定初始化
        pass
        
    async def _cleanup(self):
        # 服务特定清理
        pass
        
    @handle_errors(MyServiceError)
    @track_energy(5.0)
    @log_operation("my_operation")
    async def some_operation(self, user_id, data):
        # 操作实现
        return result
```

#### 2. 工厂模式

用于创建各种对象实例:

```python
# 定义工厂
model_factory = Factory[str, AIModel](default_type="claude")

# 注册产品
model_factory.register("claude", ClaudeModel)
model_factory.register("gemini", GeminiModel)

# 使用工厂创建产品
model = model_factory.create("claude", api_key="sk_...")
```

#### 3. 策略模式

封装不同算法和行为:

```python
# 定义策略
class MergeStrategy(Strategy[NodePair, Node]):
    def execute(self, context: NodePair) -> Node:
        # 实现节点合并策略
        return merged_node

# 使用策略管理器
strategy_manager = StrategyManager[str, NodePair, Node](default_strategy="standard")
strategy_manager.register("standard", StandardMergeStrategy())
strategy_manager.register("conservative", ConservativeMergeStrategy())

# 执行策略
result = strategy_manager.execute("standard", node_pair)
```

#### 4. 观察者模式

实现组件间松耦合通信:

```python
# 创建可观察对象
knowledge_events = Observable[str, KnowledgeEvent]()

# 添加观察者
async def handle_node_created(event: KnowledgeEvent):
    # 处理节点创建事件
    pass
    
knowledge_events.add_observer("node_created", handle_node_created)

# 通知观察者
await knowledge_events.notify_observers("node_created", event_data)
```

#### 5. 装饰器模式

处理横切关注点:

```python
@handle_errors(ExtractionError)
@track_energy(10.0)
@log_operation("extract_knowledge")
@retry(attempts=3, delay=1.0)
@cache_result(ttl=60.0)
async def extract_knowledge(content):
    # 实现知识提取
    return extracted_knowledge
```

### 编码最佳实践

#### 异步编程

系统广泛使用`async/await`进行异步处理:

```python
async def process_message(message):
    # 异步处理消息
    extracted = await extraction_service.extract(message.content)
    placement = await placement_service.determine_placement(extracted)
    await graph_manager.update_graph(placement)
```

#### 依赖注入

服务通过构造函数接收依赖:

```python
def __init__(self, 
             storage_provider: Optional[MongoDBProvider] = None,
             energy_manager: Optional[EnergyManager] = None):
    # 保存依赖
    self.storage = storage_provider
    self.energy_manager = energy_manager
    
    # 懒加载缺失的依赖
    if self.storage is None:
        self.storage = MongoDBProvider()
```

#### 错误处理

统一的错误处理策略:

```python
try:
    result = await some_operation()
except OperationError as e:
    logger.error(f"操作失败: {str(e)}")
    # 处理错误
except Exception as e:
    logger.error(f"意外错误: {str(e)}")
    raise ServiceError(f"服务错误: {str(e)}")
```

#### 性能优化

1. **使用缓存装饰器**
   ```python
   @cache_result(ttl=300.0)  # 5分钟缓存
   async def expensive_operation(data):
       # 昂贵的计算...
       return result
   ```

2. **批处理操作**
   ```python
   async def update_multiple_nodes(nodes):
       # 批量更新而非单个更新
       await storage.bulk_update("nodes", nodes)
   ```

3. **使用正确的索引**
   ```python
   # 在应用启动时创建索引
   await storage.create_index("nodes", "vector", vector_dimension=1536)
   await storage.create_index("nodes", "user_id")
   ```

## 扩展系统

### 如何添加新的知识提取策略

```python
# 1. 定义新策略
class MyExtractionStrategy(Strategy[Text, KnowledgeEntities]):
    def execute(self, context: Text) -> KnowledgeEntities:
        # 实现提取策略
        return extracted_entities

# 2. 注册策略
extraction_strategies = StrategyManager[str, Text, KnowledgeEntities]()
extraction_strategies.register("my_strategy", MyExtractionStrategy())

# 3. 在服务中使用
class EnhancedExtractionService(BaseService):
    def __init__(self, strategy_manager=None):
        super().__init__("enhanced_extraction")
        self.strategies = strategy_manager or extraction_strategies
    
    async def extract(self, text, strategy="default"):
        return self.strategies.execute(strategy, text)
```

### 如何添加新的观察者

```python
# 1. 定义处理函数
async def handle_abstraction_created(event: AbstractionEvent):
    # 处理抽象创建事件
    logger.info(f"新抽象已创建: {event.abstraction_id}")
    # 执行相关操作...

# 2. 订阅事件
event_bus.subscribe("abstraction_created", handle_abstraction_created)

# 3. 在适当时机发布事件
await event_bus.publish("abstraction_created", {
    "abstraction_id": new_abstraction.id,
    "level": new_abstraction.level,
    "timestamp": datetime.utcnow()
})
```

### 如何添加新的反思任务处理器

1. 在`src/forest/reflection/handlers/`目录下创建新的处理器类:
   ```python
   from src.forest.reflection.handlers.base import TaskHandler
   
   class MyTaskHandler(TaskHandler):
       task_type = "my_custom_task"
       
       async def handle(self, user_id: str, task: ReflectionTask) -> Dict[str, Any]:
           # 实现任务处理逻辑
           result = {
               "success": True,
               # 任务结果...
           }
           return result
   ```

2. 在`src/forest/reflection/handlers/__init__.py`中注册处理器:
   ```python
   from src.forest.reflection.handlers.my_task_handler import MyTaskHandler
   
   # 添加到处理器映射
   TASK_HANDLERS = {
       # 现有处理器...
       MyTaskHandler.task_type: MyTaskHandler,
   }
   ```

## 下一步开发计划

当前系统已实现了所有核心自我进化功能，下一阶段的开发重点是加强系统的外部感知能力和通信安全性：

### 1. HTTPS/WSS安全通道实现

- SSL证书设置
- 安全WebSocket (WSS)实现
- 安全配置更新

### 2. 外部感知能力增强

- 实时数据流整合
- 扩展Redis用途
- MongoDB连接优化

### 3. 可靠的外部通讯流程

- 通讯漏洞修复
- 分布式系统支持
- 连接管理器优化

### 远期开发方向

1. **多模态知识整合**
   - 扩展到支持图像、音频、视频等多模态知识
   - 实现跨模态知识关联和理解

2. **群体智能与知识森林互联**
   - 实现多个知识森林系统互相学习和交流
   - 知识共享协议和隐私保护机制

3. **用户适应性增强**
   - 根据用户使用模式动态调整知识结构
   - 个性化知识展示和交互

4. **自主探索能力增强**
   - 主动识别知识盲点并寻找相关信息
   - 设计实验验证假设

详细开发计划请参考`docs/NEXT_STEPS.md`。

## 学习路径建议

如果你是新加入团队的开发者，我们建议按以下顺序了解系统：

### 1. 核心概念和架构

首先了解系统的核心概念和总体架构：
- 阅读`docs/overview/system_overview.md`
- 阅读`docs/technical/system_architecture.md`

### 2. 自我进化系统

接下来，深入了解自我进化系统的各个组件：
- 阅读`docs/features/`目录下的各功能文档
- 学习能量系统、生命周期管理、抽象层级和反思系统

### 3. 核心业务组件

然后，研究系统的核心业务组件：
- 了解知识提取和放置机制
- 学习知识图谱管理
- 研究数据模型设计

### 4. 设计模式和工具

最后，学习系统使用的设计模式和工具：
- 研究`src/common/`目录下的通用组件
- 学习系统的事件总线和任务队列
- 了解异步编程模式的应用

## 获取帮助

如果您在开发过程中遇到问题，可以：

1. 查阅相关功能的文档（`docs/features/`目录）
2. 查看实现代码中的文档字符串
3. 检查日志输出以获取错误信息
4. 运行相关测试来验证功能
5. 联系团队其他成员获取支持

祝您在AI知识森林系统开发中取得成功！
