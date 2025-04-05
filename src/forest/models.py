"""Knowledge Forest data models (Pydantic V2 compatible).

This module defines the core data models for the Knowledge Forest system,
including nodes, edges, and other related structures, updated for Pydantic V2.
"""
from typing import List, Optional, Dict, Any, Union, Callable, Annotated, Set
from datetime import datetime, timedelta
import uuid
from enum import Enum
from pydantic import BaseModel, Field, field_validator, GetJsonSchemaHandler, computed_field
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
from bson import ObjectId

# Import configuration settings
from common.config import get_settings
settings = get_settings()
EMBEDDING_DIM = settings.ai.embedding_dimensions


# Custom string ID type that validates UUIDs but allows other string formats
class StringId(str):
    """
    Custom ID type that validates UUIDs but allows other string formats.
    
    This is used to handle various ID formats while ensuring they're all stored as strings.
    """
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Callable[[Any], core_schema.CoreSchema],
    ) -> core_schema.CoreSchema:
        """Define the core schema for validation and serialization."""
        def validate_id(v: Any) -> str:
            # Convert ObjectId to string if needed
            if isinstance(v, ObjectId):
                return str(v)
            
            # Accept UUID objects
            if isinstance(v, uuid.UUID):
                return str(v)
                
            # Accept strings
            if isinstance(v, str):
                # Try to validate as UUID if it looks like one
                if len(v) == 36 and "-" in v:
                    try:
                        uuid.UUID(v)  # Just to validate
                        return v
                    except ValueError:
                        pass  # Fall through to accept as regular string
                return v
                
            # Other types: attempt to convert to string
            return str(v)

        return core_schema.with_info_plain_validator_function(
            validate_id,
            serialization=core_schema.plain_serializer_function_ser_schema(str),
            json_schema_extra={"type": "string", "format": "id"}
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Updates the generated JSON schema."""
        return {"type": "string", "format": "id"}


class Message(BaseModel):
    """Message in a conversation."""

    id: StringId = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    speaker: str = Field(..., description="Message sender (e.g., 'user', 'ai:gemini')")
    text: str = Field(..., description="Original message text")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp (UTC)")
    ai_metadata: Optional[Dict[str, Any]] = Field(default=None,
                                                  description="AI-related metadata (e.g., token usage, latency)")

    model_config = {
        'populate_by_name': True,
        'arbitrary_types_allowed': True,
        'json_encoders': {uuid.UUID: str}
    }


class Conversation(BaseModel):
    """Conversation containing messages."""

    id: StringId = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_id: StringId = Field(..., description="User who owns this conversation")
    title: Optional[str] = Field(default=None, description="Conversation title (can be AI-generated or user-specified)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time (UTC)")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time (UTC)")
    participants: List[str] = Field(default_factory=list, description="List of participants")
    messages: List[Message] = Field(default_factory=list, description="List of conversation messages")

    model_config = {
        'populate_by_name': True,
        'arbitrary_types_allowed': True,
        'json_encoders': {uuid.UUID: str}
    }


class NodeVisualAttributes(BaseModel):
    """Visual attributes for nodes."""

    color: Optional[str] = None
    size: Optional[float] = None
    icon: Optional[str] = None

    model_config = {
        'arbitrary_types_allowed': True
    }


class NodeStatus(str, Enum):
    """Status of a knowledge node in its lifecycle."""
    
    BUDDING = "budding"       # Initial creation, incomplete
    GROWING = "growing"       # Still actively developing
    ACTIVE = "active"         # Mature, stable node
    EVOLVING = "evolving"     # Undergoing significant changes
    DECLINING = "declining"   # Decreasing in importance/relevance
    DORMANT = "dormant"       # Temporarily inactive but retrievable
    ARCHIVED = "archived"     # Long-term storage, rarely accessed
    MERGED = "merged"         # Merged into another node
    
    
class AbstractionLevel(int, Enum):
    """Abstraction level of a knowledge node."""
    
    INSTANCE = 1      # Concrete instances, examples, observations
    CONCEPT = 2       # Basic concepts, entities, keywords
    RULE = 3          # Rules, relationships, patterns
    PRINCIPLE = 4     # Principles, models, theories
    PARADIGM = 5      # Paradigms, worldviews, frameworks
    

class VerificationStatus(str, Enum):
    """Verification status of a knowledge node."""
    
    UNVERIFIED = "unverified"       # Not yet verified
    VERIFIED = "verified"           # Verified as accurate
    CONTRADICTED = "contradicted"   # Found to contain contradictions
    OBSOLETE = "obsolete"           # Content is outdated
    

class MetadataConfig(BaseModel):
    """Configurable options for knowledge nodes."""
    
    auto_prune: bool = True  # Whether this node can be auto-pruned
    revival_probability: float = Field(default=1.0, ge=0.0, le=1.0)  # Likelihood of revival if dormant
    importance_decay_rate: float = Field(default=0.01, ge=0.0, le=1.0)  # Daily importance decay rate
    protect_until: Optional[datetime] = None  # Protect from pruning until this time
    

class NodeMetadata(BaseModel):
    """Extended metadata for knowledge nodes."""
    
    source: Optional[str] = Field(default="user_input", description="Knowledge source (e.g., 'user_input', 'reflection', 'exploration')")
    domain: Optional[str] = None  # Knowledge domain or field
    tags: List[str] = Field(default_factory=list)  # Custom tags
    last_accessed: datetime = Field(default_factory=datetime.utcnow)  # Last access time
    access_count: int = Field(default=0)  # Number of times accessed
    config: MetadataConfig = Field(default_factory=MetadataConfig)  # Configurable options
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class Node(BaseModel):
    """Knowledge node representing a concept, entity, keyword, etc."""

    id: StringId = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_id: StringId = Field(..., description="User who owns this node")
    label: str = Field(..., description="Node display label (keyword, entity, concept)")
    type: str = Field(..., description="Node type (e.g., 'keyword', 'concept', 'topic', 'question')")
    summary: Optional[str] = Field(default=None, description="AI-generated node summary")
    content: Optional[str] = Field(default=None, description="Extended node content")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # --- Link back to source ---
    conversation_ids: List[StringId] = Field(default_factory=list, description="List of related conversation IDs")
    message_ids: List[StringId] = Field(default_factory=list, description="List of direct source message IDs")
    
    # --- Lifecycle and Status ---
    status: NodeStatus = Field(default=NodeStatus.ACTIVE, description="Current lifecycle status")
    last_status_change: datetime = Field(default_factory=datetime.utcnow, description="When the status last changed")
    
    # --- Abstraction and Knowledge Structure ---
    abstraction_level: AbstractionLevel = Field(default=AbstractionLevel.CONCEPT, description="Abstraction level (1-5)")
    abstraction_source_ids: List[StringId] = Field(default_factory=list, description="IDs of nodes this abstraction is derived from")
    abstraction_method: Optional[str] = Field(default=None, description="Method used to generate this abstraction (clustering, llm_induction, etc.)")
    generalization_scope: str = Field(default="narrow", description="Scope of this abstraction (narrow, domain, cross-domain)")
    
    # --- Quality and Verification ---
    certainty_score: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence in node accuracy (0.0-1.0)")
    verification_status: VerificationStatus = Field(default=VerificationStatus.UNVERIFIED, description="Verification status")
    verified_by: Optional[str] = Field(default=None, description="Who/what verified this node")
    verified_at: Optional[datetime] = Field(default=None, description="When this node was verified")
    
    # --- Vector Embedding ---
    embedding: Optional[List[float]] = Field(default=None,
                                             description=f"Vector embedding of node content (dimensions: {EMBEDDING_DIM})")
    
    # --- Visual & Structural Info ---
    visual_attributes: Optional[NodeVisualAttributes] = Field(default=None,
                                                             description="Frontend visualization attributes")
    parent_node_id: Optional[StringId] = Field(default=None, description="Parent node ID (for tree structure)")
    topic_cluster_id: Optional[StringId] = Field(default=None, description="Topic tree/main branch identifier")
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0,
                                           description="Node importance score (AI-evaluated or based on connectivity)")
    
    # --- Extended Metadata ---
    metadata: NodeMetadata = Field(default_factory=NodeMetadata, description="Extended metadata")

    # Computed fields
    @computed_field
    def age_days(self) -> float:
        """Calculate the age of this node in days."""
        return (datetime.utcnow() - self.created_at).total_seconds() / (60 * 60 * 24)
    
    @computed_field
    def is_dormant_candidate(self) -> bool:
        """Determine if this node is a candidate for dormancy."""
        min_age = timedelta(days=settings.knowledge_lifecycle.node_min_age_days)
        return (
            self.status == NodeStatus.ACTIVE and
            self.importance_score < settings.knowledge_lifecycle.node_dormancy_threshold and
            (datetime.utcnow() - self.created_at) > min_age and
            self.metadata.config.auto_prune and
            (self.metadata.config.protect_until is None or 
             datetime.utcnow() > self.metadata.config.protect_until)
        )

    # Validators
    @field_validator('embedding')
    def check_embedding_dim(cls, v):
        if v is not None and len(v) != EMBEDDING_DIM:
            raise ValueError(f"Embedding dimension must be {EMBEDDING_DIM}")
        return v

    model_config = {
        'populate_by_name': True,
        'arbitrary_types_allowed': True,
        'json_encoders': {ObjectId: str}
    }


class RelationshipType(str, Enum):
    """Type of relationship between knowledge nodes."""
    
    RELATES_TO = "relates_to"           # General relation
    EXTENDS = "extends"                 # Elaborates or builds upon
    BRANCHES_FROM = "branches_from"     # New direction but related
    PART_OF = "part_of"                 # Component/whole relationship
    CAUSES = "causes"                   # Causation
    EXPLAINS = "explains"               # Explanation
    CONTRADICTS = "contradicts"         # Contradiction
    INSTANCE_OF = "instance_of"         # Specific example of
    ABSTRACTED_BY = "abstracted_by"     # Lower level abstracted to higher
    CROSS_LINKS = "cross_links"         # Connects different domains
    PRECEDES = "precedes"               # Temporal or logical precedence
    MERGED_INTO = "merged_into"         # Indicates merger


class Edge(BaseModel):
    """Relationship edge between knowledge nodes."""

    id: StringId = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_id: StringId = Field(..., description="User who owns this edge")
    source_node_id: StringId = Field(..., description="Source node ID")
    target_node_id: StringId = Field(..., description="Target node ID")
    relationship_type: RelationshipType = Field(..., description="Relationship type")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="Relationship strength or confidence (0.0 to 1.0)")
    context_summary: Optional[str] = Field(default=None, description="Relationship context summary")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    
    # --- Lifecycle fields ---
    is_active: bool = Field(default=True, description="Whether this edge is active")
    access_count: int = Field(default=0, description="Number of times this edge was traversed")
    last_accessed: Optional[datetime] = Field(default=None, description="When this edge was last accessed")
    
    # --- Source fields ---
    conversation_ids: List[StringId] = Field(default_factory=list, description="List of related conversation IDs")
    message_ids: List[StringId] = Field(default_factory=list, description="List of direct source message IDs")
    source: str = Field(default="extraction", description="Source of this relationship (extraction, reflection, user, exploration)")
    
    # --- Quality fields ---
    certainty_score: float = Field(default=0.7, ge=0.0, le=1.0, description="Confidence in relationship accuracy")
    verified: bool = Field(default=False, description="Whether this relationship has been verified")

    model_config = {
        'populate_by_name': True,
        'arbitrary_types_allowed': True,
        'json_encoders': {uuid.UUID: str}
    }


class KnowledgeExtractionResult(BaseModel):
    """Result of knowledge extraction from text."""

    message_id: str = Field(default="", description="Associated message ID") 
    embedding: List[float] = Field(..., description="Vector embedding of content")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted entities")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted relationships")
    summary: str = Field(..., description="Content summary")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Extraction timestamp")
    text: str = Field(default="", description="Original text content")

    model_config = {
        'arbitrary_types_allowed': True
    }


class PlacementAction(str, Enum):
    """Type of placement action."""
    
    CREATE_NEW = "create_new"            # Create a new root node
    CREATE_CHILD = "create_child"        # Create a child node
    UPDATE_EXISTING = "update_existing"  # Update an existing node


class PlacementStrategy(str, Enum):
    """High-level placement strategy."""
    
    NEW_TREE = "new_tree"     # Create a new knowledge tree
    EXTEND = "extend"         # Extend an existing node
    BRANCH = "branch"         # Create a branch from existing node
    

class PlacementDecision(BaseModel):
    """Decision about how to place new knowledge in the graph."""

    placement: PlacementStrategy  # High-level strategy
    action_type: PlacementAction  # Specific action to take
    parent_node_info: Optional[Dict[str, Any]] = None  # Info about parent node if any
    relationship_to_parent: Optional[RelationshipType] = None  # Relationship to parent if creating child
    target_topic_cluster_id: str  # Topic cluster to place in

    model_config = {
        'arbitrary_types_allowed': True
    }


class GraphUpdateResult(BaseModel):
    """Result of updating the knowledge graph."""

    nodes_created: List[str]  # IDs of created nodes
    nodes_updated: List[str]  # IDs of updated nodes
    edges_created: List[str]  # IDs of created edges
    dormant_nodes: List[str] = Field(default_factory=list, description="Nodes made dormant")
    revived_nodes: List[str] = Field(default_factory=list, description="Dormant nodes revived")
    abstractions_created: List[str] = Field(default_factory=list, description="Abstraction nodes created")

    model_config = {
        'arbitrary_types_allowed': True
    }


class ProcessingResult(BaseModel):
    """Result of processing a message for knowledge extraction."""

    analysis: KnowledgeExtractionResult
    placement: PlacementDecision
    updates: GraphUpdateResult

    model_config = {
        'arbitrary_types_allowed': True
    }


class ReflectionStage(str, Enum):
    """Stages in the reflection cycle."""
    
    OBSERVE = "observe"    # Gather information
    ORIENT = "orient"      # Analyze and identify patterns
    DECIDE = "decide"      # Plan actions
    ACT = "act"            # Execute actions
    EVALUATE = "evaluate"  # Assess results


class GapType(str, Enum):
    """Types of knowledge gaps identified during reflection."""
    
    COVERAGE = "coverage"          # Missing topics/areas
    DEPTH = "depth"                # Lack of detailed knowledge
    CONNECTIVITY = "connectivity"  # Poor connections between knowledge
    TIMELINESS = "timeliness"      # Outdated information
    CONSISTENCY = "consistency"    # Contradictions or uncertainties


class KnowledgeGap(BaseModel):
    """Representation of a knowledge gap."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: GapType
    description: str
    topic_id: Optional[StringId] = None
    related_node_ids: List[StringId] = Field(default_factory=list)
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    identified_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="open")  # open, addressing, closed
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class ReflectionTask(BaseModel):
    """Task to be performed during reflection."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # Type of task (abstraction_generation, knowledge_pruning, etc.)
    priority: int = Field(default=0, description="Priority (higher number = higher priority)")
    energy_cost: float  # Energy cost to execute
    parameters: Dict[str, Any] = Field(default_factory=dict)  # Task-specific parameters
    target_node_ids: List[StringId] = Field(default_factory=list)  # Nodes targeted by this task
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class SystemStateSnapshot(BaseModel):
    """Snapshot of system state during reflection."""
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    node_count: int
    edge_count: int
    active_node_count: int
    dormant_node_count: int
    topics_count: int
    avg_node_connectivity: float
    topic_distribution: Dict[str, int]  # Topic ID to node count
    abstraction_level_distribution: Dict[int, int]  # Level to node count
    recently_active_topics: List[StringId]  # Topics with recent activity
    top_accessed_nodes: List[StringId]  # Most accessed nodes
    health_indicators: Dict[str, float]  # Various health indicators
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class AbstractionCluster(BaseModel):
    """Group of related nodes that can form an abstraction."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_node_ids: List[StringId]
    centroid_vector: List[float]
    coherence_score: float
    common_topic_id: Optional[StringId] = None
    suggested_label: str
    suggested_summary: str
    abstraction_level: AbstractionLevel
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class SynthesisType(str, Enum):
    """Type of concept synthesis/innovation."""
    
    ANALOGICAL = "analogical"       # Based on analogy between domains
    INTEGRATIVE = "integrative"     # Integration of multiple concepts
    TRANSFORMATIONAL = "transformational"  # Transform concept to new domain
    DIALECTICAL = "dialectical"     # Synthesize opposing concepts
    CONCEPTUAL_BLENDING = "conceptual_blending"  # Blend multiple concepts


