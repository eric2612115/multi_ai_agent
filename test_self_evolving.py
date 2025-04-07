#!/usr/bin/env python3
"""
测试AI知识森林自我进化系统组件。

这个脚本测试能量系统、生命周期管理和抽象层级管理的核心功能，
以及它们与反思系统的集成情况。
"""
import asyncio
import logging
import sys
from datetime import datetime

# 添加项目根目录到Python路径
import os
sys.path.insert(0, os.path.abspath('.'))

from forest.energy.manager_combined import EnergyManager
from forest.lifecycle.manager_combined import LifecycleManager
from forest.abstraction.generator_combined import AbstractionGenerator
from forest.reflection.core import ReflectionSystem
from storage.mongodb import MongoDBProvider
from forest.graph import KnowledgeGraphManager
from forest.models import Node, NodeStatus, AbstractionLevel

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_energy_system(user_id):
    """测试能量系统的基本功能。"""
    logger.info("=== 测试能量系统 ===")
    
    # 初始化能量管理器
    energy_manager = EnergyManager()
    await energy_manager.start()
    
    try:
        # 获取用户能量
        allocation = await energy_manager.get_user_energy(user_id)
        logger.info(f"用户总能量: {allocation.total_energy}")
        logger.info(f"反思池能量: {allocation.reflection_amount}")
        logger.info(f"能量分配: {allocation.reflection_pct}% 反思, {allocation.abstraction_pct}% 抽象")
        
        # 测试能量消耗
        success, remaining = await energy_manager.consume_energy(
            user_id=user_id,
            pool="reflection",
            amount=5.0,
            component="test_script",
            reason="测试能量消耗"
        )
        
        logger.info(f"能量消耗: {'成功' if success else '失败'}, 剩余: {remaining}")
        
        # 测试能量补充
        new_allocation = await energy_manager.replenish_energy(user_id, amount=10.0)
        logger.info(f"能量补充后: {new_allocation.total_energy}")
        
        return True
    except Exception as e:
        logger.error(f"能量系统测试失败: {str(e)}")
        return False
    finally:
        await energy_manager.stop()


async def test_lifecycle_system(user_id):
    """测试生命周期管理系统的基本功能。"""
    logger.info("=== 测试生命周期管理系统 ===")
    
    # 初始化生命周期管理器
    lifecycle_manager = LifecycleManager()
    
    try:
        # 查找休眠候选节点
        candidates = await lifecycle_manager.find_dormancy_candidates(user_id, limit=5)
        logger.info(f"找到 {len(candidates)} 个休眠候选节点")
        
        # 如果有候选节点，尝试更改其状态
        if candidates:
            node_id = candidates[0]["_id"]
            success, reason = await lifecycle_manager.change_node_status(
                node_id=node_id,
                target_status=NodeStatus.DORMANT
            )
            logger.info(f"状态更改: {'成功' if success else '失败'}, 原因: {reason}")
        
        # 运行生命周期维护
        results = await lifecycle_manager.run_lifecycle_maintenance(user_id)
        logger.info(f"生命周期维护结果: {results}")
        
        return True
    except Exception as e:
        logger.error(f"生命周期系统测试失败: {str(e)}")
        return False


async def test_abstraction_system(user_id):
    """测试抽象层级管理系统的基本功能。"""
    logger.info("=== 测试抽象层级管理系统 ===")
    
    # 初始化抽象生成器
    abstraction_generator = AbstractionGenerator()
    
    try:
        # 尝试生成抽象
        abstractions = await abstraction_generator.generate_abstractions(
            user_id=user_id,
            target_level=AbstractionLevel.PRINCIPLE,
            max_abstractions=3
        )
        
        logger.info(f"生成了 {len(abstractions)} 个抽象")
        
        # 打印抽象信息
        for i, abstraction in enumerate(abstractions):
            logger.info(f"抽象 {i+1}: {abstraction.get('label')} - {abstraction.get('summary')[:50]}...")
        
        return True
    except Exception as e:
        logger.error(f"抽象系统测试失败: {str(e)}")
        return False


async def test_reflection_system(user_id):
    """测试反思系统及其与其他系统的集成。"""
    logger.info("=== 测试反思系统 ===")
    
    # 初始化存储
    storage = MongoDBProvider()
    
    # 初始化能量管理器
    energy_manager = EnergyManager(storage_provider=storage)
    await energy_manager.start()
    
    # 初始化图管理器
    graph_manager = KnowledgeGraphManager(storage_provider=storage)
    
    # 初始化生命周期管理器
    lifecycle_manager = LifecycleManager(
        storage_provider=storage,
        graph_manager=graph_manager
    )
    
    # 初始化抽象生成器
    abstraction_generator = AbstractionGenerator(
        storage_provider=storage,
        graph_manager=graph_manager
    )
    
    # 初始化反思系统
    reflection_system = ReflectionSystem(
        storage_provider=storage,
        energy_manager=energy_manager,
        lifecycle_manager=lifecycle_manager,
        abstraction_generator=abstraction_generator
    )
    
    try:
        # 启动反思循环
        cycle_id = await reflection_system.start_reflection_cycle(
            user_id=user_id,
            energy_budget=50.0,
            trigger_source="manual"
        )
        
        logger.info(f"反思循环启动: {cycle_id}")
        
        # 等待反思循环完成 (最多30秒)
        for _ in range(30):
            # 检查循环状态
            cycle = await reflection_system.get_reflection_cycle(cycle_id)
            status = cycle.get("status", "unknown")
            
            if status != "in_progress":
                logger.info(f"反思循环完成，状态: {status}")
                break
                
            logger.info(f"反思循环进行中，阶段: {cycle.get('current_stage')}")
            await asyncio.sleep(1)
        
        return True
    except Exception as e:
        logger.error(f"反思系统测试失败: {str(e)}")
        return False
    finally:
        await energy_manager.stop()


async def main():
    """主测试函数。"""
    logger.info("开始测试AI知识森林自我进化系统")
    logger.info(f"时间: {datetime.now().isoformat()}")
    
    # 测试用户ID
    user_id = "user123"  # 默认测试用户
    
    # 初始化存储
    storage = MongoDBProvider()
    
    # 检查连接
    if not await storage.is_connected():
        logger.info("连接MongoDB...")
        if not await storage.connect():
            logger.error("无法连接到MongoDB，测试终止")
            return
    
    # 检查测试用户是否存在
    user_nodes = await storage.count_documents("nodes", {"user_id": user_id})
    logger.info(f"用户 {user_id} 拥有 {user_nodes} 个知识节点")
    
    if user_nodes == 0:
        logger.warning(f"用户 {user_id} 没有知识节点，某些测试可能会失败")
    
    # 运行各系统测试
    energy_result = await test_energy_system(user_id)
    lifecycle_result = await test_lifecycle_system(user_id)
    abstraction_result = await test_abstraction_system(user_id)
    reflection_result = await test_reflection_system(user_id)
    
    # 输出测试结果摘要
    logger.info("\n=== 测试结果摘要 ===")
    logger.info(f"能量系统: {'通过' if energy_result else '失败'}")
    logger.info(f"生命周期系统: {'通过' if lifecycle_result else '失败'}")
    logger.info(f"抽象层级系统: {'通过' if abstraction_result else '失败'}")
    logger.info(f"反思系统: {'通过' if reflection_result else '失败'}")
    
    overall_result = all([energy_result, lifecycle_result, abstraction_result, reflection_result])
    logger.info(f"整体结果: {'通过' if overall_result else '失败'}")
    logger.info(f"结束时间: {datetime.now().isoformat()}")


if __name__ == "__main__":
    asyncio.run(main())
