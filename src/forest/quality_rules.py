"""Quality monitoring rules for the Knowledge Forest.

This module defines rules for evaluating the quality and health
of the knowledge forest, supporting the internal quality monitoring
capabilities of the system.
"""
from typing import Dict, List, Any, Optional, Tuple, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class QualityRuleSeverity(Enum):
    """Severity levels for quality rules."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class QualityRuleScope(Enum):
    """Scopes for quality rules."""
    NODE = "node"           # Single node
    TOPIC = "topic"         # Topic cluster
    STRUCTURE = "structure" # Overall graph structure
    CONTENT = "content"     # Content quality

class QualityRule:
    """Base class for quality rules."""
    
    def __init__(self, 
                name: str, 
                description: str,
                scope: QualityRuleScope,
                severity: QualityRuleSeverity,
                threshold: float):
        """Initialize a quality rule.
        
        Args:
            name: Rule name
            description: Rule description
            scope: Rule scope
            severity: Rule severity
            threshold: Threshold for rule violation
        """
        self.name = name
        self.description = description
        self.scope = scope
        self.severity = severity
        self.threshold = threshold
    
    def evaluate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Evaluate the rule on data.
        
        Args:
            data: Data to evaluate
            
        Returns:
            Tuple of (passes_rule, explanation)
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary.
        
        Returns:
            Rule as dictionary
        """
        return {
            "name": self.name,
            "description": self.description,
            "scope": self.scope.value,
            "severity": self.severity.value,
            "threshold": self.threshold
        }

class StructuralRules:
    """Structural quality rules for knowledge forest."""
    
    @staticmethod
    def isolated_node_ratio(threshold: float = 0.1) -> QualityRule:
        """Rule for ratio of isolated nodes.
        
        Args:
            threshold: Maximum allowed ratio of isolated nodes
            
        Returns:
            QualityRule instance
        """
        class IsolatedNodeRatioRule(QualityRule):
            def __init__(self, threshold: float):
                super().__init__(
                    name="isolated_node_ratio",
                    description=f"No more than {threshold:.0%} of nodes should be isolated",
                    scope=QualityRuleScope.STRUCTURE,
                    severity=QualityRuleSeverity.WARNING,
                    threshold=threshold
                )
                
            def evaluate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
                if "node_count" not in data or "isolated_nodes" not in data:
                    return False, "Missing required data"
                    
                node_count = data["node_count"]
                isolated_count = data["isolated_nodes"]
                
                if node_count == 0:
                    return True, None
                    
                ratio = isolated_count / node_count
                passes = ratio <= self.threshold
                
                explanation = None if passes else f"Isolated node ratio ({ratio:.2%}) exceeds threshold ({self.threshold:.0%})"
                
                return passes, explanation
        
        return IsolatedNodeRatioRule(threshold)
    
    @staticmethod
    def average_connectivity(threshold: float = 2.0) -> QualityRule:
        """Rule for average node connectivity.
        
        Args:
            threshold: Minimum average connectivity (edges per node)
            
        Returns:
            QualityRule instance
        """
        class AverageConnectivityRule(QualityRule):
            def __init__(self, threshold: float):
                super().__init__(
                    name="average_connectivity",
                    description=f"Average node should have at least {threshold} connections",
                    scope=QualityRuleScope.STRUCTURE,
                    severity=QualityRuleSeverity.WARNING,
                    threshold=threshold
                )
                
            def evaluate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
                if "node_count" not in data or "edge_count" not in data:
                    return False, "Missing required data"
                    
                node_count = data["node_count"]
                edge_count = data["edge_count"]
                
                if node_count <= 1:
                    return True, None
                    
                # Each edge connects 2 nodes, so multiply by 2 for average connections per node
                avg_connectivity = (edge_count * 2) / node_count
                passes = avg_connectivity >= self.threshold
                
                explanation = None if passes else f"Average connectivity ({avg_connectivity:.2f}) below threshold ({self.threshold:.1f})"
                
                return passes, explanation
        
        return AverageConnectivityRule(threshold)
    
    @staticmethod
    def cross_topic_connectivity(threshold: float = 0.5) -> QualityRule:
        """Rule for cross-topic connectivity.
        
        Args:
            threshold: Minimum ratio of topics that should be connected
            
        Returns:
            QualityRule instance
        """
        class CrossTopicConnectivityRule(QualityRule):
            def __init__(self, threshold: float):
                super().__init__(
                    name="cross_topic_connectivity",
                    description=f"At least {threshold:.0%} of topics should be connected to other topics",
                    scope=QualityRuleScope.STRUCTURE,
                    severity=QualityRuleSeverity.INFO,
                    threshold=threshold
                )
                
            def evaluate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
                if "topics_count" not in data or "connected_topics" not in data:
                    return False, "Missing required data"
                    
                topics_count = data["topics_count"]
                connected_topics = data["connected_topics"]
                
                if topics_count <= 1:
                    return True, None
                    
                ratio = connected_topics / topics_count
                passes = ratio >= self.threshold
                
                explanation = None if passes else f"Only {ratio:.2%} of topics are connected (threshold: {self.threshold:.0%})"
                
                return passes, explanation
        
        return CrossTopicConnectivityRule(threshold)

