# 可靠的外部通訊流程

## 1. 增强WebSocket连接的稳定性和安全性

在 `src/api/websocket/notifications.py` 和 `src/api/websocket/chat/ws_chat.py` 中添加连接保活和身份验证增强：

```python
# 增强连接保活机制
async def _send_keepalive(self, websocket: WebSocket) -> None:
    """定期发送保活消息"""
    try:
        while True:
            await asyncio.sleep(15)  # 每15秒发送一次保活
            if await self._is_websocket_connected(websocket):
                await websocket.send_json({"type": "keepalive", "timestamp": datetime.now().isoformat()})
            else:
                break
    except asyncio.CancelledError:
        # 正常取消
        pass
    except Exception as e:
        logger.error(f"Keepalive error: {str(e)}")

# 增强身份验证
async def _verify_token(self, token: str, user_id: str) -> bool:
    """验证认证令牌有效性"""
    # ... (在此处添加令牌验证逻辑)

```

## 2. 修复潜在的通信漏洞
添加连接重试和错误恢复机制：

```python
# 添加到 connection manager
async def attempt_reconnect(self, user_id: str, max_attempts: int = 3) -> bool:
    """尝试重新连接断开的用户"""
    # ... (在此处添加重连逻辑)

# 添加到异常处理
async def handle_disconnect_exception(self, websocket: WebSocket, user_id: str, exception: Exception) -> None:
    """处理异常断开连接"""
    # ... (在此处添加异常处理和可能的重连尝试逻辑)

```

## 3. 设计支持分布式部署的通信协议
添加分布式消息中间件支持：

```python
# 创建新文件: src/services/message_broker.py
"""消息中间件服务，支持分布式部署的实时通信"""
import asyncio
from typing import Dict, Any, Callable, List
import json
import redis.asyncio as redis
from common.base_service import BaseService

class MessageBroker(BaseService):
    """消息中间件，支持分布式系统间通信"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        super().__init__("message_broker")
        self.redis_url = redis_url
        self.redis_conn = None
        self.subscribers: Dict[str, List[Callable]] = {} # 修正: 存储频道对应的回调列表
        self._pubsub = None
        self._listener_task = None

    async def _initialize(self) -> None:
        """初始化Redis连接"""
        self.logger.info(f"Connecting to Redis at {self.redis_url}")
        try:
            self.redis_conn = redis.from_url(self.redis_url, decode_responses=True) # decode_responses=True 通常更方便
            await self.redis_conn.ping() # 检查连接
            self._pubsub = self.redis_conn.pubsub(ignore_subscribe_messages=True)
            self.logger.info("Redis connection successful.")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {str(e)}")
            # 可能需要添加重试或退出逻辑

    async def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """发布消息到指定频道"""
        if not self.redis_conn:
            self.logger.error("Cannot publish, Redis connection not initialized.")
            return False
        try:
            await self.redis_conn.publish(channel, json.dumps(message))
            self.logger.debug(f"Published message to {channel}: {message}")
            return True
        except Exception as e:
            self.logger.error(f"Error publishing to {channel}: {str(e)}")
            return False

    async def subscribe(self, channel: str, callback: Callable) -> bool:
        """订阅频道并注册回调函数"""
        if not self._pubsub:
             self.logger.error("Cannot subscribe, PubSub not initialized.")
             return False
        try:
            if channel not in self.subscribers:
                self.subscribers[channel] = []
                await self._pubsub.subscribe(channel)
                self.logger.info(f"Subscribed to Redis channel: {channel}")
            if callback not in self.subscribers[channel]:
                 self.subscribers[channel].append(callback)
                 self.logger.info(f"Registered callback for channel {channel}")
            # 如果监听器未运行，则启动它
            if self._listener_task is None or self._listener_task.done():
                await self.start_listener()
            return True
        except Exception as e:
            self.logger.error(f"Error subscribing to {channel}: {str(e)}")
            return False

    async def _message_handler(self):
        """处理从 Redis Pub/Sub 收到的消息"""
        try:
             async for message in self._pubsub.listen():
                 if message["type"] == "message":
                     channel = message["channel"]
                     data_str = message["data"]
                     self.logger.debug(f"Received message from {channel}: {data_str}")
                     try:
                         data_dict = json.loads(data_str)
                         if channel in self.subscribers:
                              for callback in self.subscribers[channel]:
                                   try:
                                       # 使用 asyncio.create_task 避免阻塞处理循环
                                       asyncio.create_task(callback(channel, data_dict))
                                   except Exception as e:
                                       self.logger.error(f"Error executing callback for {channel}: {str(e)}")
                     except json.JSONDecodeError:
                         self.logger.error(f"Failed to decode JSON from {channel}: {data_str}")
                     except Exception as e:
                          self.logger.error(f"Error processing message from {channel}: {str(e)}")
        except asyncio.CancelledError:
            self.logger.info("Message listener task cancelled.")
        except redis.exceptions.ConnectionError as e:
             self.logger.error(f"Redis connection error in listener: {str(e)}")
             # 此处可以添加重连逻辑
        except Exception as e:
            self.logger.error(f"Unexpected error in message listener: {str(e)}", exc_info=True)
        finally:
             self.logger.info("Message listener stopped.")
             # 可能需要清理资源或重置状态

    async def start_listener(self) -> None:
        """启动订阅监听器"""
        if self._listener_task is None or self._listener_task.done():
             if self._pubsub:
                 self.logger.info("Starting Redis message listener...")
                 self._listener_task = asyncio.create_task(self._message_handler())
             else:
                  self.logger.error("Cannot start listener, PubSub not initialized.")
        else:
            self.logger.warning("Listener task is already running.")

    async def shutdown(self) -> None:
        """关闭连接和监听器"""
        self.logger.info("Shutting down MessageBroker...")
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass # 预期行为
            except Exception as e:
                self.logger.error(f"Error during listener task shutdown: {str(e)}")
        if self._pubsub:
             try:
                 await self._pubsub.unsubscribe() # 取消所有订阅
                 await self._pubsub.close()
                 self.logger.info("Redis PubSub connection closed.")
             except Exception as e:
                  self.logger.error(f"Error closing PubSub connection: {str(e)}")
        if self.redis_conn:
            try:
                await self.redis_conn.close()
                await self.redis_conn.connection_pool.disconnect() # 确保连接池也关闭
                self.logger.info("Redis main connection closed.")
            except Exception as e:
                self.logger.error(f"Error closing Redis connection: {str(e)}")
        self.logger.info("MessageBroker shutdown complete.")

# --- 服务生命周期管理示例 ---
async def main():
    broker = MessageBroker()

    async def sample_callback(channel: str, message: Dict[str, Any]):
        print(f"Received on {channel}: {message}")

    await broker._initialize() # 初始化
    await broker.subscribe("test_channel", sample_callback)
    # await broker.start_listener() # subscribe 内部会启动

    # 模拟发布消息
    await asyncio.sleep(1)
    await broker.publish("test_channel", {"user": "Alice", "text": "Hello!"})
    await asyncio.sleep(1)
    await broker.publish("test_channel", {"user": "Bob", "text": "Hi Alice!"})
    await asyncio.sleep(5) # 等待消息处理

    await broker.shutdown() # 关闭

if __name__ == "__main__":
     try:
         asyncio.run(main())
     except KeyboardInterrupt:
         print("Interrupted by user.")

```