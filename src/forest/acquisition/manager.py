"""Active knowledge acquisition manager for AI Knowledge Forest.

This module provides the main manager for autonomously acquiring new knowledge
to fill gaps in the knowledge forest.
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Set
from datetime import datetime, timedelta
import json
import uuid
import re

from src.common.base_service import BaseService
from src.common.decorators import track_energy, handle_errors, log_operation
from src.common.exceptions import AcquisitionError
from src.storage.mongodb import MongoDBProvider
from src.forest.extraction_service import KnowledgeExtractionService
from src.forest.placement import KnowledgePlacementService
from src.forest.graph import KnowledgeGraphManager
from src.forest.energy.manager_combined import EnergyManager
from src.forest.models import KnowledgeGap, GapType
from src.common.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class AcquisitionManager(BaseService):
    """Active knowledge acquisition manager.
    
    This class is responsible for identifying knowledge gaps and proactively
    acquiring new knowledge from external sources.
    """
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                energy_manager: Optional[EnergyManager] = None,
                extraction_service: Optional[KnowledgeExtractionService] = None,
                placement_service: Optional[KnowledgePlacementService] = None,
                graph_manager: Optional[KnowledgeGraphManager] = None):
        """Initialize the acquisition manager.
        
        Args:
            storage_provider: Optional storage provider
            energy_manager: Optional energy manager
            extraction_service: Optional extraction service
            placement_service: Optional placement service
            graph_manager: Optional graph manager
        """
        super().__init__("acquisition_manager", storage_provider)
        self.energy_manager = energy_manager
        self.extraction_service = extraction_service
        self.placement_service = placement_service
        self.graph_manager = graph_manager
        
        # Track active acquisition tasks
        self.active_tasks = {}
        self.acquisition_lock = asyncio.Lock()
        
        # Initialize the knowledge sources registry
        self.knowledge_sources = {
            "web_search": self._acquire_from_web_search,
            "rss_feed": self._acquire_from_rss_feed,
            "api_service": self._acquire_from_api_service,
            "document_repository": self._acquire_from_document_repository,
        }
    
    async def _initialize(self) -> None:
        """Service-specific initialization."""
        logger.info("Initializing acquisition manager")
        
        # Lazy initialize components if not provided
        if self.energy_manager is None and self.storage is not None:
            from src.forest.energy.manager_combined import EnergyManager
            self.energy_manager = EnergyManager(storage_provider=self.storage)
            
        if self.extraction_service is None:
            from src.forest.extraction_service import KnowledgeExtractionService
            self.extraction_service = KnowledgeExtractionService()
            
        if self.placement_service is None and self.storage is not None:
            from src.forest.placement import KnowledgePlacementService
            self.placement_service = KnowledgePlacementService(storage_provider=self.storage)
            
        if self.graph_manager is None and self.storage is not None:
            from src.forest.graph import KnowledgeGraphManager
            self.graph_manager = KnowledgeGraphManager(storage_provider=self.storage)
    
    async def _cleanup(self) -> None:
        """Service-specific cleanup."""
        logger.info("Cleaning up acquisition manager")
        
        # Cancel any active acquisition tasks
        for task_id, task in self.active_tasks.items():
            if not task.done():
                task.cancel()
                
        self.active_tasks.clear()
    
    @track_energy(15.0)
    @handle_errors(AcquisitionError)
    @log_operation("identify_knowledge_gaps")
    async def identify_knowledge_gaps(self, user_id: str) -> List[KnowledgeGap]:
        """Identify knowledge gaps that require active acquisition.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of identified knowledge gaps
            
        Raises:
            AcquisitionError: If gap identification fails
        """
        try:
            gaps = []
            
            # 1. Get reflection system identified gaps
            reflection_gaps = await self._get_reflection_gaps(user_id)
            gaps.extend(reflection_gaps)
            
            # 2. Identify coverage gaps (topics with too few nodes)
            coverage_gaps = await self._identify_coverage_gaps(user_id)
            gaps.extend(coverage_gaps)
            
            # 3. Identify depth gaps (topics that lack detailed knowledge)
            depth_gaps = await self._identify_depth_gaps(user_id)
            gaps.extend(depth_gaps)
            
            # 4. Identify timeliness gaps (outdated knowledge)
            timeliness_gaps = await self._identify_timeliness_gaps(user_id)
            gaps.extend(timeliness_gaps)
            
            # 5. Store the identified gaps
            for gap in gaps:
                # Only store new gaps or ones that don't have active tasks
                existing_gap = await self.storage.find_one(
                    "knowledge_gaps",
                    {
                        "user_id": user_id,
                        "description": gap.description,
                        "status": {"$ne": "closed"}
                    }
                )
                
                if not existing_gap:
                    gap_dict = {
                        "user_id": user_id,
                        **gap.model_dump(),
                        "identified_at": datetime.utcnow(),
                        "status": "open"
                    }
                    await self.storage.save_document("knowledge_gaps", gap_dict)
            
            return gaps
            
        except Exception as e:
            logger.error(f"Failed to identify knowledge gaps: {str(e)}")
            raise AcquisitionError(f"Failed to identify knowledge gaps: {str(e)}")
    
    @track_energy(20.0)
    @handle_errors(AcquisitionError)
    @log_operation("acquire_knowledge")
    async def acquire_knowledge(self, user_id: str, gap_id: Optional[str] = None) -> Dict[str, Any]:
        """Actively acquire knowledge to fill identified gaps.
        
        Args:
            user_id: The user ID
            gap_id: Optional specific gap ID to address
            
        Returns:
            Results of the acquisition process
            
        Raises:
            AcquisitionError: If acquisition fails
        """
        async with self.acquisition_lock:
            try:
                result = {
                    "gaps_addressed": 0,
                    "knowledge_acquired": 0,
                    "nodes_created": 0,
                    "edges_created": 0
                }
                
                # Get gaps to address
                gaps_to_address = []
                
                if gap_id:
                    # Get specific gap
                    gap_doc = await self.storage.get_document("knowledge_gaps", gap_id)
                    if gap_doc and gap_doc.get("user_id") == user_id and gap_doc.get("status") != "closed":
                        gaps_to_address.append(gap_doc)
                else:
                    # Get open gaps, prioritized by severity
                    gaps_to_address = await self.storage.find_documents(
                        "knowledge_gaps",
                        {
                            "user_id": user_id,
                            "status": "open"
                        },
                        sort=[("severity", -1)],
                        limit=5  # Limit to addressing 5 gaps at a time
                    )
                
                if not gaps_to_address:
                    return result
                
                # Process each gap
                for gap in gaps_to_address:
                    # Mark gap as being addressed
                    await self.storage.update_document(
                        "knowledge_gaps",
                        gap["_id"],
                        {"status": "addressing", "updated_at": datetime.utcnow()}
                    )
                    
                    # Determine acquisition source based on gap type
                    gap_type = gap.get("type", "coverage")
                    knowledge_acquired = await self._acquire_for_gap(user_id, gap)
                    
                    if knowledge_acquired:
                        # Mark gap as closed if successful
                        await self.storage.update_document(
                            "knowledge_gaps",
                            gap["_id"],
                            {"status": "closed", "updated_at": datetime.utcnow()}
                        )
                        
                        result["gaps_addressed"] += 1
                        result["knowledge_acquired"] += len(knowledge_acquired)
                        
                        # Process acquired knowledge
                        for item in knowledge_acquired:
                            processing_result = await self._process_acquired_knowledge(user_id, item, gap)
                            
                            result["nodes_created"] += len(processing_result.get("nodes_created", []))
                            result["edges_created"] += len(processing_result.get("edges_created", []))
                    else:
                        # Mark gap as open but with failed attempt
                        await self.storage.update_document(
                            "knowledge_gaps",
                            gap["_id"],
                            {
                                "status": "open", 
                                "updated_at": datetime.utcnow(),
                                "acquisition_attempts": gap.get("acquisition_attempts", 0) + 1
                            }
                        )
                
                return result
                
            except Exception as e:
                logger.error(f"Failed to acquire knowledge: {str(e)}")
                raise AcquisitionError(f"Failed to acquire knowledge: {str(e)}")
    
    @track_energy(30.0)
    @handle_errors(AcquisitionError)
    @log_operation("run_acquisition_cycle")
    async def run_acquisition_cycle(self, user_id: str) -> Dict[str, Any]:
        """Run a complete acquisition cycle.
        
        Args:
            user_id: The user ID
            
        Returns:
            Comprehensive acquisition results
            
        Raises:
            AcquisitionError: If cycle fails
        """
        try:
            # Check energy availability
            if self.energy_manager:
                energy_available = await self.energy_manager.get_energy_available(
                    user_id=user_id, 
                    component="acquisition_manager"
                )
                
                if energy_available < 50.0:  # Minimum energy required for acquisition cycle
                    return {
                        "success": False,
                        "message": "Insufficient energy for acquisition cycle",
                        "timestamp": datetime.utcnow().isoformat()
                    }
            
            result = {
                "gaps_identified": 0,
                "gaps_addressed": 0,
                "knowledge_acquired": 0,
                "nodes_created": 0,
                "edges_created": 0,
                "timestamp": datetime.utcnow().isoformat(),
                "success": False
            }
            
            # Identify knowledge gaps
            gaps = await self.identify_knowledge_gaps(user_id)
            result["gaps_identified"] = len(gaps)
            
            if gaps:
                # Acquire knowledge to fill gaps
                acquisition_result = await self.acquire_knowledge(user_id)
                
                result["gaps_addressed"] = acquisition_result["gaps_addressed"]
                result["knowledge_acquired"] = acquisition_result["knowledge_acquired"]
                result["nodes_created"] = acquisition_result["nodes_created"]
                result["edges_created"] = acquisition_result["edges_created"]
            
            # Record acquisition cycle history
            await self._record_acquisition_cycle(user_id, result)
            
            result["success"] = True
            return result
            
        except Exception as e:
            logger.error(f"Failed to run acquisition cycle: {str(e)}")
            raise AcquisitionError(f"Failed to run acquisition cycle: {str(e)}")
    
    async def schedule_acquisition_task(self, user_id: str, gap_id: str) -> str:
        """Schedule an acquisition task for a specific gap.
        
        Args:
            user_id: User ID
            gap_id: Knowledge gap ID
            
        Returns:
            Task ID
        """
        # Generate a task ID
        task_id = f"acquisition_{datetime.utcnow().timestamp()}_{gap_id}"
        
        # Create and start the task
        task = asyncio.create_task(self._run_acquisition_task(user_id, gap_id, task_id))
        self.active_tasks[task_id] = task
        
        # Setup callback to remove from active tasks when done
        task.add_done_callback(lambda t: self.active_tasks.pop(task_id, None))
        
        return task_id
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of an acquisition task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task status information
        """
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            
            if task.done():
                try:
                    result = task.result()
                    return {
                        "status": "completed",
                        "result": result
                    }
                except Exception as e:
                    return {
                        "status": "failed",
                        "error": str(e)
                    }
            else:
                return {
                    "status": "running"
                }
        else:
            # Check database for completed task
            task_record = await self.storage.find_one(
                "acquisition_tasks",
                {"task_id": task_id}
            )
            
            if task_record:
                return {
                    "status": task_record.get("status", "unknown"),
                    "result": task_record.get("result", {})
                }
            
            return {
                "status": "not_found"
            }
    
    async def get_knowledge_sources(self) -> List[Dict[str, Any]]:
        """Get available knowledge sources.
        
        Returns:
            List of knowledge sources with their capabilities
        """
        sources = []
        
        for source_id, func in self.knowledge_sources.items():
            source_info = {
                "id": source_id,
                "name": source_id.replace("_", " ").title(),
                "enabled": True
            }
            
            if source_id == "web_search":
                source_info["description"] = "Search the web for information"
                source_info["capabilities"] = ["text", "images", "structured_data"]
            elif source_id == "rss_feed":
                source_info["description"] = "Monitor RSS feeds for new information"
                source_info["capabilities"] = ["text", "updates"]
            elif source_id == "api_service":
                source_info["description"] = "Query external APIs for specialized information"
                source_info["capabilities"] = ["structured_data", "domain_specific"]
            elif source_id == "document_repository":
                source_info["description"] = "Access document repositories for comprehensive information"
                source_info["capabilities"] = ["text", "documents", "archives"]
            
            sources.append(source_info)
        
        return sources
    
    async def register_knowledge_source(self, source_id: str, acquisition_func: callable) -> bool:
        """Register a new knowledge source.
        
        Args:
            source_id: Source identifier
            acquisition_func: Acquisition function
            
        Returns:
            True if registration successful
        """
        if source_id in self.knowledge_sources:
            return False
            
        self.knowledge_sources[source_id] = acquisition_func
        return True
    
    async def _get_reflection_gaps(self, user_id: str) -> List[KnowledgeGap]:
        """Get knowledge gaps identified by the reflection system.
        
        Args:
            user_id: User ID
            
        Returns:
            List of knowledge gaps
        """
        # Get recent reflection cycles
        recent_cycles = await self.storage.find_documents(
            "reflection_cycles",
            {
                "user_id": user_id,
                "status": "completed",
                "end_time": {"$gte": datetime.utcnow() - timedelta(days=7)}
            },
            sort=[("end_time", -1)],
            limit=5
        )
        
        # Extract gaps from reflection cycles
        gaps = []
        seen_descriptions = set()
        
        for cycle in recent_cycles:
            cycle_gaps = cycle.get("identified_gaps", [])
            
            for gap in cycle_gaps:
                # Convert to KnowledgeGap model
                description = gap.get("description", "")
                
                # Skip duplicates
                if description in seen_descriptions:
                    continue
                    
                seen_descriptions.add(description)
                
                # Create gap object
                gaps.append(KnowledgeGap(
                    id=gap.get("id", str(uuid.uuid4())),
                    type=gap.get("type", "coverage"),
                    description=description,
                    topic_id=gap.get("topic_id"),
                    related_node_ids=gap.get("related_node_ids", []),
                    severity=gap.get("severity", 0.5),
                    identified_at=gap.get("identified_at", datetime.utcnow()),
                    status="open"
                ))
        
        return gaps
    
    async def _identify_coverage_gaps(self, user_id: str) -> List[KnowledgeGap]:
        """Identify topics with insufficient coverage.
        
        Args:
            user_id: User ID
            
        Returns:
            List of coverage gaps
        """
        # Get topic distribution
        nodes = await self.storage.find_documents(
            "nodes",
            {"user_id": user_id, "status": "active"}
        )
        
        # Group by topic
        topic_counts = {}
        for node in nodes:
            topic_id = node.get("topic_cluster_id")
            if topic_id:
                if topic_id not in topic_counts:
                    topic_counts[topic_id] = 0
                topic_counts[topic_id] += 1
        
        # Identify topics with low node counts
        gaps = []
        min_topic_size = 5  # Minimum expected nodes per topic
        
        for topic_id, count in topic_counts.items():
            if count < min_topic_size:
                # Get topic name
                topic_node = await self.storage.get_document("nodes", topic_id)
                topic_name = topic_node.get("label", f"Topic {topic_id[:8]}") if topic_node else f"Topic {topic_id[:8]}"
                
                gaps.append(KnowledgeGap(
                    id=str(uuid.uuid4()),
                    type=GapType.COVERAGE,
                    description=f"Insufficient knowledge in topic: {topic_name}",
                    topic_id=topic_id,
                    related_node_ids=[topic_id],
                    severity=0.7 if count < 3 else 0.5,  # Higher severity for very small topics
                    status="open"
                ))
        
        return gaps
    
    async def _identify_depth_gaps(self, user_id: str) -> List[KnowledgeGap]:
        """Identify topics that lack detailed knowledge.
        
        Args:
            user_id: User ID
            
        Returns:
            List of depth gaps
        """
        # Get abstraction levels distribution per topic
        nodes = await self.storage.find_documents(
            "nodes",
            {"user_id": user_id, "status": "active"}
        )
        
        # Group by topic and abstraction level
        topic_abstraction = {}
        for node in nodes:
            topic_id = node.get("topic_cluster_id")
            if not topic_id:
                continue
                
            abstraction_level = node.get("abstraction_level", 2)  # Default to CONCEPT (2)
            
            if topic_id not in topic_abstraction:
                topic_abstraction[topic_id] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                
            topic_abstraction[topic_id][abstraction_level] += 1
        
        # Identify topics with poor abstraction distribution (lack of detailed knowledge)
        gaps = []
        
        for topic_id, levels in topic_abstraction.items():
            total_nodes = sum(levels.values())
            
            if total_nodes < 5:
                continue  # Skip small topics
                
            # Check if most nodes are high-level abstractions with few concrete instances
            high_level_ratio = (levels[3] + levels[4] + levels[5]) / total_nodes if total_nodes > 0 else 0
            low_level_ratio = levels[1] / total_nodes if total_nodes > 0 else 0
            
            if high_level_ratio > 0.7 and low_level_ratio < 0.2:
                # Topic has mostly abstract concepts without concrete examples
                topic_node = await self.storage.get_document("nodes", topic_id)
                topic_name = topic_node.get("label", f"Topic {topic_id[:8]}") if topic_node else f"Topic {topic_id[:8]}"
                
                gaps.append(KnowledgeGap(
                    id=str(uuid.uuid4()),
                    type=GapType.DEPTH,
                    description=f"Need more concrete examples in topic: {topic_name}",
                    topic_id=topic_id,
                    related_node_ids=[topic_id],
                    severity=0.6,
                    status="open"
                ))
        
        return gaps
    
    async def _identify_timeliness_gaps(self, user_id: str) -> List[KnowledgeGap]:
        """Identify outdated knowledge.
        
        Args:
            user_id: User ID
            
        Returns:
            List of timeliness gaps
        """
        # Get timeliness-sensitive topics
        # For this example, we'll focus on technology and current events
        timeliness_keywords = ["technology", "news", "event", "current", "recent", 
                             "latest", "update", "tech", "development"]
        
        timeliness_nodes = []
        
        for keyword in timeliness_keywords:
            # Search for nodes related to timeliness-sensitive topics
            matches = await self.storage.find_documents(
                "nodes",
                {
                    "user_id": user_id,
                    "status": "active",
                    "$or": [
                        {"label": {"$regex": keyword, "$options": "i"}},
                        {"summary": {"$regex": keyword, "$options": "i"}}
                    ]
                }
            )
            
            timeliness_nodes.extend(matches)
        
        # Find outdated nodes (created more than 90 days ago)
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        outdated_nodes = [
            node for node in timeliness_nodes
            if node.get("created_at", datetime.utcnow()) < cutoff_date
        ]
        
        # Group by topic
        topic_outdated = {}
        for node in outdated_nodes:
            topic_id = node.get("topic_cluster_id")
            if topic_id:
                if topic_id not in topic_outdated:
                    topic_outdated[topic_id] = []
                topic_outdated[topic_id].append(node)
        
        # Create gaps for topics with many outdated nodes
        gaps = []
        
        for topic_id, nodes in topic_outdated.items():
            if len(nodes) >= 3:  # At least 3 outdated nodes
                topic_node = await self.storage.get_document("nodes", topic_id)
                topic_name = topic_node.get("label", f"Topic {topic_id[:8]}") if topic_node else f"Topic {topic_id[:8]}"
                
                # Get the oldest nodes for reference
                oldest_nodes = sorted(nodes, key=lambda n: n.get("created_at", datetime.utcnow()))[:3]
                oldest_node_ids = [node["_id"] for node in oldest_nodes]
                
                gaps.append(KnowledgeGap(
                    id=str(uuid.uuid4()),
                    type=GapType.TIMELINESS,
                    description=f"Outdated knowledge in topic: {topic_name}",
                    topic_id=topic_id,
                    related_node_ids=oldest_node_ids,
                    severity=0.7,  # Fairly high severity
                    status="open"
                ))
        
        return gaps
    
    async def _acquire_for_gap(self, user_id: str, gap: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Acquire knowledge to address a specific gap.
        
        Args:
            user_id: User ID
            gap: Knowledge gap to address
            
        Returns:
            List of acquired knowledge items
        """
        gap_type = gap.get("type")
        
        if gap_type == "coverage":
            # For coverage gaps, use web search as the primary source
            return await self._acquire_from_web_search(user_id, gap)
            
        elif gap_type == "depth":
            # For depth gaps, use a combination of web search and document repositories
            web_results = await self._acquire_from_web_search(user_id, gap)
            doc_results = await self._acquire_from_document_repository(user_id, gap)
            
            return web_results + doc_results
            
        elif gap_type == "timeliness":
            # For timeliness gaps, use a combination of web search and RSS feeds
            web_results = await self._acquire_from_web_search(user_id, gap)
            rss_results = await self._acquire_from_rss_feed(user_id, gap)
            
            return web_results + rss_results
            
        elif gap_type == "connectivity":
            # For connectivity gaps, primarily use API services
            return await self._acquire_from_api_service(user_id, gap)
            
        else:
            # Default to web search for unknown gap types
            return await self._acquire_from_web_search(user_id, gap)
    
    async def _acquire_from_web_search(self, user_id: str, gap: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Acquire knowledge from web search.
        
        Args:
            user_id: User ID
            gap: Knowledge gap to address
            
        Returns:
            List of acquired knowledge items
        """
        try:
            # Generate search queries from the gap
            search_queries = await self._generate_search_queries(gap)
            
            acquired_items = []
            
            for query in search_queries[:3]:  # Limit to top 3 queries
                # Use web search API (e.g., Firecrawl integration)
                try:
                    from src.ai.firecrawl import FirecrawlProvider
                    firecrawl = FirecrawlProvider()
                    
                    search_results = await firecrawl.search(query)
                    
                    if search_results and "results" in search_results:
                        for result in search_results["results"][:5]:  # Process top 5 results
                            url = result.get("url")
                            title = result.get("title", "")
                            snippet = result.get("snippet", "")
                            
                            # Check if this URL has been processed recently
                            existing = await self.storage.find_one(
                                "acquisition_sources",
                                {
                                    "user_id": user_id,
                                    "source_type": "web",
                                    "url": url,
                                    "timestamp": {"$gte": datetime.utcnow() - timedelta(days=7)}
                                }
                            )
                            
                            if existing:
                                continue  # Skip recently processed URLs
                            
                            # Fetch the content
                            content = await firecrawl.get_page_content(url)
                            
                            if content:
                                # Record the source
                                source_record = {
                                    "user_id": user_id,
                                    "source_type": "web",
                                    "url": url,
                                    "title": title,
                                    "query": query,
                                    "gap_id": gap.get("_id", ""),
                                    "timestamp": datetime.utcnow()
                                }
                                
                                await self.storage.save_document("acquisition_sources", source_record)
                                
                                # Add to acquired items
                                acquired_items.append({
                                    "content": content,
                                    "source": url,
                                    "title": title,
                                    "snippet": snippet,
                                    "query": query,
                                    "gap_id": gap.get("_id", ""),
                                    "type": gap.get("type", "coverage"),
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                except ImportError:
                    logger.warning("Firecrawl integration not available, using fallback method")
                    # Fallback method with simulated results for testing
                    acquired_items.append({
                        "content": f"Simulated web content about {query}. This is a fallback method when Firecrawl is not available.",
                        "source": f"https://example.com/search?q={query}",
                        "title": f"Information about {query}",
                        "snippet": f"This is a simulated search result about {query}...",
                        "query": query,
                        "gap_id": gap.get("_id", ""),
                        "type": gap.get("type", "coverage"),
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            return acquired_items
            
        except Exception as e:
            logger.error(f"Error acquiring from web search: {str(e)}")
            return []
    
    async def _acquire_from_rss_feed(self, user_id: str, gap: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Acquire knowledge from RSS feeds.
        
        Args:
            user_id: User ID
            gap: Knowledge gap to address
            
        Returns:
            List of acquired knowledge items
        """
        try:
            # Determine relevant RSS feeds for this gap
            feeds = await self._get_relevant_feeds(user_id, gap)
            
            acquired_items = []
            
            for feed_url in feeds:
                try:
                    # Fetch RSS feed content
                    import feedparser
                    import aiohttp
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(feed_url) as response:
                            content = await response.text()
                            feed_data = feedparser.parse(content)
                            
                            for entry in feed_data.entries[:5]:  # Limit to 5 entries per feed
                                title = entry.get('title', '')
                                link = entry.get('link', '')
                                summary = entry.get('summary', '')
                                published = entry.get('published', '')
                                
                                # Check if this entry has been processed recently
                                existing = await self.storage.find_one(
                                    "acquisition_sources",
                                    {
                                        "user_id": user_id,
                                        "source_type": "rss",
                                        "url": link
                                    }
                                )
                                
                                if existing:
                                    continue  # Skip already processed entries
                                
                                # Record the source
                                source_record = {
                                    "user_id": user_id,
                                    "source_type": "rss",
                                    "url": link,
                                    "title": title,
                                    "feed_url": feed_url,
                                    "gap_id": gap.get("_id", ""),
                                    "timestamp": datetime.utcnow()
                                }
                                
                                await self.storage.save_document("acquisition_sources", source_record)
                                
                                # Add to acquired items
                                acquired_items.append({
                                    "content": summary,
                                    "source": link,
                                    "title": title,
                                    "snippet": summary[:200] + "...",
                                    "feed_url": feed_url,
                                    "published": published,
                                    "gap_id": gap.get("_id", ""),
                                    "type": gap.get("type", "timeliness"),
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                except (ImportError, Exception) as e:
                    logger.warning(f"Error processing feed {feed_url}: {str(e)}")
                    # Provide fallback simulated data for testing
                    acquired_items.append({
                        "content": f"Simulated RSS content from {feed_url}",
                        "source": feed_url,
                        "title": f"News from {feed_url.split('//')[-1].split('/')[0]}",
                        "snippet": "This is a simulated RSS feed entry...",
                        "feed_url": feed_url,
                        "published": datetime.utcnow().isoformat(),
                        "gap_id": gap.get("_id", ""),
                        "type": gap.get("type", "timeliness"),
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            return acquired_items
            
        except Exception as e:
            logger.error(f"Error acquiring from RSS feeds: {str(e)}")
            return []
    
    async def _acquire_from_api_service(self, user_id: str, gap: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Acquire knowledge from API services.
        
        Args:
            user_id: User ID
            gap: Knowledge gap to address
            
        Returns:
            List of acquired knowledge items
        """
        try:
            # Determine relevant API endpoints for this gap
            api_endpoints = await self._get_relevant_apis(user_id, gap)
            
            acquired_items = []
            
            for endpoint in api_endpoints:
                try:
                    # Call API endpoint
                    import aiohttp
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(endpoint["url"], params=endpoint.get("params", {})) as response:
                            if response.status == 200:
                                data = await response.text()
                                
                                # Record the source
                                source_record = {
                                    "user_id": user_id,
                                    "source_type": "api",
                                    "url": endpoint["url"],
                                    "api_name": endpoint.get("name", "Unknown API"),
                                    "gap_id": gap.get("_id", ""),
                                    "timestamp": datetime.utcnow()
                                }
                                
                                await self.storage.save_document("acquisition_sources", source_record)
                                
                                # Add to acquired items
                                acquired_items.append({
                                    "content": data,
                                    "source": endpoint["url"],
                                    "title": f"Data from {endpoint.get('name', 'API')}",
                                    "api_name": endpoint.get("name", "Unknown API"),
                                    "gap_id": gap.get("_id", ""),
                                    "type": gap.get("type", "connectivity"),
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                except Exception as e:
                    logger.warning(f"Error calling API endpoint {endpoint['url']}: {str(e)}")
                    # Provide fallback simulated data for testing
                    acquired_items.append({
                        "content": f"Simulated API response from {endpoint.get('name', 'API')}",
                        "source": endpoint.get("url", "https://api.example.com"),
                        "title": f"Data from {endpoint.get('name', 'API')}",
                        "api_name": endpoint.get("name", "Unknown API"),
                        "gap_id": gap.get("_id", ""),
                        "type": gap.get("type", "connectivity"),
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            return acquired_items
            
        except Exception as e:
            logger.error(f"Error acquiring from API services: {str(e)}")
            return []
    
    async def _acquire_from_document_repository(self, user_id: str, gap: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Acquire knowledge from document repositories.
        
        Args:
            user_id: User ID
            gap: Knowledge gap to address
            
        Returns:
            List of acquired knowledge items
        """
        try:
            # Generate search queries for document repositories
            search_queries = await self._generate_search_queries(gap)
            
            acquired_items = []
            
            # Simulated document repository search
            # In a real implementation, this would connect to document databases
            for query in search_queries[:2]:  # Limit to top 2 queries
                # Check for access to document repositories
                try:
                    from src.storage.document_repository import DocumentRepository
                    document_repo = DocumentRepository()
                    
                    documents = await document_repo.search(query)
                    
                    for doc in documents[:3]:  # Limit to 3 documents per query
                        # Record the source
                        source_record = {
                            "user_id": user_id,
                            "source_type": "document",
                            "document_id": doc.get("id"),
                            "title": doc.get("title"),
                            "repository": doc.get("repository"),
                            "query": query,
                            "gap_id": gap.get("_id", ""),
                            "timestamp": datetime.utcnow()
                        }
                        
                        await self.storage.save_document("acquisition_sources", source_record)
                        
                        # Add to acquired items
                        acquired_items.append({
                            "content": doc.get("content"),
                            "source": f"document://{doc.get('repository')}/{doc.get('id')}",
                            "title": doc.get("title"),
                            "document_id": doc.get("id"),
                            "repository": doc.get("repository"),
                            "query": query,
                            "gap_id": gap.get("_id", ""),
                            "type": gap.get("type", "depth"),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                except ImportError:
                    # Fallback with simulated document repository
                    for i in range(2):  # Simulate finding 2 documents
                        doc_id = f"doc_{i}_{datetime.utcnow().timestamp()}"
                        
                        acquired_items.append({
                            "content": f"Simulated document content about {query}. This document contains detailed information that would fill knowledge gaps.",
                            "source": f"document://simulated/{doc_id}",
                            "title": f"Document about {query}",
                            "document_id": doc_id,
                            "repository": "simulated",
                            "query": query,
                            "gap_id": gap.get("_id", ""),
                            "type": gap.get("type", "depth"),
                            "timestamp": datetime.utcnow().isoformat()
                        })
            
            return acquired_items
            
        except Exception as e:
            logger.error(f"Error acquiring from document repository: {str(e)}")
            return []
    
    async def _process_acquired_knowledge(self, user_id: str, knowledge_item: Dict[str, Any], gap: Dict[str, Any]) -> Dict[str, Any]:
        """Process acquired knowledge and integrate it into the knowledge forest.
        
        Args:
            user_id: User ID
            knowledge_item: Acquired knowledge item
            gap: Knowledge gap being addressed
            
        Returns:
            Processing results
        """
        try:
            # Extract knowledge from the acquired content
            content = knowledge_item.get("content", "")
            source = knowledge_item.get("source", "")
            title = knowledge_item.get("title", "")
            
            # Create a unique conversation and message ID for this acquisition
            conversation_id = f"acquisition_{datetime.utcnow().timestamp()}"
            message_id = str(uuid.uuid4())
            
            # Prepare metadata
            metadata = {
                "source": source,
                "title": title,
                "gap_id": gap.get("_id", ""),
                "gap_type": gap.get("type", "coverage"),
                "acquisition_timestamp": datetime.utcnow().isoformat(),
                "topic_id": gap.get("topic_id")
            }
            
            # Extract knowledge and place it in the forest
            extraction_result = await self.extraction_service.extract_knowledge(
                text=content,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                metadata=metadata
            )
            
            # Build the decision request
            placement_request = {
                "extraction_result": extraction_result,
                "user_id": user_id,
                "topic_target": gap.get("topic_id"),  # Target specific topic if available
                "metadata": metadata
            }
            
            # Get placement decision
            placement_decision = await self.placement_service.decide_placement(placement_request)
            
            # Apply the decision to update the graph
            update_result = await self.graph_manager.update_graph(
                user_id=user_id,
                extraction_result=extraction_result,
                placement_decision=placement_decision
            )
            
            # Return the update result
            return {
                "nodes_created": update_result.get("nodes_created", []),
                "edges_created": update_result.get("edges_created", []),
                "source": source,
                "title": title,
                "gap_id": gap.get("_id", "")
            }
            
        except Exception as e:
            logger.error(f"Error processing acquired knowledge: {str(e)}")
            return {
                "nodes_created": [],
                "edges_created": [],
                "error": str(e)
            }
    
    async def _generate_search_queries(self, gap: Dict[str, Any]) -> List[str]:
        """Generate search queries from a knowledge gap.
        
        Args:
            gap: Knowledge gap
            
        Returns:
            List of search queries
        """
        description = gap.get("description", "")
        gap_type = gap.get("type", "coverage")
        
        # Extract key terms from the description
        description = re.sub(r"^(Insufficient knowledge in topic:|Need more concrete examples in topic:|Outdated knowledge in topic:)\s*", "", description)
        
        # Get related node content for context
        related_node_ids = gap.get("related_node_ids", [])
        related_nodes = []
        
        for node_id in related_node_ids:
            node = await self.storage.get_document("nodes", node_id)
            if node:
                related_nodes.append(node)
        
        # Extract key terms from related nodes
        key_terms = set()
        for node in related_nodes:
            label = node.get("label", "")
            summary = node.get("summary", "")
            
            # Add main node label
            key_terms.add(label)
            
            # Extract key terms from summary
            if summary:
                # Simple keyword extraction (in a real system, use NLP techniques)
                words = re.findall(r'\b[A-Za-z][A-Za-z-]{2,}\b', summary)
                for word in words:
                    if len(word) > 3 and word.lower() not in ["this", "that", "with", "from", "have", "were", "their", "about"]:
                        key_terms.add(word)
        
        # Generate queries based on gap type
        queries = []
        
        if gap_type == "coverage":
            # General coverage queries
            queries.append(f"overview of {description}")
            queries.append(f"introduction to {description}")
            queries.append(f"what is {description}")
            
            # Add key term combinations
            if key_terms:
                terms_list = list(key_terms)
                if len(terms_list) >= 2:
                    queries.append(f"{terms_list[0]} {terms_list[1]} overview")
                if len(terms_list) >= 3:
                    queries.append(f"{terms_list[0]} {terms_list[1]} {terms_list[2]}")
        
        elif gap_type == "depth":
            # Detailed knowledge queries
            queries.append(f"detailed explanation of {description}")
            queries.append(f"examples of {description}")
            queries.append(f"case studies {description}")
            
            # Add key term combinations
            if key_terms:
                terms_list = list(key_terms)
                if len(terms_list) >= 1:
                    queries.append(f"detailed examples of {terms_list[0]}")
                if len(terms_list) >= 2:
                    queries.append(f"{terms_list[0]} {terms_list[1]} case study")
        
        elif gap_type == "timeliness":
            # Recent information queries
            queries.append(f"latest {description}")
            queries.append(f"recent developments in {description}")
            queries.append(f"{description} news")
            queries.append(f"{description} update 2023")  # Include current year
            
            # Add key term combinations
            if key_terms:
                terms_list = list(key_terms)
                if len(terms_list) >= 1:
                    queries.append(f"latest {terms_list[0]} developments")
                if len(terms_list) >= 2:
                    queries.append(f"recent {terms_list[0]} {terms_list[1]}")
        
        elif gap_type == "connectivity":
            # Relationship queries
            queries.append(f"relationship between {description}")
            queries.append(f"how does {description} connect to related concepts")
            queries.append(f"{description} interdisciplinary connections")
            
            # Add key term combinations
            if key_terms:
                terms_list = list(key_terms)
                if len(terms_list) >= 2:
                    queries.append(f"connection between {terms_list[0]} and {terms_list[1]}")
                if len(terms_list) >= 3:
                    queries.append(f"how {terms_list[0]} relates to {terms_list[1]} and {terms_list[2]}")
        
        # Ensure we have at least 3 queries
        if len(queries) < 3:
            queries.append(f"{description} explained")
            queries.append(f"comprehensive guide to {description}")
            queries.append(f"{description} tutorial")
        
        return queries
    
    async def _get_relevant_feeds(self, user_id: str, gap: Dict[str, Any]) -> List[str]:
        """Get relevant RSS feeds for a knowledge gap.
        
        Args:
            user_id: User ID
            gap: Knowledge gap
            
        Returns:
            List of RSS feed URLs
        """
        # This is a simplified implementation with predefined feeds
        # In a real system, this would dynamically determine relevant feeds
        
        # Get topic from gap
        topic_id = gap.get("topic_id")
        topic_node = None
        
        if topic_id:
            topic_node = await self.storage.get_document("nodes", topic_id)
        
        # Default feeds
        default_feeds = [
            "https://news.google.com/rss",
            "https://feeds.bbci.co.uk/news/rss.xml"
        ]
        
        # Topic-specific feeds
        topic_feeds = {
            "technology": [
                "https://feeds.arstechnica.com/arstechnica/index",
                "https://www.wired.com/feed/rss",
                "https://www.techcrunch.com/feed/"
            ],
            "science": [
                "https://www.sciencedaily.com/rss/all.xml",
                "https://www.nature.com/nature.rss",
                "https://www.science.org/rss/news_current.xml"
            ],
            "business": [
                "https://www.forbes.com/business/feed/",
                "https://feeds.businessinsider.com/rss",
                "https://www.economist.com/business/rss.xml"
            ]
        }
        
        # Determine relevant feeds based on topic
        if topic_node:
            topic_label = topic_node.get("label", "").lower()
            
            for category, feeds in topic_feeds.items():
                if category in topic_label or any(keyword in topic_label for keyword in [category, f"{category}s"]):
                    return feeds
        
        # Return default feeds if no specific category matched
        return default_feeds
    
    async def _get_relevant_apis(self, user_id: str, gap: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get relevant API endpoints for a knowledge gap.
        
        Args:
            user_id: User ID
            gap: Knowledge gap
            
        Returns:
            List of API endpoint configurations
        """
        # This is a simplified implementation with predefined APIs
        # In a real system, this would dynamically determine relevant APIs
        
        # Get topic from gap
        topic_id = gap.get("topic_id")
        topic_node = None
        
        if topic_id:
            topic_node = await self.storage.get_document("nodes", topic_id)
        
        # Default APIs
        default_apis = [
            {
                "name": "Open Data API",
                "url": "https://api.publicapis.org/entries",
                "params": {"category": "science"}
            }
        ]
        
        # Topic-specific APIs
        topic_apis = {
            "weather": [
                {
                    "name": "OpenWeatherMap",
                    "url": "https://api.openweathermap.org/data/2.5/weather",
                    "params": {"q": "London", "appid": "demo"}
                }
            ],
            "finance": [
                {
                    "name": "Financial Data API",
                    "url": "https://api.exchangerate.host/latest",
                    "params": {}
                }
            ],
            "covid": [
                {
                    "name": "COVID-19 Data",
                    "url": "https://api.covidtracking.com/v1/us/current.json",
                    "params": {}
                }
            ]
        }
        
        # Determine relevant APIs based on topic
        if topic_node:
            topic_label = topic_node.get("label", "").lower()
            
            for category, apis in topic_apis.items():
                if category in topic_label:
                    return apis
        
        # Return default APIs if no specific category matched
        return default_apis
    
    async def _run_acquisition_task(self, user_id: str, gap_id: str, task_id: str) -> Dict[str, Any]:
        """Run an acquisition task for a specific gap.
        
        Args:
            user_id: User ID
            gap_id: Knowledge gap ID
            task_id: Task ID
            
        Returns:
            Task results
        """
        try:
            # Record task start
            task_record = {
                "user_id": user_id,
                "gap_id": gap_id,
                "task_id": task_id,
                "status": "running",
                "start_time": datetime.utcnow()
            }
            
            await self.storage.save_document("acquisition_tasks", task_record)
            
            # Acquire knowledge for this gap
            result = await self.acquire_knowledge(user_id, gap_id)
            
            # Update task record
            await self.storage.update_document(
                "acquisition_tasks",
                {"task_id": task_id},
                {
                    "status": "completed",
                    "end_time": datetime.utcnow(),
                    "result": result
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error running acquisition task: {str(e)}")
            
            # Update task record with error
            await self.storage.update_document(
                "acquisition_tasks",
                {"task_id": task_id},
                {
                    "status": "failed",
                    "end_time": datetime.utcnow(),
                    "error": str(e)
                }
            )
            
            return {
                "error": str(e),
                "status": "failed"
            }
    
    async def _record_acquisition_cycle(self, user_id: str, results: Dict[str, Any]) -> bool:
        """Record acquisition cycle for historical tracking.
        
        Args:
            user_id: The user ID
            results: Acquisition cycle results
            
        Returns:
            True if recording succeeded
        """
        try:
            # Create cycle record
            record = {
                "user_id": user_id,
                "timestamp": datetime.utcnow(),
                **results
            }
            
            # Save to database
            await self.storage.save_document("acquisition_cycles", record)
            return True
            
        except Exception as e:
            logger.error(f"Failed to record acquisition cycle: {str(e)}")
            return False