"""分布式消息中间件服务，支持跨实例通信。

此模块实现了基于Redis的发布/订阅模式，使系统能够在分布式环境中可靠通信。
"""
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Callable, Union, Set
from datetime import datetime

import redis.asyncio as redis

from src.common.base_service import BaseService
from src.common.decorators import handle_errors, retry
from src.common.exceptions import ServiceError
from src.common.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 消息处理器类型
MessageHandler = Callable[[Dict[str, Any]], Union[None, asyncio.tasks.Task]]


class MessageBroker(BaseService):
    """分布式消息中间件服务，基于Redis实现跨实例通信。
    
    此服务提供了可靠的消息发布/订阅功能，确保在分布式部署环境中
    系统各组件能够保持同步和协调。
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """初始化消息中间件服务。
        
        Args:
            redis_url: Redis连接URL，默认从配置中获取
        """
        super().__init__("message_broker")
        self.redis_url = redis_url or getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        self.redis_conn = None
        self.pubsub = None
        self.handlers: Dict[str, Set[MessageHandler]] = {}
        self.listener_task = None
        self.running = False
        self.instance_id = datetime.utcnow().timestamp()  # 唯一实例标识符
    
    async def _initialize(self) -> None:
        """服务初始化。"""
        try:
            self.logger.info(f"正在连接Redis: {self.redis_url}")
            self.redis_conn = redis.from_url(self.redis_url)
            
            # 测试连接
            await self.redis_conn.ping()
            self.logger.info("Redis连接成功")
            
            # 初始化发布/订阅客户端
            self.pubsub = self.redis_conn.pubsub()
            
            # 注册服务发现频道
            await self.pubsub.subscribe("service_discovery")
            
            # 发布实例上线消息
            await self.publish("service_discovery", {
                "action": "instance_online",
                "instance_id": self.instance_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # 启动监听任务
            self.listener_task = self.add_background_task(self._message_listener())
            self.running = True
        except Exception as e:
            self.logger.error(f"初始化MessageBroker失败: {str(e)}")
            raise ServiceError(f"初始化MessageBroker失败: {str(e)}")
    
    async def _cleanup(self) -> None:
        """服务清理。"""
        self.running = False
        
        # 发布实例下线消息
        if self.redis_conn:
            try:
                await self.publish("service_discovery", {
                    "action": "instance_offline",
                    "instance_id": self.instance_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                self.logger.error(f"发布下线消息失败: {str(e)}")
        
        # 关闭发布/订阅客户端
        if self.pubsub:
            try:
                await self.pubsub.unsubscribe()
                await self.pubsub.close()
            except Exception as e:
                self.logger.error(f"关闭pubsub失败: {str(e)}")
        
        # 关闭Redis连接
        if self.redis_conn:
            try:
                await self.redis_conn.close()
            except Exception as e:
                self.logger.error(f"关闭Redis连接失败: {str(e)}")
    
    @handle_errors(ServiceError)
    @retry(attempts=3, delay=1.0, backoff=2.0)
    async def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """发布消息到指定频道。
        
        Args:
            channel: 频道名称
            message: 消息内容
            
        Returns:
            发布是否成功
            
        Raises:
            ServiceError: 发布失败时抛出异常
        """
        if not self.redis_conn:
            raise ServiceError("Redis连接未初始化")
        
        try:
            # 添加实例标识和时间戳
            if isinstance(message, dict):
                message.setdefault("_instance_id", self.instance_id)
                message.setdefault("_timestamp", datetime.utcnow().isoformat())
            
            # 序列化消息
            message_str = json.dumps(message)
            
            # 发布消息
            await self.redis_conn.publish(channel, message_str)
            return True
        except Exception as e:
            self.logger.error(f"发布消息到'{channel}'失败: {str(e)}")
            raise ServiceError(f"发布消息失败: {str(e)}")
    
    @handle_errors(ServiceError)
    async def subscribe(self, channel: str, handler: MessageHandler) -> bool:
        """订阅频道。
        
        Args:
            channel: 频道名称
            handler: 消息处理函数
            
        Returns:
            订阅是否成功
            
        Raises:
            ServiceError: 订阅失败时抛出异常
        """
        if not self.pubsub:
            raise ServiceError("发布/订阅客户端未初始化")
        
        try:
            # 注册处理函数
            if channel not in self.handlers:
                self.handlers[channel] = set()
                # 首次订阅频道
                await self.pubsub.subscribe(channel)
                self.logger.info(f"订阅频道: {channel}")
            
            self.handlers[channel].add(handler)
            return True
        except Exception as e:
            self.logger.error(f"订阅频道'{channel}'失败: {str(e)}")
            raise ServiceError(f"订阅频道失败: {str(e)}")
    
    @handle_errors(ServiceError)
    async def unsubscribe(self, channel: str, handler: Optional[MessageHandler] = None) -> bool:
        """取消订阅频道。
        
        Args:
            channel: 频道名称
            handler: 特定的处理函数，如果为None则取消所有处理函数
            
        Returns:
            取消订阅是否成功
            
        Raises:
            ServiceError: 取消订阅失败时抛出异常
        """
        if not self.pubsub or channel not in self.handlers:
            return False
        
        try:
            if handler:
                # 移除特定处理函数
                if handler in self.handlers[channel]:
                    self.handlers[channel].remove(handler)
                
                # 如果没有处理函数了，取消订阅频道
                if not self.handlers[channel]:
                    await self.pubsub.unsubscribe(channel)
                    del self.handlers[channel]
                    self.logger.info(f"取消订阅频道: {channel}")
            else:
                # 取消所有处理函数
                await self.pubsub.unsubscribe(channel)
                del self.handlers[channel]
                self.logger.info(f"取消订阅频道: {channel}")
            
            return True
        except Exception as e:
            self.logger.error(f"取消订阅频道'{channel}'失败: {str(e)}")
            raise ServiceError(f"取消订阅频道失败: {str(e)}")
    
    async def _message_listener(self) -> None:
        """消息监听循环，处理所有订阅频道的消息。"""
        if not self.pubsub:
            self.logger.error("发布/订阅客户端未初始化，无法启动监听器")
            return
        
        self.logger.info("启动消息监听器")
        
        try:
            while self.running:
                try:
                    # 获取消息，超时1秒
                    message = await asyncio.wait_for(self.pubsub.get_message(ignore_subscribe_messages=True), 1.0)
                    
                    if message and message["type"] == "message":
                        channel = message["channel"].decode("utf-8")
                        data = message["data"].decode("utf-8")
                        
                        try:
                            # 解析消息
                            payload = json.loads(data)
                            
                            # 检查是否是自己发送的消息（可选，取决于需求）
                            sender_id = payload.get("_instance_id")
                            if sender_id == self.instance_id:
                                continue  # 忽略自己发送的消息
                            
                            # 分发消息给处理函数
                            await self._dispatch_message(channel, payload)
                        except json.JSONDecodeError:
                            self.logger.warning(f"无法解析消息: {data}")
                        except Exception as e:
                            self.logger.error(f"处理消息时发生错误: {str(e)}")
                except asyncio.TimeoutError:
                    # 正常超时，继续下一轮
                    continue
                except Exception as e:
                    self.logger.error(f"消息监听器错误: {str(e)}")
                    # 短暂暂停后重试
                    await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            self.logger.info("消息监听器任务已取消")
        except Exception as e:
            self.logger.error(f"消息监听器意外退出: {str(e)}")
    
    async def _dispatch_message(self, channel: str, message: Dict[str, Any]) -> None:
        """分发消息给对应频道的处理函数。
        
        Args:
            channel: 频道名称
            message: 消息内容
        """
        if channel not in self.handlers:
            return
        
        for handler in list(self.handlers[channel]):
            try:
                # 检查处理函数是否是协程函数
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                self.logger.error(f"处理消息处理器错误: {str(e)}")
    
    async def get_active_instances(self) -> List[Dict[str, Any]]:
        """获取当前活跃的服务实例列表。
        
        Returns:
            活跃实例列表
        """
        if not self.redis_conn:
            return []
        
        try:
            # 从Redis获取活跃实例
            instances_data = await self.redis_conn.get("active_instances")
            if not instances_data:
                return []
            
            return json.loads(instances_data)
        except Exception as e:
            self.logger.error(f"获取活跃实例失败: {str(e)}")
            return []
    
    @handle_errors(ServiceError)
    async def heartbeat(self) -> bool:
        """发送心跳，更新实例活跃状态。
        
        Returns:
            是否成功
        """
        if not self.redis_conn:
            return False
        
        try:
            # 更新当前实例的最后活跃时间
            instance_key = f"instance:{self.instance_id}"
            instance_data = {
                "instance_id": self.instance_id,
                "last_seen": datetime.utcnow().isoformat(),
                "channels": list(self.handlers.keys())
            }
            
            # 设置实例数据，30秒过期
            await self.redis_conn.setex(
                instance_key,
                30,  # 30秒过期
                json.dumps(instance_data)
            )
            
            return True
        except Exception as e:
            self.logger.error(f"发送心跳失败: {str(e)}")
            return False
    
    def start_heartbeat_task(self) -> None:
        """启动定期心跳任务。"""
        async def _heartbeat_loop():
            while self.running:
                try:
                    await self.heartbeat()
                except Exception as e:
                    self.logger.error(f"心跳任务错误: {str(e)}")
                await asyncio.sleep(10)  # 每10秒发送一次心跳
        
        self.add_background_task(_heartbeat_loop())
