# src/forest/interfaces/monitoring.py
from dataclasses import dataclass, field
from typing import Dict, Any, List, Union
from datetime import datetime
import time

@dataclass
class Metric:
    name: str
    value: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class LogEntry:
    timestamp: datetime
    level: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)

class MonitoringMixin:
    """Mixin class that adds monitoring capabilities to components."""
    
    def __init__(self):
        """Initialize monitoring data structures."""
        self._metrics = {}
        self._errors = {}
        self._latencies = {}
    
    def _record_metric(self, name: str, value: Union[int, float] = 1) -> None:
        """Record a metric.
        
        Args:
            name: Metric name
            value: Metric value (default=1)
        """
        if name not in self._metrics:
            self._metrics[name] = 0
        self._metrics[name] += value
    
    def _record_latency(self, operation: str, seconds: float) -> None:
        """Record operation latency.
        
        Args:
            operation: Operation name
            seconds: Execution time in seconds
        """
        if operation not in self._latencies:
            self._latencies[operation] = []
        self._latencies[operation].append(seconds)
    
    def _record_error(self, operation: str, error_msg: str) -> None:
        """Record an error.
        
        Args:
            operation: Operation name
            error_msg: Error message
        """
        if operation not in self._errors:
            self._errors[operation] = []
        self._errors[operation].append({
            "timestamp": time.time(),
            "message": error_msg
        })
    
    def _get_metrics(self) -> Dict[str, Union[int, float]]:
        """Get all recorded metrics.
        
        Returns:
            Dictionary of metrics
        """
        return self._metrics.copy()
    
    def _get_errors(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all recorded errors.
        
        Returns:
            Dictionary of errors by operation
        """
        return self._errors.copy()
    
    def _get_latencies(self) -> Dict[str, List[float]]:
        """Get all recorded latencies.
        
        Returns:
            Dictionary of latencies by operation
        """
        return self._latencies.copy() 