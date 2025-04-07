"""Energy system data models.

This module defines the data models for the energy management system,
which helps regulate computational resources across the knowledge forest.
"""
from typing import Dict, List, Optional, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator

from src.forest.models import StringId


class EnergyPoolType(str, Enum):
    """Type of energy pool."""
    
    REFLECTION = "reflection"       # For reflection activities
    EXTRACTION = "extraction"       # For knowledge extraction
    PLACEMENT = "placement"         # For knowledge placement
    ABSTRACTION = "abstraction"     # For abstraction generation
    EXPLORATION = "exploration"     # For active exploration
    SYSTEM = "system"               # For system maintenance
    RESERVE = "reserve"             # Reserve energy pool
    

class EnergyTransactionType(str, Enum):
    """Type of energy transaction."""
    
    ALLOCATION = "allocation"       # Allocating energy to a pool
    CONSUMPTION = "consumption"     # Consuming energy from a pool
    REPLENISHMENT = "replenishment" # Adding energy to a pool
    TRANSFER = "transfer"           # Moving energy between pools
    DECAY = "decay"                 # Periodic energy decay
    ADJUSTMENT = "adjustment"       # Manual adjustment


class EnergyAllocation(BaseModel):
    """Represents the allocation of energy across different pools."""
    
    user_id: StringId
    total_energy: float = Field(default=100.0, ge=0.0, description="Total energy in the system")
    
    # Distribution across pools (percentages)
    reflection_pct: float = Field(default=30.0, ge=0.0, le=100.0)
    extraction_pct: float = Field(default=20.0, ge=0.0, le=100.0)
    placement_pct: float = Field(default=15.0, ge=0.0, le=100.0)
    abstraction_pct: float = Field(default=15.0, ge=0.0, le=100.0)
    exploration_pct: float = Field(default=10.0, ge=0.0, le=100.0)
    system_pct: float = Field(default=5.0, ge=0.0, le=100.0)
    reserve_pct: float = Field(default=5.0, ge=0.0, le=100.0)
    
    # Computed absolute amounts based on percentages
    reflection_amount: float = Field(default=0.0, ge=0.0)
    extraction_amount: float = Field(default=0.0, ge=0.0)
    placement_amount: float = Field(default=0.0, ge=0.0)
    abstraction_amount: float = Field(default=0.0, ge=0.0)
    exploration_amount: float = Field(default=0.0, ge=0.0)
    system_amount: float = Field(default=0.0, ge=0.0)
    reserve_amount: float = Field(default=0.0, ge=0.0)
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_replenishment: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('reflection_amount', 'extraction_amount', 'placement_amount', 
              'abstraction_amount', 'exploration_amount', 'system_amount', 
              'reserve_amount', pre=True, always=True)
    def calculate_amounts(cls, v, values):
        """Calculate absolute amounts based on percentages."""
        # Skip if total_energy is not yet available
        if 'total_energy' not in values:
            return 0.0
            
        # Get the field name without _amount suffix
        field_name = None
        for name in ['reflection', 'extraction', 'placement', 'abstraction', 
                    'exploration', 'system', 'reserve']:
            if f'{name}_amount' in values.keys():
                field_name = name
                break
                
        if not field_name:
            return 0.0
            
        # Calculate amount based on percentage
        pct_field = f"{field_name}_pct"
        if pct_field in values:
            return values['total_energy'] * (values[pct_field] / 100.0)
        return 0.0
    
    @validator('reflection_pct', 'extraction_pct', 'placement_pct', 
              'abstraction_pct', 'exploration_pct', 'system_pct', 
              'reserve_pct')
    def check_pct_total(cls, v, values):
        """Ensure percentages sum to 100%."""
        # Only validate after all values are collected
        if 'reserve_pct' in values or values.get('reserve_pct') == v:
            total = sum([
                values.get('reflection_pct', 0),
                values.get('extraction_pct', 0),
                values.get('placement_pct', 0),
                values.get('abstraction_pct', 0),
                values.get('exploration_pct', 0),
                values.get('system_pct', 0),
                values.get('reserve_pct', 0) if 'reserve_pct' not in values else v
            ])
            
            # Allow small floating point variations
            if abs(total - 100.0) > 0.1:
                raise ValueError(f"Energy percentages must sum to 100% (current sum: {total}%)")
        return v
    
    model_config = {
        'arbitrary_types_allowed': True
    }
    
    def get_pool_amount(self, pool_type: EnergyPoolType) -> float:
        """Get the amount of energy in a specific pool.
        
        Args:
            pool_type: The energy pool type
            
        Returns:
            The amount of energy in the pool
        """
        pool_map = {
            EnergyPoolType.REFLECTION: self.reflection_amount,
            EnergyPoolType.EXTRACTION: self.extraction_amount,
            EnergyPoolType.PLACEMENT: self.placement_amount,
            EnergyPoolType.ABSTRACTION: self.abstraction_amount,
            EnergyPoolType.EXPLORATION: self.exploration_amount,
            EnergyPoolType.SYSTEM: self.system_amount,
            EnergyPoolType.RESERVE: self.reserve_amount
        }
        
        return pool_map.get(pool_type, 0.0)


class EnergyTransaction(BaseModel):
    """Record of an energy transaction."""
    
    id: StringId = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    user_id: StringId
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    transaction_type: EnergyTransactionType
    amount: float
    pool: EnergyPoolType
    source_pool: Optional[EnergyPoolType] = None  # For transfers
    component: str  # Which component consumed/allocated the energy
    task_id: Optional[StringId] = None  # Associated task (if any)
    reason: str
    
    model_config = {
        'arbitrary_types_allowed': True
    }
