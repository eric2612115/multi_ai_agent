"""知識提煉與萃取模組。

這個模組提供從現有知識中提煉核心原則和規律的功能，
通過高階分析和抽象，將具體知識凝練為更通用的原則。
"""
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import asyncio

from src.storage.mongodb import MongoDBProvider
from src.common.service_base import ServiceBase
from src.common.exceptions import ExtractionError
from src.ai.factory import get_text_model

logger = logging.getLogger(__name__)

class KnowledgeDistiller(ServiceBase):
    """知識提煉器，從複雜信息中提取核心概念與原則。"""
    
    def __init__(self, storage_provider: Optional[MongoDBProvider] = None):
        """初始化知識提煉器。
        
        Args:
            storage_provider: 可選的儲存提供者。如果未提供，將創建一個新的。
        """
        super().__init__(storage_provider)
        self.text_model = get_text_model()
        
        # 批量處理參數
        self.batch_size = 15  # 批量處理的節點數
        self.max_tokens = 1000  # 模型生成的最大標記數
    
    async def distill_core_principles(self, user_id: str, topic_id: str) -> List[Dict[str, Any]]:
        """從主題中提煉核心原則。
        
        Args:
            user_id: 用戶ID。
            topic_id: 主題ID。
            
        Returns:
            提煉出的原則節點列表。
            
        Raises:
            ExtractionError: 提煉過程出錯。
        """
        try:
            # 獲取主題下的所有節點
            nodes = await self.storage.find_documents(
                "nodes",
                {
                    "user_id": user_id,
                    "topic_cluster_id": topic_id,
                    "status": "active"
                }
            )
            
            if not nodes:
                logger.warning(f"No active nodes found for topic {topic_id}")
                return []
                
            # 按抽象層級分組
            abstraction_groups = {}
            for node in nodes:
                level = node.get("abstraction_level", 2)  # 默認為概念層級
                if level not in abstraction_groups:
                    abstraction_groups[level] = []
                abstraction_groups[level].append(node)
            
            # 準備上下文信息，優先使用低層級節點
            context_nodes = []
            for level in sorted(abstraction_groups.keys()):
                context_nodes.extend(abstraction_groups[level][:10])  # 每個層級最多取10個
                if len(context_nodes) >= self.batch_size:
                    break
                    
            # 截斷到指定批量大小
            context_nodes = context_nodes[:self.batch_size]
            
            # 獲取主題信息
            topic_info = await self._get_topic_info(user_id, topic_id)
            topic_name = topic_info.get("label", f"主題 {topic_id[:8]}")
            
            # 構建上下文文本
            context = "\n\n".join([
                f"- {node.get('label', 'Unnamed')}: {node.get('summary', '')}"
                for node in context_nodes if node.get('summary')
            ])
            
            # 提煉原則的提示詞
            prompt = f"""以下是關於「{topic_name}」主題的多個相關概念。請從這些概念中提煉出3-5個核心原則或規律：

            {context}
            
            提煉出的核心原則或規律應該是更高層次的抽象，揭示這些概念背後的共同模式和規律。
            
            請以以下格式回答：
            原則1：[原則名稱]
            說明：[原則解釋]
            
            原則2：[原則名稱]
            說明：[原則解釋]
            
            以此類推。
            """
            
            # 生成原則
            response = await self.text_model.generate_text(prompt, max_tokens=self.max_tokens)
            
            # 解析回應
            principles = []
            current_principle = None
            
            for line in response.strip().split('\n'):
                line = line.strip()
                if line.startswith('原則') and ':' in line:
                    if current_principle:
                        principles.append(current_principle)
                    principle_name = line.split(':', 1)[1].strip()
                    current_principle = {
                        "label": principle_name,
                        "summary": "",
                        "type": "principle",
                        "abstraction_level": 4  # 原則層級
                    }
                elif line.startswith('說明：') and current_principle:
                    current_principle["summary"] = line.replace('說明：', '').strip()
            
            # 添加最後一個原則
            if current_principle:
                principles.append(current_principle)
                
            # 保存原則節點
            created_nodes = []
            for principle in principles:
                # 檢查是否已經存在相似的原則
                existing = await self._find_similar_principles(user_id, topic_id, principle["label"])
                if existing:
                    logger.info(f"Similar principle already exists: {existing.get('label')}")
                    continue
                
                # 創建新原則節點
                principle_data = {
                    "user_id": user_id,
                    "topic_cluster_id": topic_id,
                    "label": principle["label"],
                    "summary": principle["summary"],
                    "type": principle["type"],
                    "abstraction_level": principle["abstraction_level"],
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "status": "active",
                    "source": "distillation",
                    "extracted_terms": [],  # 可以添加從原則中提取的關鍵詞
                    "certainty_score": 0.7,  # 提煉出的原則有一定的不確定性
                    "verification_status": "pending"  # 需要驗證
                }
                
                # 保存到數據庫
                try:
                    node_id = await self.storage.save_document("nodes", principle_data)
                    created_nodes.append({**principle_data, "_id": node_id})
                    
                    # 創建與相關概念的連接
                    await self._create_connections(user_id, node_id, context_nodes[:5])
                    
                    logger.info(f"Created principle node: {node_id}")
                except Exception as e:
                    logger.error(f"Error saving principle node: {e}")
                
            return created_nodes
            
        except Exception as e:
            logger.error(f"Error distilling core principles: {e}")
            raise ExtractionError(f"Failed to distill core principles: {str(e)}")
    
    async def extract_cross_domain_insights(self, user_id: str, topic_ids: List[str]) -> List[Dict[str, Any]]:
        """提取跨領域洞察。
        
        分析多個主題之間的共同模式和規律，提煉出跨領域的洞察和原則。
        
        Args:
            user_id: 用戶ID。
            topic_ids: 主題ID列表。
            
        Returns:
            提煉出的跨領域洞察節點列表。
            
        Raises:
            ExtractionError: 提煉過程出錯。
        """
        if len(topic_ids) < 2:
            logger.warning("Need at least two topics for cross-domain insights")
            return []
            
        try:
            # 獲取每個主題的代表性節點
            topic_representatives = {}
            topic_info = {}
            
            for topic_id in topic_ids:
                # 獲取主題信息
                info = await self._get_topic_info(user_id, topic_id)
                topic_info[topic_id] = info
                
                # 獲取主題下的高抽象級節點（原則層級）
                high_level_nodes = await self.storage.find_documents(
                    "nodes",
                    {
                        "user_id": user_id,
                        "topic_cluster_id": topic_id,
                        "abstraction_level": {"$gte": 3},  # 規則層級或更高
                        "status": "active"
                    },
                    limit=3,
                    sort=[("importance_score", -1)]  # 按重要性排序
                )
                
                # 如果沒有高抽象級節點，獲取任何節點
                if not high_level_nodes:
                    high_level_nodes = await self.storage.find_documents(
                        "nodes",
                        {
                            "user_id": user_id,
                            "topic_cluster_id": topic_id,
                            "status": "active"
                        },
                        limit=3,
                        sort=[("importance_score", -1)]  # 按重要性排序
                    )
                
                topic_representatives[topic_id] = high_level_nodes
            
            # 構建跨領域分析的上下文
            context_parts = []
            for topic_id, nodes in topic_representatives.items():
                topic_name = topic_info[topic_id].get("label", f"主題 {topic_id[:8]}")
                context_parts.append(f"## {topic_name}")
                
                for node in nodes:
                    context_parts.append(f"- {node.get('label', 'Unnamed')}: {node.get('summary', '')}")
                    
                context_parts.append("")  # 空行分隔主題
            
            context = "\n".join(context_parts)
            
            # 提取跨領域洞察的提示詞
            prompt = f"""以下是來自不同主題的一些核心概念和原則。請分析這些主題之間的聯繫，提取出2-3個跨領域的洞察或元原則：

            {context}
            
            請找出這些不同主題之間的共通點、相似模式或可以相互啟發的原則。
            
            請以以下格式回答：
            跨領域洞察1：[洞察名稱]
            說明：[洞察解釋]
            相關主題：[涉及到的主題]
            
            跨領域洞察2：[洞察名稱]
            說明：[洞察解釋]
            相關主題：[涉及到的主題]
            
            以此類推。
            """
            
            # 生成跨領域洞察
            response = await self.text_model.generate_text(prompt, max_tokens=self.max_tokens)
            
            # 解析回應
            insights = []
            current_insight = None
            
            for line in response.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('跨領域洞察') and ':' in line:
                    if current_insight:
                        insights.append(current_insight)
                    insight_name = line.split(':', 1)[1].strip()
                    current_insight = {
                        "label": insight_name,
                        "summary": "",
                        "related_topics": [],
                        "type": "cross_domain_insight",
                        "abstraction_level": 5  # 範式層級，最高抽象層
                    }
                elif line.startswith('說明：') and current_insight:
                    current_insight["summary"] = line.replace('說明：', '').strip()
                elif line.startswith('相關主題：') and current_insight:
                    topics_text = line.replace('相關主題：', '').strip()
                    # 嘗試將主題名稱映射回主題ID
                    for topic_id, info in topic_info.items():
                        topic_name = info.get("label", "")
                        if topic_name and topic_name in topics_text:
                            current_insight["related_topics"].append(topic_id)
            
            # 添加最後一個洞察
            if current_insight:
                insights.append(current_insight)
            
            # 保存洞察節點
            created_nodes = []
            for insight in insights:
                # 檢查是否已經存在相似的洞察
                existing = await self._find_similar_insights(user_id, insight["label"])
                if existing:
                    logger.info(f"Similar insight already exists: {existing.get('label')}")
                    continue
                
                # 如果沒有明確指定相關主題，使用所有提供的主題
                if not insight["related_topics"]:
                    insight["related_topics"] = topic_ids
                
                # 創建跨領域洞察節點
                # 注意：創建在一個特殊的"meta"主題下，或者第一個相關主題下
                primary_topic_id = insight["related_topics"][0] if insight["related_topics"] else topic_ids[0]
                
                insight_data = {
                    "user_id": user_id,
                    "topic_cluster_id": primary_topic_id,
                    "label": insight["label"],
                    "summary": insight["summary"],
                    "type": insight["type"],
                    "abstraction_level": insight["abstraction_level"],
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "status": "active",
                    "source": "cross_domain_distillation",
                    "related_topics": insight["related_topics"],
                    "certainty_score": 0.6,  # 跨領域洞察比單一領域原則更不確定
                    "verification_status": "pending"  # 需要驗證
                }
                
                # 保存到數據庫
                try:
                    node_id = await self.storage.save_document("nodes", insight_data)
                    created_nodes.append({**insight_data, "_id": node_id})
                    
                    # 創建與相關主題代表性節點的連接
                    for topic_id in insight["related_topics"]:
                        if topic_id in topic_representatives:
                            await self._create_connections(user_id, node_id, topic_representatives[topic_id])
                    
                    logger.info(f"Created cross-domain insight node: {node_id}")
                except Exception as e:
                    logger.error(f"Error saving cross-domain insight node: {e}")
            
            return created_nodes
            
        except Exception as e:
            logger.error(f"Error extracting cross-domain insights: {e}")
            raise ExtractionError(f"Failed to extract cross-domain insights: {str(e)}")
    
    async def enhance_node_explanation(self, user_id: str, node_id: str) -> Dict[str, Any]:
        """增強節點的解釋。
        
        通過增加例子、背景和影響來豐富節點的解釋。
        
        Args:
            user_id: 用戶ID。
            node_id: 節點ID。
            
        Returns:
            更新後的節點數據。
            
        Raises:
            ExtractionError: 增強過程出錯。
        """
        try:
            # 獲取節點
            node = await self.storage.get_document("nodes", node_id)
            if not node or node.get("user_id") != user_id:
                raise ExtractionError(f"Node {node_id} not found or not owned by user {user_id}")
                
            # 獲取節點的連接節點，用於上下文
            connected_nodes = await self._get_connected_nodes(user_id, node_id)
            
            # 構建上下文
            connected_text = "\n".join([
                f"- {n.get('label', 'Unnamed')}: {n.get('summary', '')}"
                for n in connected_nodes[:5]  # 最多使用5個連接節點
            ])
            
            node_label = node.get("label", "")
            node_summary = node.get("summary", "")
            
            # 增強解釋的提示詞
            prompt = f"""請為以下概念提供更豐富、更詳細的解釋：

            概念名稱：{node_label}
            現有解釋：{node_summary}
            
            相關概念：
            {connected_text}
            
            請提供一個增強的解釋，包括以下部分：
            1. 詳細說明 - 更深入地解釋概念
            2. 實例與應用 - 提供1-2個具體例子
            3. 影響與重要性 - 說明這個概念為什麼重要
            
            請以完整的段落形式回答，保持語言簡潔、清晰且有深度。回答應包含原始解釋中的重要內容，但大幅擴展和改進它。
            """
            
            # 生成增強解釋
            enhanced_summary = await self.text_model.generate_text(prompt, max_tokens=self.max_tokens)
            
            # 更新節點
            update_data = {
                "summary": enhanced_summary.strip(),
                "updated_at": datetime.utcnow(),
                "has_enhanced_explanation": True
            }
            
            await self.storage.update_document("nodes", node_id, update_data)
            
            # 返回更新後的節點
            updated_node = await self.storage.get_document("nodes", node_id)
            return updated_node
            
        except Exception as e:
            logger.error(f"Error enhancing node explanation: {e}")
            raise ExtractionError(f"Failed to enhance node explanation: {str(e)}")
    
    async def _get_topic_info(self, user_id: str, topic_id: str) -> Dict[str, Any]:
        """獲取主題信息。
        
        Args:
            user_id: 用戶ID。
            topic_id: 主題ID。
            
        Returns:
            主題信息。
        """
        # 嘗試獲取主題根節點
        root_nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "topic_cluster_id": topic_id,
                "parent_node_id": {"$exists": False}
            },
            limit=1
        )
        
        if root_nodes and len(root_nodes) > 0:
            return {
                "label": root_nodes[0].get("label", f"主題 {topic_id[:8]}"),
                "summary": root_nodes[0].get("summary", ""),
                "type": root_nodes[0].get("type", "topic")
            }
            
        # 如果沒有根節點，獲取任何主題節點
        topic_nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "topic_cluster_id": topic_id
            },
            limit=1
        )
        
        if topic_nodes and len(topic_nodes) > 0:
            return {
                "label": topic_nodes[0].get("label", f"主題 {topic_id[:8]}"),
                "summary": topic_nodes[0].get("summary", ""),
                "type": topic_nodes[0].get("type", "unknown")
            }
            
        # 如果沒有任何節點，返回默認信息
        return {
            "label": f"主題 {topic_id[:8]}",
            "summary": "",
            "type": "unknown"
        }
    
    async def _find_similar_principles(self, user_id: str, topic_id: str, principle_label: str) -> Optional[Dict[str, Any]]:
        """查找相似的原則。
        
        Args:
            user_id: 用戶ID。
            topic_id: 主題ID。
            principle_label: 原則標題。
            
        Returns:
            相似的原則，如果沒有則返回None。
        """
        principles = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "topic_cluster_id": topic_id,
                "type": "principle",
                "status": "active"
            }
        )
        
        # 簡單的標題比較，實際中可能需要更複雜的相似性計算
        for principle in principles:
            label = principle.get("label", "")
            if label and (
                label.lower() == principle_label.lower() or
                principle_label.lower() in label.lower() or
                label.lower() in principle_label.lower()
            ):
                return principle
                
        return None
    
    async def _find_similar_insights(self, user_id: str, insight_label: str) -> Optional[Dict[str, Any]]:
        """查找相似的跨領域洞察。
        
        Args:
            user_id: 用戶ID。
            insight_label: 洞察標題。
            
        Returns:
            相似的洞察，如果沒有則返回None。
        """
        insights = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "type": "cross_domain_insight",
                "status": "active"
            }
        )
        
        # 簡單的標題比較
        for insight in insights:
            label = insight.get("label", "")
            if label and (
                label.lower() == insight_label.lower() or
                insight_label.lower() in label.lower() or
                label.lower() in insight_label.lower()
            ):
                return insight
                
        return None
    
    async def _create_connections(self, user_id: str, source_node_id: str, target_nodes: List[Dict[str, Any]]) -> None:
        """創建與目標節點的連接。
        
        Args:
            user_id: 用戶ID。
            source_node_id: 源節點ID。
            target_nodes: 目標節點列表。
        """
        from src.forest.models import RelationshipType
        
        for target_node in target_nodes:
            target_id = target_node["_id"]
            
            # 創建從源節點到目標節點的"explains"關係
            edge_data = {
                "user_id": user_id,
                "source_node_id": source_node_id,
                "target_node_id": target_id,
                "relationship_type": RelationshipType.EXPLAINS,
                "strength": 0.8,
                "context_summary": "由萃取系統自動生成的關係",
                "created_at": datetime.utcnow(),
                "is_active": True,
                "source": "distillation",
                "certainty_score": 0.7
            }
            
            await self.storage.save_document("edges", edge_data)
    
    async def _get_connected_nodes(self, user_id: str, node_id: str) -> List[Dict[str, Any]]:
        """獲取與指定節點相連的節點。
        
        Args:
            user_id: 用戶ID。
            node_id: 節點ID。
            
        Returns:
            連接的節點列表。
        """
        # 獲取所有連接到該節點的邊
        edges = await self.storage.find_documents(
            "edges",
            {
                "user_id": user_id,
                "$or": [
                    {"source_node_id": node_id},
                    {"target_node_id": node_id}
                ],
                "is_active": True
            }
        )
        
        # 收集連接節點的ID
        connected_ids = set()
        for edge in edges:
            if edge["source_node_id"] == node_id:
                connected_ids.add(edge["target_node_id"])
            else:
                connected_ids.add(edge["source_node_id"])
                
        # 獲取連接節點的詳細信息
        connected_nodes = []
        for connected_id in connected_ids:
            node = await self.storage.get_document("nodes", connected_id)
            if node and node.get("status") == "active":
                connected_nodes.append(node)
                
        return connected_nodes