class AbstractionRules:
    """Abstraction quality rules for knowledge forest."""
    
    @staticmethod
    def abstraction_balance(threshold: float = 0.4) -> QualityRule:
        """Rule for abstraction level balance.
        
        Args:
            threshold: Minimum balance score
            
        Returns:
            QualityRule instance
        """
        class AbstractionBalanceRule(QualityRule):
            def __init__(self, threshold: float):
                super().__init__(
                    name="abstraction_balance",
                    description=f"Abstraction levels should be balanced with score >= {threshold:.1f}",
                    scope=QualityRuleScope.STRUCTURE,
                    severity=QualityRuleSeverity.WARNING,
                    threshold=threshold
                )
                
            def evaluate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
                if "abstraction_balance" not in data:
                    return False, "Missing required data"
                    
                balance = data["abstraction_balance"]
                passes = balance >= self.threshold
                
                explanation = None if passes else f"Abstraction balance ({balance:.2f}) below threshold ({self.threshold:.1f})"
                
                return passes, explanation
        
        return AbstractionBalanceRule(threshold)
    
    @staticmethod
    def high_level_abstraction_exists(min_level: int = 4) -> QualityRule:
        """Rule checking if high-level abstractions exist.
        
        Args:
            min_level: Minimum abstraction level that should exist
            
        Returns:
            QualityRule instance
        """
        class HighLevelAbstractionRule(QualityRule):
            def __init__(self, min_level: int):
                super().__init__(
                    name="high_level_abstraction_exists",
                    description=f"Knowledge should have abstractions at level {min_level} or higher",
                    scope=QualityRuleScope.STRUCTURE,
                    severity=QualityRuleSeverity.INFO,
                    threshold=min_level
                )
                
            def evaluate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
                if "abstraction_distribution" not in data or "node_count" not in data:
                    return False, "Missing required data"
                    
                abstraction_dist = data["abstraction_distribution"]
                node_count = data["node_count"]
                
                # Skip for small graphs
                if node_count < 10:
                    return True, None
                    
                # Check if there are any nodes at or above the minimum level
                high_level_count = sum(abstraction_dist.get(level, 0) for level in range(self.threshold, 6))
                passes = high_level_count > 0
                
                explanation = None if passes else f"No abstractions at level {self.threshold} or higher"
                
                return passes, explanation
        
        return HighLevelAbstractionRule(min_level)

