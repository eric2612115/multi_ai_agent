"""Strategy pattern implementation for AI Knowledge Forest.

This module provides a generic strategy pattern implementation that can be used
across different components of the system for implementing various algorithms.
"""
import logging
from typing import Dict, Type, TypeVar, Generic, Any, Optional, List, Protocol, runtime_checkable

# Generic type for strategy context
C = TypeVar('C')
# Generic type for strategy result
R = TypeVar('R')
# Generic type for strategy identifiers
ID = TypeVar('ID')

logger = logging.getLogger(__name__)

@runtime_checkable
class Strategy(Protocol[C, R]):
    """Protocol defining the interface for strategy objects."""
    
    def execute(self, context: C) -> R:
        """Execute the strategy.
        
        Args:
            context: Context data for strategy execution
            
        Returns:
            Result of strategy execution
        """
        ...


class StrategyManager(Generic[ID, C, R]):
    """Manager for selecting and executing strategies.
    
    This class implements the strategy pattern, allowing for registration and
    execution of different strategies based on an identifier.
    """
    
    def __init__(self, default_strategy: Optional[ID] = None):
        """Initialize the strategy manager.
        
        Args:
            default_strategy: Optional default strategy to use if not specified
        """
        self._strategies: Dict[ID, Strategy[C, R]] = {}
        self._default_strategy = default_strategy
    
    def register(self, strategy_id: ID, strategy: Strategy[C, R]) -> None:
        """Register a strategy with the manager.
        
        Args:
            strategy_id: Identifier for the strategy
            strategy: The strategy to register
        """
        self._strategies[strategy_id] = strategy
    
    def execute(self, strategy_id: Optional[ID] = None, context: C = None) -> R:
        """Execute a strategy.
        
        Args:
            strategy_id: Identifier for the strategy (uses default if not specified)
            context: Context data for strategy execution
            
        Returns:
            Result of strategy execution
            
        Raises:
            ValueError: If the strategy is not registered
        """
        # Use default strategy if not specified
        if strategy_id is None:
            if self._default_strategy is None:
                raise ValueError("No strategy_id specified and no default strategy registered")
            strategy_id = self._default_strategy
            
        # Get the strategy
        strategy = self._strategies.get(strategy_id)
        if strategy is None:
            raise ValueError(f"Unknown strategy: {strategy_id}")
            
        # Execute and return the result
        return strategy.execute(context)
    
    def get_registered_strategies(self) -> List[ID]:
        """Get all registered strategies.
        
        Returns:
            List of registered strategy identifiers
        """
        return list(self._strategies.keys())
    
    def is_registered(self, strategy_id: ID) -> bool:
        """Check if a strategy is registered.
        
        Args:
            strategy_id: Identifier for the strategy
            
        Returns:
            True if the strategy is registered
        """
        return strategy_id in self._strategies


class ChainedStrategy(Generic[C, R]):
    """Strategy that chains multiple strategies together.
    
    This strategy executes a list of strategies in sequence, passing the result
    of each strategy as input to the next.
    """
    
    def __init__(self, strategies: List[Strategy[C, R]]):
        """Initialize the chained strategy.
        
        Args:
            strategies: List of strategies to execute in sequence
        """
        self.strategies = strategies
    
    def execute(self, context: C) -> R:
        """Execute the strategies in sequence.
        
        Args:
            context: Initial context data for strategy execution
            
        Returns:
            Result of the final strategy execution
        """
        current_context = context
        
        for strategy in self.strategies:
            try:
                current_context = strategy.execute(current_context)
            except Exception as e:
                logger.error(f"Error executing strategy {strategy.__class__.__name__}: {str(e)}")
                raise
        
        return current_context


class CompositeStrategy(Generic[C, R]):
    """Strategy that combines results from multiple strategies.
    
    This strategy executes multiple strategies in parallel and combines their
    results using a combiner function.
    """
    
    def __init__(self, strategies: List[Strategy[C, R]], combiner: callable):
        """Initialize the composite strategy.
        
        Args:
            strategies: List of strategies to execute
            combiner: Function that combines strategy results into a single result
        """
        self.strategies = strategies
        self.combiner = combiner
    
    def execute(self, context: C) -> R:
        """Execute the strategies and combine their results.
        
        Args:
            context: Context data for strategy execution
            
        Returns:
            Combined result from all strategies
        """
        results = []
        
        for strategy in self.strategies:
            try:
                result = strategy.execute(context)
                results.append(result)
            except Exception as e:
                logger.error(f"Error executing strategy {strategy.__class__.__name__}: {str(e)}")
                # Continue with other strategies
        
        # Combine the results
        return self.combiner(results)


class ConditionalStrategy(Generic[C, R]):
    """Strategy that selects from multiple strategies based on conditions.
    
    This strategy evaluates conditions to determine which strategy to execute.
    """
    
    def __init__(self, condition_strategies: List[tuple[callable, Strategy[C, R]]], default_strategy: Optional[Strategy[C, R]] = None):
        """Initialize the conditional strategy.
        
        Args:
            condition_strategies: List of (condition, strategy) tuples
            default_strategy: Strategy to use if no conditions match
        """
        self.condition_strategies = condition_strategies
        self.default_strategy = default_strategy
    
    def execute(self, context: C) -> R:
        """Execute the appropriate strategy based on conditions.
        
        Args:
            context: Context data for strategy execution
            
        Returns:
            Result of the selected strategy execution
            
        Raises:
            ValueError: If no conditions match and no default strategy is provided
        """
        # Evaluate conditions to find the right strategy
        for condition, strategy in self.condition_strategies:
            if condition(context):
                return strategy.execute(context)
        
        # No conditions matched, use default if available
        if self.default_strategy:
            return self.default_strategy.execute(context)
        
        raise ValueError("No conditions matched and no default strategy provided")
