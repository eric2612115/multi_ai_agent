"""Node lifecycle state transition engine.

This module provides the engine for managing node state transitions
based on rules and conditions.
"""
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple, Callable

from src.forest.models import Node, NodeStatus
from src.common.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class StateTransitionEngine:
    """Engine for managing node state transitions."""
    
    def __init__(self):
        """Initialize the state transition engine."""
        # Define possible transitions and rules
        self.valid_transitions = {
            NodeStatus.BUDDING: {NodeStatus.GROWING, NodeStatus.ACTIVE, NodeStatus.MERGED},
            NodeStatus.GROWING: {NodeStatus.ACTIVE, NodeStatus.EVOLVING, NodeStatus.MERGED},
            NodeStatus.ACTIVE: {NodeStatus.EVOLVING, NodeStatus.DECLINING, NodeStatus.DORMANT, NodeStatus.MERGED},
            NodeStatus.EVOLVING: {NodeStatus.ACTIVE, NodeStatus.DECLINING, NodeStatus.MERGED},
            NodeStatus.DECLINING: {NodeStatus.ACTIVE, NodeStatus.DORMANT, NodeStatus.ARCHIVED, NodeStatus.MERGED},
            NodeStatus.DORMANT: {NodeStatus.ACTIVE, NodeStatus.ARCHIVED, NodeStatus.MERGED},
            NodeStatus.ARCHIVED: {NodeStatus.DORMANT, NodeStatus.MERGED},
            NodeStatus.MERGED: set()  # Terminal state
        }
        
        # Transition rules (functions that determine if transition is valid)
        self.transition_rules = {
            # Transition from BUDDING
            (NodeStatus.BUDDING, NodeStatus.GROWING): self._check_budding_to_growing,
            (NodeStatus.BUDDING, NodeStatus.ACTIVE): self._check_budding_to_active,
            
            # Transition from GROWING
            (NodeStatus.GROWING, NodeStatus.ACTIVE): self._check_growing_to_active,
            (NodeStatus.GROWING, NodeStatus.EVOLVING): self._check_growing_to_evolving,
            
            # Transition from ACTIVE
            (NodeStatus.ACTIVE, NodeStatus.EVOLVING): self._check_active_to_evolving,
            (NodeStatus.ACTIVE, NodeStatus.DECLINING): self._check_active_to_declining,
            (NodeStatus.ACTIVE, NodeStatus.DORMANT): self._check_active_to_dormant,
            
            # Transition from EVOLVING
            (NodeStatus.EVOLVING, NodeStatus.ACTIVE): self._check_evolving_to_active,
            (NodeStatus.EVOLVING, NodeStatus.DECLINING): self._check_evolving_to_declining,
            
            # Transition from DECLINING
            (NodeStatus.DECLINING, NodeStatus.ACTIVE): self._check_declining_to_active,
            (NodeStatus.DECLINING, NodeStatus.DORMANT): self._check_declining_to_dormant,
            (NodeStatus.DECLINING, NodeStatus.ARCHIVED): self._check_declining_to_archived,
            
            # Transition from DORMANT
            (NodeStatus.DORMANT, NodeStatus.ACTIVE): self._check_dormant_to_active,
            (NodeStatus.DORMANT, NodeStatus.ARCHIVED): self._check_dormant_to_archived,
            
            # Transition from ARCHIVED
            (NodeStatus.ARCHIVED, NodeStatus.DORMANT): self._check_archived_to_dormant,
            
            # Merged transitions (any state can transition to MERGED)
            (NodeStatus.BUDDING, NodeStatus.MERGED): self._check_any_to_merged,
            (NodeStatus.GROWING, NodeStatus.MERGED): self._check_any_to_merged,
            (NodeStatus.ACTIVE, NodeStatus.MERGED): self._check_any_to_merged,
            (NodeStatus.EVOLVING, NodeStatus.MERGED): self._check_any_to_merged,
            (NodeStatus.DECLINING, NodeStatus.MERGED): self._check_any_to_merged,
            (NodeStatus.DORMANT, NodeStatus.MERGED): self._check_any_to_merged,
            (NodeStatus.ARCHIVED, NodeStatus.MERGED): self._check_any_to_merged,
        }
    
    #--------------------------------------------------------------------------
    # Core interface methods
    #--------------------------------------------------------------------------
    
    def get_valid_transitions(self, status: NodeStatus) -> Set[NodeStatus]:
        """Get valid state transitions from a given state.
        
        Args:
            status: Current node status
            
        Returns:
            Set of valid target states
        """
        return self.valid_transitions.get(status, set())
    
    def check_transition_rule(self, 
                            node: Node, 
                            target_status: NodeStatus,
                            context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """Check if a transition is allowed based on rules.
        
        Args:
            node: The node to transition
            target_status: Target status to transition to
            context: Optional context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check if the transition is valid in principle
        if target_status not in self.valid_transitions.get(node.status, set()):
            return False, f"Invalid transition from {node.status} to {target_status}"
            
        # Use rule function if available
        rule_func = self.transition_rules.get((node.status, target_status))
        if rule_func:
            return rule_func(node, context or {})
            
        # If no specific rule, allow the transition
        return True, "No specific rule defined"
    
    #--------------------------------------------------------------------------
    # Budding state transition rules
    #--------------------------------------------------------------------------
    
    def _check_budding_to_growing(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from BUDDING to GROWING.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check content completeness - budding nodes should be developing
        min_certainty = 0.4
        
        if node.certainty_score < min_certainty:
            return False, f"Node certainty too low ({node.certainty_score:.2f} < {min_certainty})"
            
        # Check if it has a summary
        if not node.summary:
            return False, "Node needs a summary to grow"
            
        return True, "Node is ready to grow"
    
    def _check_budding_to_active(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition directly from BUDDING to ACTIVE.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # This is a "fast track" for nodes that are created with sufficient information
        min_certainty = 0.7
        min_age_hours = 1
        
        if node.certainty_score < min_certainty:
            return False, f"Node certainty too low for fast track ({node.certainty_score:.2f} < {min_certainty})"
            
        # Check content
        if not node.summary:
            return False, "Node needs a summary to become active"
            
        # Check age (avoid premature activation)
        node_age_hours = (datetime.utcnow() - node.created_at).total_seconds() / 3600
        if node_age_hours < min_age_hours:
            return False, f"Node too new for fast track ({node_age_hours:.1f}h < {min_age_hours}h)"
            
        return True, "Node is ready for direct activation"
    
    #--------------------------------------------------------------------------
    # Growing state transition rules
    #--------------------------------------------------------------------------
    
    def _check_growing_to_active(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from GROWING to ACTIVE.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        min_certainty = 0.6
        min_age_days = 1
        
        if node.certainty_score < min_certainty:
            return False, f"Node certainty too low ({node.certainty_score:.2f} < {min_certainty})"
            
        # Check age
        node_age_days = (datetime.utcnow() - node.created_at).total_seconds() / (24 * 3600)
        if node_age_days < min_age_days:
            return False, f"Node too new ({node_age_days:.1f}d < {min_age_days}d)"
            
        return True, "Node is ready for activation"
    
    def _check_growing_to_evolving(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from GROWING to EVOLVING.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # This is uncommon but can happen if a growing node suddenly needs significant revision
        forced = context.get("force_evolving", False)
        
        if not forced:
            # Check recent updates
            update_count = context.get("recent_update_count", 0)
            
            if update_count < 3:
                return False, f"Not enough recent updates ({update_count} < 3) for evolution"
                
        return True, "Node needs to evolve based on recent updates"
    
    #--------------------------------------------------------------------------
    # Active state transition rules
    #--------------------------------------------------------------------------
    
    def _check_active_to_evolving(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from ACTIVE to EVOLVING.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check if this is a forced evolution
        forced = context.get("force_evolving", False)
        
        if forced:
            return True, "Forced evolution transition"
            
        # Check number of recent updates
        update_count = context.get("recent_update_count", 0)
        
        if update_count < 2:
            return False, f"Not enough recent updates ({update_count} < 2)"
            
        # Check if certainty is decreasing
        certainty_change = context.get("certainty_change", 0)
        
        if certainty_change < -0.1:
            return True, f"Node certainty decreasing ({certainty_change:.2f})"
            
        # Check if the node's topic is evolving
        topic_evolving = context.get("topic_evolving", False)
        
        if topic_evolving:
            return True, "Node's topic is evolving"
            
        return False, "No sufficient reason for evolution"
    
    def _check_active_to_declining(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from ACTIVE to DECLINING.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check if this is a forced decline
        forced = context.get("force_declining", False)
        
        if forced:
            return True, "Forced declining transition"
            
        # Check node age
        min_age_days = 14  # Only older nodes can start declining
        node_age_days = (datetime.utcnow() - node.created_at).total_seconds() / (24 * 3600)
        
        if node_age_days < min_age_days:
            return False, f"Node too new to decline ({node_age_days:.1f}d < {min_age_days}d)"
            
        # Check if importance is decreasing
        importance_change = context.get("importance_change", 0)
        
        if importance_change < -0.15:
            return True, f"Node importance decreasing significantly ({importance_change:.2f})"
            
        # Check access patterns
        access_trend = context.get("access_trend", 0)
        
        if access_trend < -0.3:
            return True, f"Node access declining significantly ({access_trend:.2f})"
            
        # Check if timeliness has decreased
        timeliness_score = context.get("timeliness_score", 1.0)
        
        if timeliness_score < 0.4:
            return True, f"Node timeliness low ({timeliness_score:.2f})"
            
        return False, "No sufficient reason for decline"
    
    def _check_active_to_dormant(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from ACTIVE to DORMANT.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check if this is a forced dormancy
        forced = context.get("force_dormant", False)
        
        if forced:
            return True, "Forced dormancy transition"
            
        # Check if protected
        protect_until = node.metadata.get("config", {}).get("protect_until")
        if protect_until and protect_until > datetime.utcnow():
            return False, f"Node is protected until {protect_until.isoformat()}"
            
        # Check node importance
        dormancy_threshold = settings.lifecycle.node_dormancy_threshold
        
        if node.importance_score > dormancy_threshold:
            return False, f"Node importance too high ({node.importance_score:.2f} > {dormancy_threshold})"
            
        # Check node age
        min_age_days = settings.lifecycle.node_min_age_days
        node_age_days = (datetime.utcnow() - node.created_at).total_seconds() / (24 * 3600)
        
        if node_age_days < min_age_days:
            return False, f"Node too new for dormancy ({node_age_days:.1f}d < {min_age_days}d)"
            
        # Check if auto-prune is disabled for this node
        auto_prune = node.metadata.get("config", {}).get("auto_prune", True)
        
        if not auto_prune:
            return False, "Auto-pruning is disabled for this node"
            
        # Check if node has been accessed recently
        days_since_access = 30  # Default high value
        if node.metadata.get("last_accessed"):
            days_since_access = (datetime.utcnow() - node.metadata.get("last_accessed")).total_seconds() / (24 * 3600)
            
        if days_since_access < 14:
            return False, f"Node accessed recently ({days_since_access:.1f}d < 14d)"
            
        return True, f"Node can be made dormant (importance: {node.importance_score:.2f}, age: {node_age_days:.1f}d)"
    
    #--------------------------------------------------------------------------
    # Evolving state transition rules
    #--------------------------------------------------------------------------
    
    def _check_evolving_to_active(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from EVOLVING to ACTIVE.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check if evolution is complete
        evolution_complete = context.get("evolution_complete", False)
        
        if not evolution_complete:
            # Check for minimum time in evolving state
            min_evolution_days = 1
            days_in_evolution = 0
            
            if node.last_status_change:
                days_in_evolution = (datetime.utcnow() - node.last_status_change).total_seconds() / (24 * 3600)
                
            if days_in_evolution < min_evolution_days:
                return False, f"Not enough time in evolution ({days_in_evolution:.1f}d < {min_evolution_days}d)"
                
            # Check for stabilization
            update_count = context.get("recent_update_count", 0)
            if update_count > 1:
                return False, f"Node still being updated frequently ({update_count} updates recently)"
        
        # Check if certainty is now acceptable
        min_certainty = 0.6
        
        if node.certainty_score < min_certainty:
            return False, f"Node certainty still too low ({node.certainty_score:.2f} < {min_certainty})"
            
        return True, "Evolution complete, node can return to active state"
    
    def _check_evolving_to_declining(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from EVOLVING to DECLINING.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # This transition happens when evolution isn't going well
        
        # Check if evolution has been in progress for too long
        max_evolution_days = 7
        days_in_evolution = 0
        
        if node.last_status_change:
            days_in_evolution = (datetime.utcnow() - node.last_status_change).total_seconds() / (24 * 3600)
            
        if days_in_evolution < max_evolution_days:
            return False, f"Not enough time in evolution to consider declining ({days_in_evolution:.1f}d < {max_evolution_days}d)"
            
        # Check if importance is decreasing
        importance_change = context.get("importance_change", 0)
        
        if importance_change < -0.2:
            return True, f"Node importance decreasing during evolution ({importance_change:.2f})"
            
        # Check if evolution is failing
        evolution_progress = context.get("evolution_progress", 0.5)
        
        if evolution_progress < 0.3:
            return True, f"Evolution not progressing well ({evolution_progress:.2f})"
            
        return False, "No sufficient reason to transition from evolving to declining"
    
    #--------------------------------------------------------------------------
    # Declining state transition rules
    #--------------------------------------------------------------------------
    
    def _check_declining_to_active(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from DECLINING to ACTIVE.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # This is a "revival" - the node becomes relevant again
        
        # Check if this is a forced revival
        forced = context.get("force_revival", False)
        
        if forced:
            return True, "Forced revival transition"
            
        # Check if importance is increasing
        importance_change = context.get("importance_change", 0)
        
        if importance_change > 0.15:
            return True, f"Node importance increasing ({importance_change:.2f})"
            
        # Check access patterns
        access_trend = context.get("access_trend", 0)
        
        if access_trend > 0.2:
            return True, f"Node access increasing ({access_trend:.2f})"
            
        # Check new connections
        new_connections = context.get("new_connections", 0)
        
        if new_connections >= 2:
            return True, f"Node gained new connections ({new_connections})"
            
        return False, "No sufficient reason for revival"
    
    def _check_declining_to_dormant(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from DECLINING to DORMANT.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check if this is a forced dormancy
        forced = context.get("force_dormant", False)
        
        if forced:
            return True, "Forced dormancy transition"
            
        # Check node importance
        dormancy_threshold = settings.knowledge_lifecycle.node_dormancy_threshold
        
        if node.importance_score > dormancy_threshold:
            return False, f"Node importance still too high ({node.importance_score:.2f} > {dormancy_threshold})"
            
        # Check time in declining state
        min_declining_days = 3
        days_in_declining = 0
        
        if node.last_status_change:
            days_in_declining = (datetime.utcnow() - node.last_status_change).total_seconds() / (24 * 3600)
            
        if days_in_declining < min_declining_days:
            return False, f"Not enough time in declining state ({days_in_declining:.1f}d < {min_declining_days}d)"
            
        # Check access patterns
        days_since_access = 30  # Default high value
        if node.metadata.get("last_accessed"):
            days_since_access = (datetime.utcnow() - node.metadata.get("last_accessed")).total_seconds() / (24 * 3600)
            
        if days_since_access < 10:
            return False, f"Node accessed recently ({days_since_access:.1f}d < 10d)"
            
        return True, "Node can be made dormant due to continued decline"
    
    def _check_declining_to_archived(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from DECLINING to ARCHIVED.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # This is direct archiving without going through dormancy
        
        # Check if this is a forced archive
        forced = context.get("force_archive", False)
        
        if forced:
            return True, "Forced archive transition"
            
        # Check node importance - must be very low
        archive_threshold = 0.1  # Lower than dormancy
        
        if node.importance_score > archive_threshold:
            return False, f"Node importance too high for direct archive ({node.importance_score:.2f} > {archive_threshold})"
            
        # Check time in declining state - must be very long
        min_declining_days = 30  # Must be declining for a long time
        days_in_declining = 0
        
        if node.last_status_change:
            days_in_declining = (datetime.utcnow() - node.last_status_change).total_seconds() / (24 * 3600)
            
        if days_in_declining < min_declining_days:
            return False, f"Not enough time in declining state for direct archive ({days_in_declining:.1f}d < {min_declining_days}d)"
            
        # Check node age - must be old
        min_age_days = 60
        node_age_days = (datetime.utcnow() - node.created_at).total_seconds() / (24 * 3600)
        
        if node_age_days < min_age_days:
            return False, f"Node too new for direct archive ({node_age_days:.1f}d < {min_age_days}d)"
            
        # Check access patterns - must be virtually unused
        days_since_access = 30  # Default high value
        if node.metadata.get("last_accessed"):
            days_since_access = (datetime.utcnow() - node.metadata.get("last_accessed")).total_seconds() / (24 * 3600)
            
        if days_since_access < 30:
            return False, f"Node accessed too recently for direct archive ({days_since_access:.1f}d < 30d)"
            
        return True, "Node can be archived directly due to extended decline and no usage"
    
    #--------------------------------------------------------------------------
    # Dormant state transition rules
    #--------------------------------------------------------------------------
    
    def _check_dormant_to_active(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from DORMANT to ACTIVE.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # This is a revival from dormancy
        
        # Check if this is a forced revival
        forced = context.get("force_revival", False)
        
        if forced:
            return True, "Forced revival from dormancy"
            
        # Check revival probability from node config
        revival_prob = node.metadata.get("config", {}).get("revival_probability", 1.0)
        random_factor = context.get("random_factor", 0.5)
        
        if random_factor > revival_prob:
            return False, f"Revival probability check failed ({random_factor:.2f} > {revival_prob:.2f})"
            
        # Check if importance has increased
        revival_threshold = settings.knowledge_lifecycle.revival_threshold
        
        if node.importance_score < revival_threshold:
            return False, f"Node importance too low for revival ({node.importance_score:.2f} < {revival_threshold})"
            
        # Check recent access
        recent_access = context.get("recently_accessed", False)
        
        if recent_access:
            return True, "Node was recently accessed"
            
        # Check new connections
        new_connections = context.get("new_connections", 0)
        
        if new_connections >= 1:
            return True, f"Node gained new connections ({new_connections})"
            
        # Check topic relevance
        topic_relevance = context.get("topic_relevance", 0)
        
        if topic_relevance > 0.7:
            return True, f"Topic became relevant again ({topic_relevance:.2f})"
            
        return False, "No sufficient reason for revival from dormancy"
    
    def _check_dormant_to_archived(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from DORMANT to ARCHIVED.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check if this is a forced archive
        forced = context.get("force_archive", False)
        
        if forced:
            return True, "Forced archive transition"
            
        # Check time in dormant state
        min_dormant_days = 30
        days_in_dormant = 0
        
        if node.last_status_change:
            days_in_dormant = (datetime.utcnow() - node.last_status_change).total_seconds() / (24 * 3600)
            
        if days_in_dormant < min_dormant_days:
            return False, f"Not enough time in dormant state ({days_in_dormant:.1f}d < {min_dormant_days}d)"
            
        # Check if node was never revived despite opportunities
        revival_attempts = context.get("revival_attempts", 0)
        
        if revival_attempts >= 2:
            return True, f"Failed to revive after {revival_attempts} attempts"
            
        # Check node importance - must be very low
        archive_threshold = 0.1
        
        if node.importance_score <= archive_threshold:
            return True, f"Node importance extremely low ({node.importance_score:.2f} <= {archive_threshold})"
            
        # Check available storage space
        storage_pressure = context.get("storage_pressure", 0)
        
        if storage_pressure > 0.8:
            return True, f"System storage pressure high ({storage_pressure:.2f})"
            
        return False, "No sufficient reason to archive dormant node"
    
    #--------------------------------------------------------------------------
    # Archived state transition rules
    #--------------------------------------------------------------------------
    
    def _check_archived_to_dormant(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can transition from ARCHIVED to DORMANT.
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # This is a partial revival from archive to dormant state
        
        # Check if this is a forced revival
        forced = context.get("force_revival", False)
        
        if forced:
            return True, "Forced revival from archive to dormant"
            
        # Check recent access (someone looked up the archive)
        recent_access = context.get("recently_accessed", False)
        
        if recent_access:
            return True, "Archived node was accessed"
            
        # Check if topic became relevant again
        topic_relevance = context.get("topic_relevance", 0)
        
        if topic_relevance > 0.8:
            return True, f"Topic became highly relevant again ({topic_relevance:.2f})"
            
        # Check for explicit revival requests
        revival_requests = context.get("revival_requests", 0)
        
        if revival_requests > 0:
            return True, f"Received {revival_requests} explicit revival requests"
            
        return False, "No sufficient reason to revive from archive"
    
    #--------------------------------------------------------------------------
    # Special merge transition rules
    #--------------------------------------------------------------------------
    
    def _check_any_to_merged(self, node: Node, context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a node can be merged (from any state).
        
        Args:
            node: The node to transition
            context: Context information
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # For merging, we mainly check if target node info is provided
        
        # Check if this is a forced merge
        forced = context.get("force_merge", False)
        
        if forced:
            return True, "Forced merge transition"
            
        # Check if we have target node information
        target_node_id = context.get("target_node_id")
        
        if not target_node_id:
            return False, "No target node specified for merge"
            
        # Check if similarity is high enough
        similarity = context.get("similarity", 0)
        min_similarity = 0.8
        
        if similarity < min_similarity:
            return False, f"Similarity too low for merge ({similarity:.2f} < {min_similarity})"
            
        # Check if target node has higher importance
        target_importance = context.get("target_importance", 0)
        
        if target_importance <= node.importance_score:
            return False, f"Target node not more important ({target_importance:.2f} <= {node.importance_score:.2f})"
            
        return True, f"Node can be merged with target (similarity: {similarity:.2f})"