class ContentRules:
    """Content quality rules for knowledge forest."""
    
    @staticmethod
    def verified_content_ratio(threshold: float = 0.3) -> QualityRule:
        """Rule for ratio of verified content.
        
        Args:
            threshold: Minimum ratio of verified nodes
            
        Returns:
            QualityRule instance
        """
        class VerifiedContentRatioRule(QualityRule):
            def __init__(self, threshold: float):
                super().__init__(
                    name="verified_content_ratio",
                    description=f"At least {threshold:.0%} of nodes should be verified",
                    scope=QualityRuleScope.CONTENT,
                    severity=QualityRuleSeverity.WARNING,
                    threshold=threshold
                )
                
            def evaluate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
                if "verified_ratio" not in data or "node_count" not in data:
                    return False, "Missing required data"
                    
                verified_ratio = data["verified_ratio"]
                node_count = data["node_count"]
                
                # Skip for small graphs
                if node_count < 5:
                    return True, None
                    
                passes = verified_ratio >= self.threshold
                
                explanation = None if passes else f"Verified content ratio ({verified_ratio:.2%}) below threshold ({self.threshold:.0%})"
                
                return passes, explanation
        
        return VerifiedContentRatioRule(threshold)
    
    @staticmethod
    def average_certainty(threshold: float = 0.6) -> QualityRule:
        """Rule for average certainty score.
        
        Args:
            threshold: Minimum average certainty score
            
        Returns:
            QualityRule instance
        """
        class AverageCertaintyRule(QualityRule):
            def __init__(self, threshold: float):
                super().__init__(
                    name="average_certainty",
                    description=f"Average certainty score should be at least {threshold:.1f}",
                    scope=QualityRuleScope.CONTENT,
                    severity=QualityRuleSeverity.WARNING,
                    threshold=threshold
                )
                
            def evaluate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
                if "avg_certainty" not in data:
                    return False, "Missing required data"
                    
                avg_certainty = data["avg_certainty"]
                passes = avg_certainty >= self.threshold
                
                explanation = None if passes else f"Average certainty ({avg_certainty:.2f}) below threshold ({self.threshold:.1f})"
                
                return passes, explanation
        
        return AverageCertaintyRule(threshold)
    
    @staticmethod
    def summary_completeness(threshold: float = 0.8) -> QualityRule:
        """Rule for summary completeness.
        
        Args:
            threshold: Minimum ratio of nodes with proper summaries
            
        Returns:
            QualityRule instance
        """
        class SummaryCompletenessRule(QualityRule):
            def __init__(self, threshold: float):
                super().__init__(
                    name="summary_completeness",
                    description=f"At least {threshold:.0%} of nodes should have proper summaries",
                    scope=QualityRuleScope.CONTENT,
                    severity=QualityRuleSeverity.INFO,
                    threshold=threshold
                )
                
            def evaluate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
                if "nodes_with_summary" not in data or "node_count" not in data:
                    return False, "Missing required data"
                    
                nodes_with_summary = data["nodes_with_summary"]
                node_count = data["node_count"]
                
                if node_count == 0:
                    return True, None
                    
                ratio = nodes_with_summary / node_count
                passes = ratio >= self.threshold
                
                explanation = None if passes else f"Only {ratio:.2%} of nodes have proper summaries (threshold: {self.threshold:.0%})"
                
                return passes, explanation
        
        return SummaryCompletenessRule(threshold)