class ConceptSynthesisResult(BaseModel):
    """Result of concept synthesis (innovation)."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    synthesis_type: SynthesisType
    source_concept_ids: List[StringId]
    new_concept_label: str
    new_concept_summary: str
    new_concept_abstraction_level: AbstractionLevel
    evaluation_scores: Dict[str, float]  # novelty, coherence, utility, etc.
    creation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class ReflectionCycle(BaseModel):
    """Record of a complete reflection cycle."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: StringId
    start_time: datetime
    end_time: Optional[datetime] = None
    energy_budget: float
    energy_consumed: float = 0.0
    current_stage: ReflectionStage = ReflectionStage.OBSERVE
    status: str = "in_progress"  # in_progress, completed, error
    identified_gaps: List[KnowledgeGap] = Field(default_factory=list)
    executed_tasks: List[ReflectionTask] = Field(default_factory=list)
    system_state_before: Optional[SystemStateSnapshot] = None
    system_state_after: Optional[SystemStateSnapshot] = None
    error_message: Optional[str] = None
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class StrategyType(str, Enum):
    """Type of learning or system strategy."""
    
    ACQUISITION = "acquisition"     # Knowledge acquisition strategy
    EXTRACTION = "extraction"       # Knowledge extraction strategy 
    PLACEMENT = "placement"         # Knowledge placement strategy
    REFLECTION = "reflection"       # Reflection process strategy
    EXPLORATION = "exploration"     # Active exploration strategy
    PRUNING = "pruning"             # Knowledge pruning strategy


