"""Perception system for active knowledge acquisition.

This module provides a system for perceiving external information sources
and trigger knowledge acquisition when relevant new information is detected.
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Set
from datetime import datetime, timedelta
import json
import uuid
import re

from common.base_service import BaseService
from common.decorators import track_energy, handle_errors, log_operation
from common.exceptions import AcquisitionError
from storage.mongodb import MongoDBProvider
from forest.acquisition.manager import AcquisitionManager
from common.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class PerceptionSystem(BaseService):
    """Perception system for active knowledge acquisition.
    
    This class is responsible for monitoring external information sources
    and triggering knowledge acquisition when relevant new information is detected.
    """
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                acquisition_manager: Optional[AcquisitionManager] = None):
        """Initialize the perception system.
        
        Args:
            storage_provider: Optional storage provider
            acquisition_manager: Optional acquisition manager
        """
        super().__init__("perception_system", storage_provider)
        self.acquisition_manager = acquisition_manager
        
        # Track monitored sources
        self.monitored_sources = {}
        self.monitoring_tasks = {}
        self.source_lock = asyncio.Lock()
    
    async def _initialize(self) -> None:
        """Service-specific initialization."""
        logger.info("Initializing perception system")
        
        # Lazy initialize components if not provided
        if self.acquisition_manager is None and self.storage is not None:
            from forest.acquisition.manager import AcquisitionManager
            self.acquisition_manager = AcquisitionManager(storage_provider=self.storage)
            
        # Load monitored sources from database
        if self.storage:
            sources = await self.storage.find_documents(
                "monitored_sources",
                {"is_active": True}
            )
            
            for source in sources:
                source_id = source.get("_id")
                source_type = source.get("source_type")
                user_id = source.get("user_id")
                
                if source_id and source_type and user_id:
                    self.monitored_sources[str(source_id)] = source
    
    async def _cleanup(self) -> None:
        """Service-specific cleanup."""
        logger.info("Cleaning up perception system")
        
        # Cancel monitoring tasks
        for task_id, task in self.monitoring_tasks.items():
            if not task.done():
                task.cancel()
                
        self.monitoring_tasks.clear()
    
    @track_energy(5.0)
    @handle_errors(AcquisitionError)
    @log_operation("add_monitored_source")
    async def add_monitored_source(self, user_id: str, source_config: Dict[str, Any]) -> str:
        """Add a new source to monitor.
        
        Args:
            user_id: The user ID
            source_config: Source configuration
            
        Returns:
            Source ID
            
        Raises:
            AcquisitionError: If adding source fails
        """
        async with self.source_lock:
            try:
                source_type = source_config.get("type")
                source_url = source_config.get("url")
                
                if not source_type or not source_url:
                    raise AcquisitionError("Missing required source configuration: type and url")
                
                # Check if source is already monitored
                existing = await self.storage.find_one(
                    "monitored_sources",
                    {
                        "user_id": user_id,
                        "source_type": source_type,
                        "source_url": source_url,
                        "is_active": True
                    }
                )
                
                if existing:
                    return str(existing["_id"])
                
                # Create source record
                source_record = {
                    "user_id": user_id,
                    "source_type": source_type,
                    "source_url": source_url,
                    "keywords": source_config.get("keywords", []),
                    "topics": source_config.get("topics", []),
                    "schedule": source_config.get("schedule", "hourly"),
                    "last_check": None,
                    "is_active": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                # Save to database
                source_id = await self.storage.save_document("monitored_sources", source_record)
                source_record["_id"] = source_id
                
                # Add to monitored sources
                self.monitored_sources[str(source_id)] = source_record
                
                # Start monitoring task
                if source_type == "rss":
                    self._start_rss_monitoring(str(source_id), source_record)
                elif source_type == "api":
                    self._start_api_monitoring(str(source_id), source_record)
                elif source_type == "web":
                    self._start_web_monitoring(str(source_id), source_record)
                
                return str(source_id)
                
            except Exception as e:
                logger.error(f"Failed to add monitored source: {str(e)}")
                raise AcquisitionError(f"Failed to add monitored source: {str(e)}")
    
    @track_energy(3.0)
    @handle_errors(AcquisitionError)
    @log_operation("remove_monitored_source")
    async def remove_monitored_source(self, user_id: str, source_id: str) -> bool:
        """Remove a monitored source.
        
        Args:
            user_id: The user ID
            source_id: Source ID
            
        Returns:
            True if removed successfully
            
        Raises:
            AcquisitionError: If removing source fails
        """
        async with self.source_lock:
            try:
                # Get source record
                source = await self.storage.get_document("monitored_sources", source_id)
                
                if not source or source.get("user_id") != user_id:
                    return False
                
                # Mark as inactive
                await self.storage.update_document(
                    "monitored_sources",
                    source_id,
                    {"is_active": False, "updated_at": datetime.utcnow()}
                )
                
                # Remove from monitored sources
                if source_id in self.monitored_sources:
                    del self.monitored_sources[source_id]
                
                # Cancel monitoring task
                if source_id in self.monitoring_tasks:
                    task = self.monitoring_tasks[source_id]
                    if not task.done():
                        task.cancel()
                    del self.monitoring_tasks[source_id]
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to remove monitored source: {str(e)}")
                raise AcquisitionError(f"Failed to remove monitored source: {str(e)}")
    
    @track_energy(10.0)
    @handle_errors(AcquisitionError)
    @log_operation("check_all_sources")
    async def check_all_sources(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Check all monitored sources for new information.
        
        Args:
            user_id: Optional user ID to filter sources
            
        Returns:
            Check results
            
        Raises:
            AcquisitionError: If checking sources fails
        """
        try:
            results = {
                "sources_checked": 0,
                "new_information_found": 0,
                "acquisition_tasks_started": 0
            }
            
            # Get sources to check
            sources_to_check = []
            
            if user_id:
                # Get sources for specific user
                sources = await self.storage.find_documents(
                    "monitored_sources",
                    {"user_id": user_id, "is_active": True}
                )
                sources_to_check.extend(sources)
            else:
                # Get all active sources
                sources = await self.storage.find_documents(
                    "monitored_sources",
                    {"is_active": True}
                )
                sources_to_check.extend(sources)
            
            # Check each source
            for source in sources_to_check:
                source_id = str(source["_id"])
                source_type = source.get("source_type")
                source_url = source.get("source_url")
                source_user_id = source.get("user_id")
                
                # Update last check time
                await self.storage.update_document(
                    "monitored_sources",
                    source_id,
                    {"last_check": datetime.utcnow()}
                )
                
                results["sources_checked"] += 1
                
                # Check for new information
                new_information = await self._check_source_for_new_information(source)
                
                if new_information:
                    results["new_information_found"] += len(new_information)
                    
                    # Create knowledge gaps for the new information
                    gaps_created = await self._create_gaps_from_new_information(
                        source_user_id, new_information, source
                    )
                    
                    # Trigger acquisition for the gaps
                    for gap_id in gaps_created:
                        if self.acquisition_manager:
                            # Schedule acquisition task
                            task_id = await self.acquisition_manager.schedule_acquisition_task(
                                source_user_id, gap_id
                            )
                            
                            results["acquisition_tasks_started"] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to check all sources: {str(e)}")
            raise AcquisitionError(f"Failed to check all sources: {str(e)}")
    
    def _start_rss_monitoring(self, source_id: str, source_config: Dict[str, Any]) -> None:
        """Start RSS feed monitoring task.
        
        Args:
            source_id: Source ID
            source_config: Source configuration
        """
        async def monitor_rss_feed():
            try:
                schedule = source_config.get("schedule", "hourly")
                
                # Determine check interval
                if schedule == "hourly":
                    interval = 60 * 60  # 1 hour
                elif schedule == "daily":
                    interval = 24 * 60 * 60  # 24 hours
                elif schedule == "weekly":
                    interval = 7 * 24 * 60 * 60  # 7 days
                else:
                    interval = 60 * 60  # Default to hourly
                
                while True:
                    # Check RSS feed
                    source = await self.storage.get_document("monitored_sources", source_id)
                    
                    if not source or not source.get("is_active", False):
                        # Source was removed or deactivated
                        break
                    
                    user_id = source.get("user_id")
                    
                    try:
                        # Check for new information
                        new_information = await self._check_source_for_new_information(source)
                        
                        if new_information:
                            # Create knowledge gaps for the new information
                            gaps_created = await self._create_gaps_from_new_information(
                                user_id, new_information, source
                            )
                            
                            # Trigger acquisition for the gaps
                            for gap_id in gaps_created:
                                if self.acquisition_manager:
                                    await self.acquisition_manager.schedule_acquisition_task(
                                        user_id, gap_id
                                    )
                    except Exception as check_error:
                        logger.error(f"Error checking RSS feed {source_id}: {check_error}")
                    
                    # Wait for next check
                    await asyncio.sleep(interval)
                    
            except asyncio.CancelledError:
                # Task was cancelled
                pass
            except Exception as e:
                logger.error(f"Error in RSS monitoring task for source {source_id}: {str(e)}")
        
        # Start the monitoring task
        task = asyncio.create_task(monitor_rss_feed())
        self.monitoring_tasks[source_id] = task
    
    def _start_api_monitoring(self, source_id: str, source_config: Dict[str, Any]) -> None:
        """Start API monitoring task.
        
        Args:
            source_id: Source ID
            source_config: Source configuration
        """
        async def monitor_api():
            try:
                schedule = source_config.get("schedule", "hourly")
                
                # Determine check interval
                if schedule == "hourly":
                    interval = 60 * 60  # 1 hour
                elif schedule == "daily":
                    interval = 24 * 60 * 60  # 24 hours
                elif schedule == "weekly":
                    interval = 7 * 24 * 60 * 60  # 7 days
                else:
                    interval = 60 * 60  # Default to hourly
                
                while True:
                    # Check API
                    source = await self.storage.get_document("monitored_sources", source_id)
                    
                    if not source or not source.get("is_active", False):
                        # Source was removed or deactivated
                        break
                    
                    user_id = source.get("user_id")
                    
                    try:
                        # Check for new information
                        new_information = await self._check_source_for_new_information(source)
                        
                        if new_information:
                            # Create knowledge gaps for the new information
                            gaps_created = await self._create_gaps_from_new_information(
                                user_id, new_information, source
                            )
                            
                            # Trigger acquisition for the gaps
                            for gap_id in gaps_created:
                                if self.acquisition_manager:
                                    await self.acquisition_manager.schedule_acquisition_task(
                                        user_id, gap_id
                                    )
                    except Exception as check_error:
                        logger.error(f"Error checking API {source_id}: {check_error}")
                    
                    # Wait for next check
                    await asyncio.sleep(interval)
                    
            except asyncio.CancelledError:
                # Task was cancelled
                pass
            except Exception as e:
                logger.error(f"Error in API monitoring task for source {source_id}: {str(e)}")
        
        # Start the monitoring task
        task = asyncio.create_task(monitor_api())
        self.monitoring_tasks[source_id] = task
    
    def _start_web_monitoring(self, source_id: str, source_config: Dict[str, Any]) -> None:
        """Start web page monitoring task.
        
        Args:
            source_id: Source ID
            source_config: Source configuration
        """
        async def monitor_web_page():
            try:
                schedule = source_config.get("schedule", "daily")
                
                # Determine check interval
                if schedule == "hourly":
                    interval = 60 * 60  # 1 hour
                elif schedule == "daily":
                    interval = 24 * 60 * 60  # 24 hours
                elif schedule == "weekly":
                    interval = 7 * 24 * 60 * 60  # 7 days
                else:
                    interval = 24 * 60 * 60  # Default to daily
                
                while True:
                    # Check web page
                    source = await self.storage.get_document("monitored_sources", source_id)
                    
                    if not source or not source.get("is_active", False):
                        # Source was removed or deactivated
                        break
                    
                    user_id = source.get("user_id")
                    
                    try:
                        # Check for new information
                        new_information = await self._check_source_for_new_information(source)
                        
                        if new_information:
                            # Create knowledge gaps for the new information
                            gaps_created = await self._create_gaps_from_new_information(
                                user_id, new_information, source
                            )
                            
                            # Trigger acquisition for the gaps
                            for gap_id in gaps_created:
                                if self.acquisition_manager:
                                    await self.acquisition_manager.schedule_acquisition_task(
                                        user_id, gap_id
                                    )
                    except Exception as check_error:
                        logger.error(f"Error checking web page {source_id}: {check_error}")
                    
                    # Wait for next check
                    await asyncio.sleep(interval)
                    
            except asyncio.CancelledError:
                # Task was cancelled
                pass
            except Exception as e:
                logger.error(f"Error in web monitoring task for source {source_id}: {str(e)}")
        
        # Start the monitoring task
        task = asyncio.create_task(monitor_web_page())
        self.monitoring_tasks[source_id] = task
    
    async def _check_source_for_new_information(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check a source for new information.
        
        Args:
            source: Source configuration
            
        Returns:
            List of new information items
        """
        source_type = source.get("source_type")
        source_url = source.get("source_url")
        keywords = source.get("keywords", [])
        
        if source_type == "rss":
            # Check RSS feed
            return await self._check_rss_feed(source_url, keywords, source)
            
        elif source_type == "api":
            # Check API
            return await self._check_api(source_url, keywords, source)
            
        elif source_type == "web":
            # Check web page
            return await self._check_web_page(source_url, keywords, source)
            
        return []
    
    async def _check_rss_feed(self, feed_url: str, keywords: List[str], source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check RSS feed for new entries.
        
        Args:
            feed_url: RSS feed URL
            keywords: Keywords to filter entries
            source: Source configuration
            
        Returns:
            List of new entries
        """
        try:
            import feedparser
            import aiohttp
            
            # Get source info
            user_id = source.get("user_id")
            last_check = source.get("last_check")
            
            # Fetch RSS feed
            async with aiohttp.ClientSession() as session:
                async with session.get(feed_url) as response:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    new_entries = []
                    
                    for entry in feed.entries:
                        # Check if entry is new since last check
                        entry_date = entry.get("published_parsed") or entry.get("updated_parsed")
                        
                        if entry_date:
                            entry_datetime = datetime(*entry_date[:6])
                            
                            if last_check and entry_datetime <= last_check:
                                continue
                        elif last_check:
                            # If no date, assume it's a new entry after a first check
                            if not isinstance(last_check, datetime):
                                continue
                        
                        # Check if entry matches keywords
                        entry_title = entry.get("title", "")
                        entry_summary = entry.get("summary", "")
                        
                        if not keywords or any(keyword.lower() in entry_title.lower() or 
                                            keyword.lower() in entry_summary.lower() 
                                            for keyword in keywords):
                            # Check if entry already processed
                            existing = await self.storage.find_one(
                                "source_entries",
                                {
                                    "user_id": user_id,
                                    "source_id": source.get("_id"),
                                    "entry_id": entry.get("id", entry.get("link", ""))
                                }
                            )
                            
                            if not existing:
                                # Record the entry
                                entry_record = {
                                    "user_id": user_id,
                                    "source_id": source.get("_id"),
                                    "entry_id": entry.get("id", entry.get("link", "")),
                                    "title": entry_title,
                                    "url": entry.get("link", ""),
                                    "content": entry_summary,
                                    "timestamp": datetime.utcnow()
                                }
                                
                                await self.storage.save_document("source_entries", entry_record)
                                
                                # Add to new entries
                                new_entries.append({
                                    "title": entry_title,
                                    "content": entry_summary,
                                    "url": entry.get("link", ""),
                                    "source_type": "rss",
                                    "source_url": feed_url
                                })
                    
                    return new_entries
                    
        except (ImportError, Exception) as e:
            logger.error(f"Error checking RSS feed {feed_url}: {str(e)}")
            return []
    
    async def _check_api(self, api_url: str, keywords: List[str], source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check API for new data.
        
        Args:
            api_url: API URL
            keywords: Keywords to filter data
            source: Source configuration
            
        Returns:
            List of new data items
        """
        try:
            import aiohttp
            
            # Get source info
            user_id = source.get("user_id")
            params = source.get("params", {})
            
            # Call API
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, params=params) as response:
                    if response.status != 200:
                        return []
                        
                    content = await response.text()
                    
                    try:
                        data = json.loads(content)
                    except json.JSONDecodeError:
                        # Not JSON data
                        return []
                    
                    # Process API response
                    items = []
                    
                    # Extract items from response (depends on API structure)
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        # Try common patterns for items in APIs
                        for key in ["items", "results", "data", "content", "response"]:
                            if key in data and isinstance(data[key], list):
                                items = data[key]
                                break
                        
                        if not items and not any(isinstance(v, (list, dict)) for v in data.values()):
                            # Treat entire response as a single item
                            items = [data]
                    
                    new_items = []
                    
                    for item in items:
                        # Convert item to string for keyword matching
                        item_str = json.dumps(item)
                        
                        # Check if item matches keywords
                        if not keywords or any(keyword.lower() in item_str.lower() for keyword in keywords):
                            # Generate a unique ID for the item
                            item_id = hash(item_str)
                            
                            # Check if item already processed
                            existing = await self.storage.find_one(
                                "source_entries",
                                {
                                    "user_id": user_id,
                                    "source_id": source.get("_id"),
                                    "entry_id": str(item_id)
                                }
                            )
                            
                            if not existing:
                                # Extract title and content
                                title = self._extract_title_from_item(item)
                                content = item_str
                                
                                # Record the item
                                item_record = {
                                    "user_id": user_id,
                                    "source_id": source.get("_id"),
                                    "entry_id": str(item_id),
                                    "title": title,
                                    "url": api_url,
                                    "content": content,
                                    "timestamp": datetime.utcnow()
                                }
                                
                                await self.storage.save_document("source_entries", item_record)
                                
                                # Add to new items
                                new_items.append({
                                    "title": title,
                                    "content": content,
                                    "url": api_url,
                                    "source_type": "api",
                                    "source_url": api_url
                                })
                    
                    return new_items
                    
        except Exception as e:
            logger.error(f"Error checking API {api_url}: {str(e)}")
            return []
    
    async def _check_web_page(self, page_url: str, keywords: List[str], source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check web page for changes.
        
        Args:
            page_url: Web page URL
            keywords: Keywords to filter content
            source: Source configuration
            
        Returns:
            List of new content items
        """
        try:
            import aiohttp
            from bs4 import BeautifulSoup
            
            # Get source info
            user_id = source.get("user_id")
            last_content = source.get("last_content")
            
            # Fetch web page
            async with aiohttp.ClientSession() as session:
                async with session.get(page_url) as response:
                    if response.status != 200:
                        return []
                        
                    content = await response.text()
                    
                    # Parse HTML
                    soup = BeautifulSoup(content, "html.parser")
                    
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.extract()
                    
                    # Get text content
                    text = soup.get_text()
                    
                    # Break into lines and remove leading and trailing space
                    lines = (line.strip() for line in text.splitlines())
                    # Break multi-headlines into a line each
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    # Join the lines
                    text = "\n".join(chunk for chunk in chunks if chunk)
                    
                    # Check if content has changed
                    if last_content and text == last_content:
                        return []
                    
                    # Update last content
                    await self.storage.update_document(
                        "monitored_sources",
                        source.get("_id"),
                        {"last_content": text}
                    )
                    
                    # If no previous content, just record the current content
                    if not last_content:
                        return []
                    
                    # Extract title
                    title = soup.title.string if soup.title else page_url
                    
                    # Check for keywords
                    if not keywords or any(keyword.lower() in text.lower() for keyword in keywords):
                        # Record the entry
                        entry_record = {
                            "user_id": user_id,
                            "source_id": source.get("_id"),
                            "entry_id": f"{page_url}_{datetime.utcnow().timestamp()}",
                            "title": title,
                            "url": page_url,
                            "content": text[:5000],  # Limit content length
                            "timestamp": datetime.utcnow()
                        }
                        
                        await self.storage.save_document("source_entries", entry_record)
                        
                        # Return as new content
                        return [{
                            "title": title,
                            "content": text[:5000],  # Limit content length
                            "url": page_url,
                            "source_type": "web",
                            "source_url": page_url
                        }]
                    
                    return []
                    
        except (ImportError, Exception) as e:
            logger.error(f"Error checking web page {page_url}: {str(e)}")
            return []
    
    async def _create_gaps_from_new_information(self, user_id: str, new_information: List[Dict[str, Any]], source: Dict[str, Any]) -> List[str]:
        """Create knowledge gaps from new information.
        
        Args:
            user_id: User ID
            new_information: New information items
            source: Source configuration
            
        Returns:
            List of created gap IDs
        """
        created_gaps = []
        
        for item in new_information:
            # Determine most relevant topic
            topics = source.get("topics", [])
            topic_id = None
            
            if topics:
                topic_id = topics[0]  # Use the first topic for now
                
                # TODO: Implement more sophisticated topic matching
            
            # Create a timeliness gap for the new information
            gap_data = {
                "user_id": user_id,
                "type": "timeliness",
                "description": f"New information: {item.get('title', 'Update')}",
                "topic_id": topic_id,
                "related_node_ids": [],
                "severity": 0.7,  # High severity for new information
                "identified_at": datetime.utcnow(),
                "status": "open",
                "source": {
                    "type": item.get("source_type"),
                    "url": item.get("url"),
                    "content": item.get("content")
                }
            }
            
            # Save the gap
            gap_id = await self.storage.save_document("knowledge_gaps", gap_data)
            created_gaps.append(str(gap_id))
        
        return created_gaps
    
    def _extract_title_from_item(self, item: Dict[str, Any]) -> str:
        """Extract a title from an API response item.
        
        Args:
            item: API response item
            
        Returns:
            Extracted title
        """
        # Try common title fields
        for field in ["title", "name", "label", "subject", "heading"]:
            if field in item and isinstance(item[field], str):
                return item[field]
        
        # If no title field, look for any string field with "title" in the name
        for field, value in item.items():
            if isinstance(value, str) and "title" in field.lower():
                return value
        
        # Fallback: use the first string field
        for field, value in item.items():
            if isinstance(value, str) and len(value) < 100:
                return value
        
        # Last resort: use item hash
        return f"Data item {hash(json.dumps(item))}"