class TopicRules:
    """Topic quality rules for knowledge forest."""
    
    @staticmethod
    def topic_balance(threshold: float = 0.3) -> QualityRule:
        """Rule for topic size balance.
        
        Args:
            threshold: Maximum ratio for largest topic
            
        Returns:
            QualityRule instance
        """
        class TopicBalanceRule(QualityRule):
            def __init__(self, threshold: float):
                super().__init__(
                    name="topic_balance",
                    description=f"No single topic should contain more than {threshold:.0%} of all nodes",
                    scope=QualityRuleScope.TOPIC,
                    severity=QualityRuleSeverity.INFO,
                    threshold=threshold
                )
                
            def evaluate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
                if "topic_distribution" not in data or "node_count" not in data:
                    return False, "Missing required data"
                    
                topic_distribution = data["topic_distribution"]
                node_count = data["node_count"]
                
                if node_count < 10 or len(topic_distribution) <= 1:
                    return True, None
                    
                # Find the largest topic
                largest_topic_size = max(topic_distribution.values()) if topic_distribution else 0
                
                if largest_topic_size == 0:
                    return True, None
                    
                ratio = largest_topic_size / node_count
                passes = ratio <= self.threshold
                
                explanation = None if passes else f"Largest topic contains {ratio:.2%} of nodes (threshold: {self.threshold:.0%})"
                
                return passes, explanation
        
        return TopicBalanceRule(threshold)
    
    @staticmethod
    def topic_internal_connectivity(threshold: float = 0.2) -> QualityRule:
        """Rule for internal topic connectivity.
        
        Args:
            threshold: Minimum connectivity within topics
            
        Returns:
            QualityRule instance
        """
        class TopicInternalConnectivityRule(QualityRule):
            def __init__(self, threshold: float):
                super().__init__(
                    name="topic_internal_connectivity",
                    description=f"Topics should have internal connectivity >= {threshold:.1f}",
                    scope=QualityRuleScope.TOPIC,
                    severity=QualityRuleSeverity.WARNING,
                    threshold=threshold
                )
                
            def evaluate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
                if "topics" not in data:
                    return False, "Missing required data"
                    
                topics = data["topics"]
                
                # Skip if no topics
                if not topics:
                    return True, None
                    
                # Check each topic
                low_connectivity_topics = []
                for topic in topics:
                    # Skip small topics
                    if topic.get("node_count", 0) < 5:
                        continue
                        
                    connectivity = topic.get("connectivity", 0)
                    if connectivity < self.threshold:
                        low_connectivity_topics.append(topic.get("label", "Unknown"))
                
                passes = len(low_connectivity_topics) == 0
                
                explanation = None if passes else f"Low connectivity in topics: {', '.join(low_connectivity_topics)}"
                
                return passes, explanation
        
        return TopicInternalConnectivityRule(threshold)

# Define standard rule sets
DEFAULT_RULES = [
    StructuralRules.isolated_node_ratio(0.15),
    StructuralRules.average_connectivity(1.5),
    StructuralRules.cross_topic_connectivity(0.5),
    AbstractionRules.abstraction_balance(0.4),
    AbstractionRules.high_level_abstraction_exists(4),
    ContentRules.verified_content_ratio(0.3),
    ContentRules.average_certainty(0.6),
    ContentRules.summary_completeness(0.8),
    TopicRules.topic_balance(0.35),
    TopicRules.topic_internal_connectivity(0.2)
]

STRICT_RULES = [
    StructuralRules.isolated_node_ratio(0.05),
    StructuralRules.average_connectivity(2.5),
    StructuralRules.cross_topic_connectivity(0.8),
    AbstractionRules.abstraction_balance(0.6),
    AbstractionRules.high_level_abstraction_exists(4),
    ContentRules.verified_content_ratio(0.5),
    ContentRules.average_certainty(0.75),
    ContentRules.summary_completeness(0.95),
    TopicRules.topic_balance(0.25),
    TopicRules.topic_internal_connectivity(0.3)
]

LENIENT_RULES = [
    StructuralRules.isolated_node_ratio(0.25),
    StructuralRules.average_connectivity(1.0),
    StructuralRules.cross_topic_connectivity(0.3),
    AbstractionRules.abstraction_balance(0.3),
    AbstractionRules.high_level_abstraction_exists(4),
    ContentRules.verified_content_ratio(0.2),
    ContentRules.average_certainty(0.5),
    ContentRules.summary_completeness(0.6),
    TopicRules.topic_balance(0.5),
    TopicRules.topic_internal_connectivity(0.1)
]