class StrategyAdjustment(BaseModel):
    """Adjustment to a learning or organization strategy."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_type: StrategyType
    parameter_name: str
    old_value: Any
    new_value: Any
    adjustment_reason: str
    adjustment_time: datetime = Field(default_factory=datetime.utcnow)
    reflection_cycle_id: Optional[StringId] = None
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class MetricsRecord(BaseModel):
    """Collection of system metrics at a point in time."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: StringId
    
    # Structure metrics
    node_count: int
    edge_count: int
    topic_count: int
    avg_node_degree: float
    avg_path_length: Optional[float] = None
    graph_density: float
    clustering_coefficient: Optional[float] = None
    connected_components: int
    
    # Content metrics
    avg_certainty_score: float
    verified_node_ratio: float
    dormant_node_ratio: float
    
    # Diversity metrics
    topic_entropy: float  # Shannon entropy of topic distribution
    abstraction_level_distribution: Dict[int, float]  # Level to percentage
    
    # Performance metrics
    avg_query_time_ms: Optional[float] = None
    extraction_success_rate: Optional[float] = None
    
    # Health indicators
    health_score: float  # Overall health score (0-1)
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class ExplorationQuery(BaseModel):
    """Query for active exploration."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: StringId
    query_text: str
    source_gap_id: Optional[StringId] = None  # Knowledge gap that triggered this
    related_node_ids: List[StringId] = Field(default_factory=list)
    priority: int = 0
    status: str = "pending"  # pending, in_progress, completed, failed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    result_summary: Optional[str] = None
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class ExplorationResult(BaseModel):
    """Result of an exploration query."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query_id: StringId
    source_text: str
    source_url: Optional[str] = None
    extracted_content: str
    importance_score: float
    reliability_score: float
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    knowledge_extraction_result: Optional[KnowledgeExtractionResult] = None
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class PerceptionEvent(BaseModel):
    """Event from the perception system."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str  # api_call, scheduled_task, user_interaction, etc.
    source: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {
        'arbitrary_types_allowed': True
    }


class LearningStrategy(BaseModel):
    """Current learning strategy configuration."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: StringId
    
    # Knowledge acquisition preferences
    topic_priorities: Dict[str, float] = Field(default_factory=dict)  # Topic ID to priority
    depth_breadth_balance: float = Field(default=0.5, ge=0.0, le=1.0)  # 0=breadth, 1=depth
    
    # Knowledge extraction parameters  
    extraction_detail_level: str = Field(default="standard")  # minimal, standard, detailed
    
    # Knowledge placement thresholds
    extend_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    branch_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Reflection parameters
    reflection_triggers: List[str] = Field(default_factory=list)  # idle, schedule, threshold
    
    # Last updated
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        'arbitrary_types_allowed': True
    }
