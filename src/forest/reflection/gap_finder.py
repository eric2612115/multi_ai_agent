"""Knowledge gap finder for reflection cycle.

This module provides functionality for identifying knowledge gaps in the forest,
which is part of the Orient phase of the OODA reflection cycle.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set

from forest.models import KnowledgeGap, GapType, StringId
from storage.mongodb import MongoDBProvider
from ai.base import TextGenerationModel
from ai.factory import get_text_generation_model
from common.config import get_settings
from common.exceptions import GapFinderError

settings = get_settings()
logger = logging.getLogger(__name__)

class KnowledgeGapFinder:
    """Identifies knowledge gaps and areas for improvement."""
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                text_model: Optional[TextGenerationModel] = None):
        """Initialize the knowledge gap finder.
        
        Args:
            storage_provider: Optional storage provider
            text_model: Optional text generation model
        """
        self.storage = storage_provider
        self.text_model = text_model
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBProvider()
            
        # Lazy initialize text model if not provided
        if self.text_model is None:
            self.text_model = get_text_generation_model()
            
        # Energy cost for gap finding
        self._energy_cost = 20.0  # Base cost
    
    async def identify_knowledge_gaps(self, 
                                   user_id: str, 
                                   analysis_results: Dict[str, Any]) -> List[KnowledgeGap]:
        """Identify knowledge gaps based on analysis results.
        
        Args:
            user_id: The user ID
            analysis_results: Analysis results from KnowledgeAnalyzer
            
        Returns:
            List of identified knowledge gaps
            
        Raises:
            GapFinderError: If gap identification fails
        """
        try:
            start_time = datetime.utcnow()
            
            # Initial empty list
            gaps = []
            
            # Skip if analysis results are empty or indicate insufficient data
            if not analysis_results or analysis_results.get("summary", {}).get("status") == "insufficient_data":
                logger.info("Insufficient data for gap identification")
                return gaps
                
            # Extract recommendations from analysis results
            recommendations = analysis_results.get("recommendations", [])
            
            # Convert recommendations to knowledge gaps
            for recommendation in recommendations:
                gap = self._recommendation_to_gap(recommendation, user_id)
                if gap:
                    gaps.append(gap)
            
            # Find coverage gaps
            coverage_gaps = await self._find_coverage_gaps(user_id, analysis_results)
            gaps.extend(coverage_gaps)
            
            # Find depth gaps
            depth_gaps = await self._find_depth_gaps(user_id, analysis_results)
            gaps.extend(depth_gaps)
            
            # Find connectivity gaps
            connectivity_gaps = await self._find_connectivity_gaps(user_id, analysis_results)
            gaps.extend(connectivity_gaps)
            
            # Find timeliness gaps
            timeliness_gaps = await self._find_timeliness_gaps(user_id)
            gaps.extend(timeliness_gaps)
            
            # Find consistency gaps
            consistency_gaps = await self._find_consistency_gaps(user_id)
            gaps.extend(consistency_gaps)
            
            # Deduplicate gaps based on type and related nodes
            unique_gaps = self._deduplicate_gaps(gaps)
            
            # Sort by severity (descending)
            unique_gaps.sort(key=lambda g: g.severity, reverse=True)
            
            # Adjust energy cost based on gaps found
            self._energy_cost = 20.0 + (len(unique_gaps) * 2)
            
            # Log the duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Identified {len(unique_gaps)} knowledge gaps for user {user_id} in {duration:.2f}s")
            
            return unique_gaps
            
        except Exception as e:
            logger.error(f"Failed to identify knowledge gaps: {str(e)}")
            raise GapFinderError(f"Failed to identify knowledge gaps: {str(e)}")
    
    def get_energy_cost(self) -> float:
        """Get the energy cost of the last gap identification.
        
        Returns:
            Energy cost
        """
        return self._energy_cost
    
    def _recommendation_to_gap(self, 
                            recommendation: Dict[str, Any], 
                            user_id: str) -> Optional[KnowledgeGap]:
        """Convert an analysis recommendation to a knowledge gap.
        
        Args:
            recommendation: Recommendation from analysis
            user_id: The user ID
            
        Returns:
            Knowledge gap or None
        """
        # Map recommendation types to gap types
        type_mapping = {
            "abstraction_generation": GapType.DEPTH,
            "relation_discovery": GapType.CONNECTIVITY,
            "isolated_component_connection": GapType.CONNECTIVITY,
            "cross_topic_linking": GapType.CONNECTIVITY,
            "global_abstraction": GapType.DEPTH,
            "content_verification": GapType.CONSISTENCY,
            "summary_enhancement": GapType.DEPTH,
            "knowledge_pruning": GapType.TIMELINESS
        }
        
        # Get the gap type
        recommendation_type = recommendation.get("type")
        gap_type = type_mapping.get(recommendation_type)
        
        if not gap_type:
            return None
            
        # Map priority to severity
        priority_to_severity = {
            "high": 0.9,
            "medium": 0.6,
            "low": 0.3
        }
        
        severity = priority_to_severity.get(recommendation.get("priority", "medium"), 0.5)
        
        # Get related node IDs
        related_node_ids = []
        target_topic = recommendation.get("target_topic")
        
        # Create the gap
        gap = KnowledgeGap(
            type=gap_type,
            description=recommendation.get("description", "Knowledge gap identified"),
            topic_id=target_topic,
            related_node_ids=related_node_ids,
            severity=severity,
            identified_at=datetime.utcnow(),
            status="open"
        )
        
        return gap
    
    async def _find_coverage_gaps(self, 
                               user_id: str, 
                               analysis_results: Dict[str, Any]) -> List[KnowledgeGap]:
        """Find coverage gaps (missing topics or areas).
        
        Args:
            user_id: The user ID
            analysis_results: Analysis results
            
        Returns:
            List of coverage gaps
        """
        gaps = []
        
        # Get topic distribution
        topics = analysis_results.get("topics", [])
        
        # If there are too few topics, suggest creating more
        if len(topics) < 3:
            gaps.append(
                KnowledgeGap(
                    type=GapType.COVERAGE,
                    description="Knowledge graph has limited topic coverage",
                    severity=0.7,
                    status="open"
                )
            )
            
        # Look for imbalanced topic distribution
        # If one topic dominates (>70% of nodes), suggest expanding other areas
        total_nodes = sum(topic.get("node_count", 0) for topic in topics)
        if total_nodes > 0:
            for topic in topics:
                percentage = topic.get("percentage", 0)
                if percentage > 70:
                    gaps.append(
                        KnowledgeGap(
                            type=GapType.COVERAGE,
                            description=f"Topic '{topic.get('label', 'Unknown')}' dominates the knowledge graph ({percentage:.1f}%). Consider expanding other knowledge areas.",
                            topic_id=topic.get("topic_id"),
                            severity=0.6,
                            status="open"
                        )
                    )
                    break
        
        # Check if there are any popular or trending topics missing
        # This would require external knowledge, which could be simulated
        # For now, let's check against a predefined list of common topics
        common_topics = await self._get_common_topics_for_user(user_id)
        existing_topic_labels = {topic.get("label", "").lower() for topic in topics}
        
        for common_topic in common_topics:
            # Check if any existing topic is similar to this common topic
            if not any(common_topic.lower() in label or label in common_topic.lower() for label in existing_topic_labels):
                gaps.append(
                    KnowledgeGap(
                        type=GapType.COVERAGE,
                        description=f"Common topic '{common_topic}' not represented in knowledge graph",
                        severity=0.5,
                        status="open"
                    )
                )
        
        return gaps
    
    async def _get_common_topics_for_user(self, user_id: str) -> List[str]:
        """Get common topics that might be relevant for a user.
        
        In a real system, this could analyze user interests, domain, etc.
        For now, we'll use a placeholder implementation.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of common topic names
        """
        # This is a placeholder - in a real system, this would be personalized
        return ["AI", "Machine Learning", "Knowledge Management", "Data Science", "Natural Language Processing"]
    
    async def _find_depth_gaps(self, 
                            user_id: str, 
                            analysis_results: Dict[str, Any]) -> List[KnowledgeGap]:
        """Find depth gaps (lack of detailed knowledge).
        
        Args:
            user_id: The user ID
            analysis_results: Analysis results
            
        Returns:
            List of depth gaps
        """
        gaps = []
        
        # Get abstraction level distribution
        topics = analysis_results.get("topics", [])
        structure = analysis_results.get("structure", {})
        
        # Global abstraction balance
        abstraction_balance = structure.get("abstraction_balance", 1.0)
        abstraction_distribution = structure.get("abstraction_distribution", {})
        
        # Check if there's a severe global abstraction imbalance
        if abstraction_balance < 0.3:
            # Check which levels are missing or underrepresented
            levels = {1: "instance", 2: "concept", 3: "rule", 4: "principle", 5: "paradigm"}
            
            for level, name in levels.items():
                count = abstraction_distribution.get(str(level), 0)
                if count == 0:
                    gaps.append(
                        KnowledgeGap(
                            type=GapType.DEPTH,
                            description=f"Knowledge graph lacks {name}-level abstractions",
                            severity=0.8 if level < 4 else 0.6,  # Higher severity for lower levels
                            status="open"
                        )
                    )
        
        # Check for topics with poor abstraction balance
        for topic in topics:
            if topic.get("abstraction_balance", 1.0) < 0.3 and topic.get("node_count", 0) >= 5:
                # Check which levels are missing in this topic
                abs_dist = topic.get("abstraction_distribution", {})
                
                # For large topics, missing middle abstractions is a bigger problem
                if topic.get("node_count", 0) >= 10:
                    if abs_dist.get(3, 0) == 0 and (abs_dist.get(2, 0) > 0 and abs_dist.get(4, 0) > 0):
                        gaps.append(
                            KnowledgeGap(
                                type=GapType.DEPTH,
                                description=f"Topic '{topic.get('label', 'Unknown')}' is missing rule-level abstractions that connect concepts to principles",
                                topic_id=topic.get("topic_id"),
                                severity=0.8,
                                status="open"
                            )
                        )
                        
                # For all substantive topics, missing high-level abstractions reduces understanding
                if abs_dist.get(4, 0) == 0 and abs_dist.get(3, 0) > 0:
                    gaps.append(
                        KnowledgeGap(
                            type=GapType.DEPTH,
                            description=f"Topic '{topic.get('label', 'Unknown')}' lacks principle-level abstractions that provide deeper understanding",
                            topic_id=topic.get("topic_id"),
                            severity=0.7,
                            status="open"
                        )
                    )
        
        # Check for nodes with poor content quality
        await self._check_incomplete_nodes(user_id, gaps)
        
        return gaps
    
    async def _check_incomplete_nodes(self, user_id: str, gaps: List[KnowledgeGap]) -> None:
        """Check for nodes with incomplete content and add to gaps.
        
        Args:
            user_id: The user ID
            gaps: List to add gaps to
        """
        # Find nodes with missing or very short summaries
        incomplete_nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "status": "active",
                "$or": [
                    {"summary": {"$exists": False}},
                    {"summary": None},
                    {"summary": ""},
                    {"summary": {"$regex": "^.{1,20}$"}}  # Very short summaries (1-20 chars)
                ]
            },
            projection={"_id": 1, "label": 1, "topic_cluster_id": 1},
            limit=5  # Limit to avoid overwhelming
        )
        
        if incomplete_nodes and len(incomplete_nodes) > 0:
            # Group by topic
            by_topic = {}
            for node in incomplete_nodes:
                topic_id = str(node.get("topic_cluster_id", "unknown"))
                if topic_id not in by_topic:
                    by_topic[topic_id] = []
                by_topic[topic_id].append(node)
            
            # Create a gap for each topic with incomplete nodes
            for topic_id, nodes in by_topic.items():
                node_list = ", ".join([f"'{node.get('label', 'Unknown')}'" for node in nodes[:3]])
                if len(nodes) > 3:
                    node_list += f", and {len(nodes) - 3} more"
                    
                gaps.append(
                    KnowledgeGap(
                        type=GapType.DEPTH,
                        description=f"Incomplete content for nodes: {node_list}",
                        topic_id=topic_id if topic_id != "unknown" else None,
                        related_node_ids=[str(node["_id"]) for node in nodes],
                        severity=0.6,
                        status="open"
                    )
                )
    
    async def _find_connectivity_gaps(self, 
                                   user_id: str, 
                                   analysis_results: Dict[str, Any]) -> List[KnowledgeGap]:
        """Find connectivity gaps (poor connections between knowledge).
        
        Args:
            user_id: The user ID
            analysis_results: Analysis results
            
        Returns:
            List of connectivity gaps
        """
        gaps = []
        
        # Check for isolated components
        structure = analysis_results.get("structure", {})
        isolated_count = structure.get("isolated_component_count", 0)
        
        if isolated_count > 0:
            gaps.append(
                KnowledgeGap(
                    type=GapType.CONNECTIVITY,
                    description=f"Found {isolated_count} isolated nodes disconnected from the main knowledge graph",
                    severity=0.8 if isolated_count > 3 else 0.6,
                    status="open"
                )
            )
        
        # Check for topics with poor internal connectivity
        topics = analysis_results.get("topics", [])
        
        for topic in topics:
            if topic.get("connectivity", 1.0) < 0.2 and topic.get("node_count", 0) >= 5:
                gaps.append(
                    KnowledgeGap(
                        type=GapType.CONNECTIVITY,
                        description=f"Topic '{topic.get('label', 'Unknown')}' has poor internal connectivity",
                        topic_id=topic.get("topic_id"),
                        severity=0.7,
                        status="open"
                    )
                )
        
        # Check for lack of cross-topic connections
        if len(topics) >= 2:
            cross_connections = structure.get("cross_topic_connections", 0)
            if cross_connections < len(topics) - 1:
                gaps.append(
                    KnowledgeGap(
                        type=GapType.CONNECTIVITY,
                        description=f"Limited cross-topic connections ({cross_connections}) between {len(topics)} knowledge topics",
                        severity=0.6,
                        status="open"
                    )
                )
        
        # Find potential connections that are missing
        await self._find_missing_relationships(user_id, gaps)
        
        return gaps
    
    async def _find_missing_relationships(self, user_id: str, gaps: List[KnowledgeGap]) -> None:
        """Find potential connections that are missing.
        
        Args:
            user_id: The user ID
            gaps: List to add gaps to
        """
        # This would ideally use vector similarity to find nodes that should be connected
        # For now, we'll implement a simplified version that looks for nodes with similar labels
        
        # Get topics with at least 3 nodes
        pipeline = [
            {"$match": {"user_id": user_id, "status": "active"}},
            {"$group": {"_id": "$topic_cluster_id", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gte": 3}}},
            {"$project": {"topic_id": "$_id", "count": 1, "_id": 0}}
        ]
        
        topics = await self.storage.aggregate("nodes", pipeline)
        
        # For each topic, check internal connectivity
        for topic_data in topics:
            topic_id = topic_data.get("topic_id")
            if not topic_id:
                continue
                
            # Get nodes in this topic
            nodes = await self.storage.find_documents(
                "nodes",
                {
                    "user_id": user_id,
                    "status": "active",
                    "topic_cluster_id": topic_id
                },
                projection={"_id": 1, "label": 1},
                limit=20  # Reasonable limit
            )
            
            if len(nodes) < 3:
                continue
                
            # Check edge count between these nodes
            node_ids = [node["_id"] for node in nodes]
            edge_count = await self.storage.count_documents(
                "edges",
                {
                    "user_id": user_id,
                    "source_node_id": {"$in": node_ids},
                    "target_node_id": {"$in": node_ids}
                }
            )
            
            # Calculate potential edges vs actual edges
            potential_edges = (len(nodes) * (len(nodes) - 1)) / 2
            if potential_edges > 0 and edge_count / potential_edges < 0.2:
                # Get topic label
                topic_label = await self._get_topic_label(user_id, topic_id)
                
                # This topic has sparse connectivity
                gaps.append(
                    KnowledgeGap(
                        type=GapType.CONNECTIVITY,
                        description=f"Topic '{topic_label}' has only {edge_count} connections out of {int(potential_edges)} possible",
                        topic_id=topic_id,
                        related_node_ids=[str(node["_id"]) for node in nodes[:5]],  # Include some related nodes
                        severity=0.6,
                        status="open"
                    )
                )
    
    async def _get_topic_label(self, user_id: str, topic_id: Any) -> str:
        """Get the label for a topic.
        
        Args:
            user_id: The user ID
            topic_id: The topic ID
            
        Returns:
            Topic label
        """
        # Find the root node for this topic
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
            return root_nodes[0].get("label", f"Topic {str(topic_id)[:8]}")
            
        # Fall back to any node in the topic
        topic_nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "topic_cluster_id": topic_id
            },
            limit=1
        )
        
        if topic_nodes and len(topic_nodes) > 0:
            return topic_nodes[0].get("label", f"Topic {str(topic_id)[:8]}")
            
        return f"Topic {str(topic_id)[:8]}"
    
    async def _find_timeliness_gaps(self, user_id: str) -> List[KnowledgeGap]:
        """Find timeliness gaps (outdated information).
        
        Args:
            user_id: The user ID
            
        Returns:
            List of timeliness gaps
        """
        gaps = []
        
        # Set threshold for old nodes (e.g., 90 days)
        threshold_date = datetime.utcnow() - timedelta(days=90)
        
        # Find old nodes that might need updating
        old_nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "status": "active",
                "updated_at": {"$lt": threshold_date}
            },
            projection={"_id": 1, "label": 1, "topic_cluster_id": 1, "updated_at": 1},
            limit=10  # Reasonable limit
        )
        
        if old_nodes and len(old_nodes) > 0:
            # Group by topic
            by_topic = {}
            for node in old_nodes:
                topic_id = str(node.get("topic_cluster_id", "unknown"))
                if topic_id not in by_topic:
                    by_topic[topic_id] = []
                by_topic[topic_id].append(node)
            
            # Create a gap for each topic with old nodes
            for topic_id, nodes in by_topic.items():
                node_list = ", ".join([f"'{node.get('label', 'Unknown')}'" for node in nodes[:3]])
                if len(nodes) > 3:
                    node_list += f", and {len(nodes) - 3} more"
                    
                # Get the oldest update date
                oldest_date = min([node.get("updated_at", datetime.utcnow()) for node in nodes])
                days_old = (datetime.utcnow() - oldest_date).days
                
                gaps.append(
                    KnowledgeGap(
                        type=GapType.TIMELINESS,
                        description=f"Potentially outdated knowledge: {node_list} (last updated {days_old} days ago)",
                        topic_id=topic_id if topic_id != "unknown" else None,
                        related_node_ids=[str(node["_id"]) for node in nodes],
                        severity=0.5 + min(0.4, days_old / 365),  # Higher severity for older nodes
                        status="open"
                    )
                )
        
        # Find nodes marked as obsolete
        obsolete_nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "verification_status": "obsolete"
            },
            projection={"_id": 1, "label": 1, "topic_cluster_id": 1},
            limit=5
        )
        
        if obsolete_nodes and len(obsolete_nodes) > 0:
            node_list = ", ".join([f"'{node.get('label', 'Unknown')}'" for node in obsolete_nodes])
            
            gaps.append(
                KnowledgeGap(
                    type=GapType.TIMELINESS,
                    description=f"Nodes marked as obsolete need updating: {node_list}",
                    related_node_ids=[str(node["_id"]) for node in obsolete_nodes],
                    severity=0.9,  # High severity
                    status="open"
                )
            )
        
        return gaps
    
    async def _find_consistency_gaps(self, user_id: str) -> List[KnowledgeGap]:
        """Find consistency gaps (contradictions or uncertainties).
        
        Args:
            user_id: The user ID
            
        Returns:
            List of consistency gaps
        """
        gaps = []
        
        # Find nodes with low certainty
        uncertain_nodes = await self.storage.find_documents(
            "nodes",
            {
                "user_id": user_id,
                "status": "active",
                "certainty_score": {"$lt": 0.4}
            },
            projection={"_id": 1, "label": 1, "topic_cluster_id": 1, "certainty_score": 1},
            limit=5
        )
        
        if uncertain_nodes and len(uncertain_nodes) > 0:
            node_list = ", ".join([f"'{node.get('label', 'Unknown')}' ({node.get('certainty_score', 0):.2f})" for node in uncertain_nodes])
            
            gaps.append(
                KnowledgeGap(
                    type=GapType.CONSISTENCY,
                    description=f"Low certainty knowledge: {node_list}",
                    related_node_ids=[str(node["_id"]) for node in uncertain_nodes],
                    severity=0.7,
                    status="open"
                )
            )
        
        # Find contradict relationships
        contradict_edges = await self.storage.find_documents(
            "edges",
            {
                "user_id": user_id,
                "relationship_type": "contradicts"
            },
            limit=5
        )
        
        if contradict_edges and len(contradict_edges) > 0:
            # Get the node labels for these contradictions
            contradiction_details = []
            related_nodes = set()
            
            for edge in contradict_edges:
                source_id = edge.get("source_node_id")
                target_id = edge.get("target_node_id")
                
                source_node = await self.storage.get_document("nodes", source_id)
                target_node = await self.storage.get_document("nodes", target_id)
                
                if source_node and target_node:
                    source_label = source_node.get("label", "Unknown")
                    target_label = target_node.get("label", "Unknown")
                    
                    contradiction_details.append(f"'{source_label}' contradicts '{target_label}'")
                    related_nodes.add(str(source_id))
                    related_nodes.add(str(target_id))
            
            if contradiction_details:
                contradiction_text = "; ".join(contradiction_details)
                
                gaps.append(
                    KnowledgeGap(
                        type=GapType.CONSISTENCY,
                        description=f"Contradictions in knowledge graph: {contradiction_text}",
                        related_node_ids=list(related_nodes),
                        severity=0.8,  # High severity
                        status="open"
                    )
                )
        
        return gaps
    
    def _deduplicate_gaps(self, gaps: List[KnowledgeGap]) -> List[KnowledgeGap]:
        """Deduplicate gaps based on type and related nodes.
        
        Args:
            gaps: List of gaps
            
        Returns:
            Deduplicated list of gaps
        """
        # Track unique gaps by their signature
        unique_gaps = {}
        
        for gap in gaps:
            # Create a signature based on type and related entities
            signature = (
                gap.type,
                gap.topic_id,
                tuple(sorted(gap.related_node_ids)) if gap.related_node_ids else None
            )
            
            # If we haven't seen this signature, or the new gap has higher severity
            if (signature not in unique_gaps or 
                gap.severity > unique_gaps[signature].severity):
                unique_gaps[signature] = gap
        
        return list(unique_gaps.values())
