"""Data models for the innovation mechanism.

This module defines the data models used by the concept synthesis and innovation
evaluation components of the knowledge forest system.
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, computed_field

from forest.models import StringId, SynthesisType, AbstractionLevel


class InnovationCriterion(str, Enum):
    """Criteria for evaluating innovations."""
    
    NOVELTY = "novelty"                 # How new and original is the concept
    COHERENCE = "coherence"             # How internally consistent is the concept
    UTILITY = "utility"                  # How useful or valuable is the concept
    COMPATIBILITY = "compatibility"     # How well it fits existing knowledge
    FLEXIBILITY = "flexibility"         # How adaptable is the concept
    SIMPLICITY = "simplicity"           # How elegantly simple is the concept
    EXPLANATORY_POWER = "explanatory_power"  # How well it explains phenomena
    GENERATIVE_POTENTIAL = "generative_potential"  # How many new ideas it can spawn


class InnovationEvaluation(BaseModel):
    """Evaluation of an innovation according to multiple criteria."""
    
    id: StringId = Field(default_factory=lambda: StringId())
    concept_id: StringId
    evaluator: str  # e.g., "ai", "user", "system"
    criteria_scores: Dict[InnovationCriterion, float]  # Scores per criterion (0.0-1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    comments: Optional[str] = None
    
    @computed_field
    def overall_score(self) -> float:
        """Calculate overall score as average of criteria scores."""
        if not self.criteria_scores:
            return 0.0
        return sum(self.criteria_scores.values()) / len(self.criteria_scores)


class SynthesisCandidate(BaseModel):
    """Pair of concepts that are candidates for synthesis."""
    
    id: StringId = Field(default_factory=lambda: StringId())
    source_concept_ids: List[StringId]
    source_concept_labels: List[str]
    similarity_score: float  # How similar the concepts are (0.0-1.0)
    difference_score: float  # How different the concepts are (0.0-1.0)
    complementarity_score: float  # How complementary the concepts are (0.0-1.0)
    synthesis_potential: float  # Overall potential for synthesis (0.0-1.0)
    suggested_synthesis_types: List[SynthesisType]  # Potential synthesis methods
    identified_at: datetime = Field(default_factory=datetime.utcnow)


class SynthesisTask(BaseModel):
    """Task specification for concept synthesis."""
    
    id: StringId = Field(default_factory=lambda: StringId())
    user_id: StringId
    synthesis_type: SynthesisType
    source_concept_ids: List[StringId]
    target_abstraction_level: AbstractionLevel
    creation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    completion_timestamp: Optional[datetime] = None
    status: str = "pending"  # pending, in_progress, completed, failed
    result_concept_id: Optional[StringId] = None
    energy_cost: float = 25.0
    priority: int = 1
    
    
class InnovationHistory(BaseModel):
    """Record of innovation activity for analysis and improvement."""
    
    id: StringId = Field(default_factory=lambda: StringId())
    user_id: StringId
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    activity_type: str  # "candidate_identification", "synthesis", "evaluation"
    synthesis_type: Optional[SynthesisType] = None
    source_concept_ids: List[StringId] = Field(default_factory=list)
    result_concept_id: Optional[StringId] = None
    success: bool
    details: Dict[str, Any] = Field(default_factory=dict)
    energy_consumed: float
