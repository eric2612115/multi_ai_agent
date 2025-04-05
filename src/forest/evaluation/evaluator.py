"""System evaluation and optimization for AI Knowledge Forest.

This module provides functionality for evaluating system health, identifying optimization
opportunities, and implementing improvements to enhance system performance.
"""
import logging
import math
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import json

from common.base_service import BaseService
from common.decorators import track_energy, handle_errors, log_operation
from common.exceptions import EvaluationError, OptimizationError
from storage.mongodb import MongoDBProvider
from forest.energy.manager_combined import EnergyManager
from forest.lifecycle.manager_combined import LifecycleManager
from forest.graph import KnowledgeGraphManager
from forest.reflection.core import ReflectionSystem
from forest.models import MetricsRecord
from forest.evaluation.strategies.parameter_tuning import ParameterTuningStrategy
from forest.evaluation.strategies.resource_allocation import ResourceAllocationStrategy
from common.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class SystemEvaluator(BaseService):
    """System evaluation and optimization manager.
    
    This class is responsible for evaluating system health, identifying optimization
    opportunities, and implementing improvements to enhance system performance.
    """
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None,
                energy_manager: Optional[EnergyManager] = None,
                lifecycle_manager: Optional[LifecycleManager] = None,
                reflection_system: Optional[ReflectionSystem] = None,
                graph_manager: Optional[KnowledgeGraphManager] = None):
        """Initialize the system evaluator.
        
        Args:
            storage_provider: Optional storage provider
            energy_manager: Optional energy manager
            lifecycle_manager: Optional lifecycle manager
            reflection_system: Optional reflection system
            graph_manager: Optional graph manager
        """
        super().__init__("system_evaluator", storage_provider)
        
        self.energy_manager = energy_manager
        self.lifecycle_manager = lifecycle_manager
        self.reflection_system = reflection_system
        self.graph_manager = graph_manager
        
        # Initialize optimization strategies
        self.optimization_strategies = {}
        
        # Experiments in progress
        self.active_experiments = {}
        
        # Performance thresholds
        self.performance_thresholds = {}
    
    async def _initialize(self) -> None:
        """Service-specific initialization."""
        logger.info("Initializing system evaluator")
        
        # Initialize optimization strategies
        self.optimization_strategies = {
            "parameter_tuning": ParameterTuningStrategy(self.storage),
            "resource_allocation": ResourceAllocationStrategy(self.storage)
        }
        
        # Load performance thresholds from database
        await self._load_performance_thresholds()
    
    async def _cleanup(self) -> None:
        """Service-specific cleanup."""
        logger.info("Cleaning up system evaluator")
        
        # Complete any active experiments
        for experiment_id, experiment in self.active_experiments.items():
            await self._complete_experiment(experiment_id, "cancelled")
    
    @track_energy(15.0)
    @handle_errors(EvaluationError)
    @log_operation("collect_system_metrics")
    async def collect_system_metrics(self, user_id: str) -> MetricsRecord:
        """Collect comprehensive system metrics.
        
        Args:
            user_id: The user ID
            
        Returns:
            MetricsRecord containing collected metrics
            
        Raises:
            EvaluationError: If metric collection fails
        """
        logger.info(f"Collecting system metrics for user {user_id}")
        
        try:
            # Collect structure metrics
            structure_metrics = await self._collect_structure_metrics(user_id)
            
            # Collect content metrics
            content_metrics = await self._collect_content_metrics(user_id)
            
            # Collect diversity metrics
            diversity_metrics = await self._collect_diversity_metrics(user_id)
            
            # Collect performance metrics
            performance_metrics = await self._collect_performance_metrics(user_id)
            
            # Calculate overall health score
            health_score = self._calculate_health_score(
                structure_metrics, 
                content_metrics,
                diversity_metrics, 
                performance_metrics
            )
            
            # Create metrics record
            metrics = MetricsRecord(
                user_id=user_id,
                # Structure metrics
                node_count=structure_metrics["node_count"],
                edge_count=structure_metrics["edge_count"],
                topic_count=structure_metrics["topic_count"],
                avg_node_degree=structure_metrics["avg_node_degree"],
                avg_path_length=structure_metrics.get("avg_path_length"),
                graph_density=structure_metrics["graph_density"],
                clustering_coefficient=structure_metrics.get("clustering_coefficient"),
                connected_components=structure_metrics["connected_components"],
                
                # Content metrics
                avg_certainty_score=content_metrics["avg_certainty_score"],
                verified_node_ratio=content_metrics["verified_node_ratio"],
                dormant_node_ratio=content_metrics["dormant_node_ratio"],
                
                # Diversity metrics
                topic_entropy=diversity_metrics["topic_entropy"],
                abstraction_level_distribution=diversity_metrics["abstraction_level_distribution"],
                
                # Performance metrics
                avg_query_time_ms=performance_metrics.get("avg_query_time_ms"),
                extraction_success_rate=performance_metrics.get("extraction_success_rate"),
                
                # Health indicators
                health_score=health_score
            )
            
            # Save metrics to database
            metrics_dict = metrics.model_dump()
            saved_id = await self.storage.save_document("metrics_records", metrics_dict)
            logger.info(f"Saved metrics record with ID {saved_id}")
            
            # Cleanup old metrics
            await self._cleanup_old_metrics(user_id)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {str(e)}")
            raise EvaluationError(f"Failed to collect system metrics: {str(e)}")
    
    @track_energy(10.0)
    @handle_errors(EvaluationError)
    @log_operation("evaluate_system")
    async def evaluate_system(self, user_id: str) -> Dict[str, Any]:
        """Evaluate system health and identify optimization opportunities.
        
        Args:
            user_id: The user ID
            
        Returns:
            Evaluation results
            
        Raises:
            EvaluationError: If evaluation fails
        """
        logger.info(f"Evaluating system for user {user_id}")
        
        try:
            # Collect current metrics
            metrics = await self.collect_system_metrics(user_id)
            metrics_dict = metrics.model_dump()
            
            # Check against thresholds
            threshold_results = await self._check_performance_thresholds(user_id, metrics_dict)
            
            # Run optimization strategies for evaluation only
            strategy_results = {}
            for strategy_name, strategy in self.optimization_strategies.items():
                strategy_results[strategy_name] = await strategy.evaluate(user_id, metrics_dict)
            
            # Calculate overall system trajectory
            trajectory = await self._analyze_system_trajectory(user_id)
            
            # Determine if optimization is needed
            optimization_needed = (
                threshold_results["threshold_violations"] > 0 or
                any(result.get("priority", 0) > 3 for result in strategy_results.values())
            )
            
            # Determine priority areas for optimization
            priority_areas = []
            if threshold_results["threshold_violations"] > 0:
                for violation in threshold_results["violations"]:
                    priority_areas.append({
                        "area": violation["metric_name"],
                        "priority": violation["importance_weight"] * 2, # Multiply by 2 to prioritize threshold violations
                        "reason": f"Below threshold: {violation['metric_name']}"
                    })
            
            for strategy_name, result in strategy_results.items():
                if result.get("priority", 0) > 0:
                    priority_areas.append({
                        "area": strategy_name,
                        "priority": result.get("priority", 0),
                        "reason": f"Optimization opportunity: {strategy_name}"
                    })
            
            # Sort priority areas by priority (descending)
            priority_areas.sort(key=lambda x: x["priority"], reverse=True)
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": metrics_dict,
                "threshold_results": threshold_results,
                "strategy_results": strategy_results,
                "trajectory": trajectory,
                "optimization_needed": optimization_needed,
                "priority_areas": priority_areas[:5],  # Top 5 priority areas
                "overall_health": metrics.health_score
            }
            
        except Exception as e:
            logger.error(f"Error evaluating system: {str(e)}")
            raise EvaluationError(f"Failed to evaluate system: {str(e)}")
    
    @track_energy(20.0)
    @handle_errors(OptimizationError)
    @log_operation("optimize_system")
    async def optimize_system(self, user_id: str, evaluation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize system based on evaluation results.
        
        Args:
            user_id: The user ID
            evaluation_results: Evaluation results
            
        Returns:
            Optimization results
            
        Raises:
            OptimizationError: If optimization fails
        """
        logger.info(f"Optimizing system for user {user_id}")
        
        try:
            # Check if optimization is needed
            if not evaluation_results.get("optimization_needed", False):
                logger.info(f"No optimization needed for user {user_id}")
                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "actions_taken": [],
                    "status": "skipped",
                    "reason": "No optimization needed"
                }
            
            # Check if we can run more experiments
            active_experiment_count = len(await self._get_active_experiments(user_id))
            max_experiments = settings.evaluation.max_concurrent_experiments
            
            if active_experiment_count >= max_experiments:
                logger.info(f"Maximum concurrent experiments reached for user {user_id}")
                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "actions_taken": [],
                    "status": "deferred",
                    "reason": f"Maximum concurrent experiments reached ({max_experiments})"
                }
            
            # Get priority areas
            priority_areas = evaluation_results.get("priority_areas", [])
            if not priority_areas:
                logger.info(f"No priority areas identified for user {user_id}")
                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "actions_taken": [],
                    "status": "skipped",
                    "reason": "No priority areas identified"
                }
            
            # Start optimization experiment
            experiment_id = await self._start_experiment(user_id, priority_areas)
            
            # Select top area to optimize
            top_area = priority_areas[0]
            area_name = top_area["area"]
            
            # Apply optimization based on area
            if area_name in self.optimization_strategies:
                # Get strategy
                strategy = self.optimization_strategies[area_name]
                
                # Get strategy recommendations
                recommendations = evaluation_results.get("strategy_results", {}).get(area_name, {}).get("recommendations", [])
                
                if not recommendations:
                    logger.info(f"No recommendations for strategy {area_name}")
                    await self._complete_experiment(experiment_id, "no_recommendations")
                    return {
                        "timestamp": datetime.utcnow().isoformat(),
                        "actions_taken": [],
                        "status": "skipped",
                        "reason": f"No recommendations for strategy {area_name}",
                        "experiment_id": experiment_id
                    }
                
                # Extract parameters from recommendations
                parameters = {}
                
                if area_name == "parameter_tuning":
                    # For parameter tuning, extract parameters from recommendations
                    for recommendation in recommendations:
                        parameters[recommendation["parameter"]] = recommendation["recommended_value"]
                
                elif area_name == "resource_allocation":
                    # For resource allocation, build component allocations
                    component_allocations = {}
                    for recommendation in recommendations:
                        component_allocations[recommendation["component"]] = recommendation["recommended_allocation"]
                    
                    parameters["component_allocations"] = component_allocations
                
                # Apply optimization
                optimization_result = await strategy.optimize(user_id, parameters)
                
                # Update experiment with results
                await self._update_experiment(experiment_id, {
                    "area_optimized": area_name,
                    "parameters": parameters,
                    "optimization_result": optimization_result,
                    "status": "in_progress"
                })
                
                # Schedule experiment evaluation
                # In a real system, this would be scheduled to run after some time
                # to measure the impact of the optimization
                
                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "actions_taken": [{
                        "area": area_name,
                        "parameters": parameters,
                        "result": optimization_result
                    }],
                    "status": "success",
                    "experiment_id": experiment_id
                }
                
            else:
                # Handle other types of optimizations based on metric violations
                # For now, just log and return
                logger.info(f"No optimization strategy available for area {area_name}")
                await self._complete_experiment(experiment_id, "no_strategy")
                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "actions_taken": [],
                    "status": "skipped",
                    "reason": f"No optimization strategy available for area {area_name}",
                    "experiment_id": experiment_id
                }
                
        except Exception as e:
            logger.error(f"Error optimizing system: {str(e)}")
            raise OptimizationError(f"Failed to optimize system: {str(e)}")
    
    @track_energy(5.0)
    @handle_errors(EvaluationError)
    async def evaluate_experiment(self, user_id: str, experiment_id: str) -> Dict[str, Any]:
        """Evaluate the results of an optimization experiment.
        
        Args:
            user_id: The user ID
            experiment_id: The experiment ID
            
        Returns:
            Experiment evaluation results
            
        Raises:
            EvaluationError: If evaluation fails
        """
        logger.info(f"Evaluating experiment {experiment_id} for user {user_id}")
        
        try:
            # Get experiment
            experiment = await self.storage.find_one(
                "optimization_experiments",
                {"_id": experiment_id, "user_id": user_id}
            )
            
            if not experiment:
                raise EvaluationError(f"Experiment {experiment_id} not found")
            
            # Collect current metrics
            current_metrics = await self.collect_system_metrics(user_id)
            current_metrics_dict = current_metrics.model_dump()
            
            # Compare with baseline metrics
            baseline_metrics = experiment.get("baseline_metrics", {})
            
            # Calculate changes
            changes = {}
            improvement_percentage = {}
            
            for key, current_value in current_metrics_dict.items():
                if key in baseline_metrics and isinstance(current_value, (int, float)):
                    baseline_value = baseline_metrics[key]
                    
                    # Skip if baseline is zero to avoid division by zero
                    if baseline_value == 0:
                        continue
                    
                    # Calculate absolute change
                    changes[key] = current_value - baseline_value
                    
                    # Calculate percentage change
                    improvement_percentage[key] = (changes[key] / baseline_value) * 100
            
            # Calculate overall improvement score
            improvement_metrics = [
                "health_score",
                "avg_node_degree",
                "avg_certainty_score",
                "verified_node_ratio",
                "topic_entropy"
            ]
            
            # Weighted improvement score
            weighted_sum = 0
            total_weight = 0
            
            for metric in improvement_metrics:
                if metric in improvement_percentage:
                    weight = 1.0  # Default weight
                    
                    # Assign weights based on metric importance
                    if metric == "health_score":
                        weight = 3.0
                    elif metric in ["avg_certainty_score", "verified_node_ratio"]:
                        weight = 2.0
                    
                    weighted_sum += improvement_percentage[metric] * weight
                    total_weight += weight
            
            overall_improvement = weighted_sum / total_weight if total_weight > 0 else 0
            
            # Determine success or failure
            success = overall_improvement > 0
            
            # Update experiment with results
            await self.storage.update_document(
                "optimization_experiments",
                experiment_id,
                {
                    "current_metrics": current_metrics_dict,
                    "metric_changes": changes,
                    "improvement_percentage": improvement_percentage,
                    "overall_improvement": overall_improvement,
                    "success": success,
                    "evaluated_at": datetime.utcnow()
                }
            )
            
            # Complete experiment if it's been running long enough
            experiment_age = datetime.utcnow() - experiment.get("start_time", datetime.utcnow())
            if experiment_age > timedelta(hours=settings.evaluation.experiment_timeout_hours):
                await self._complete_experiment(experiment_id, "completed")
            
            return {
                "experiment_id": experiment_id,
                "baseline_metrics": baseline_metrics,
                "current_metrics": current_metrics_dict,
                "changes": changes,
                "improvement_percentage": improvement_percentage,
                "overall_improvement": overall_improvement,
                "success": success
            }
            
        except Exception as e:
            logger.error(f"Error evaluating experiment: {str(e)}")
            raise EvaluationError(f"Failed to evaluate experiment: {str(e)}")
    
    @track_energy(5.0)
    @handle_errors(OptimizationError)
    async def revert_optimization(self, user_id: str, optimization_id: str) -> Dict[str, Any]:
        """Revert an optimization that had negative impact.
        
        Args:
            user_id: The user ID
            optimization_id: The optimization ID
            
        Returns:
            Reversion results
            
        Raises:
            OptimizationError: If reversion fails
        """
        logger.info(f"Reverting optimization {optimization_id} for user {user_id}")
        
        try:
            # Get optimization record
            optimization = await self.storage.find_one(
                "optimizations",
                {"_id": optimization_id, "user_id": user_id}
            )
            
            if not optimization:
                raise OptimizationError(f"Optimization {optimization_id} not found")
            
            # Get strategy
            strategy_name = optimization.get("strategy_name")
            if strategy_name not in self.optimization_strategies:
                raise OptimizationError(f"Strategy {strategy_name} not found")
            
            strategy = self.optimization_strategies[strategy_name]
            
            # Revert optimization
            success = await strategy.revert(user_id, optimization_id)
            
            if not success:
                raise OptimizationError(f"Failed to revert optimization {optimization_id}")
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "optimization_id": optimization_id,
                "success": True,
                "message": f"Successfully reverted optimization {optimization_id}"
            }
            
        except Exception as e:
            logger.error(f"Error reverting optimization: {str(e)}")
            raise OptimizationError(f"Failed to revert optimization: {str(e)}")
    
    def needs_optimization(self, evaluation_results: Dict[str, Any]) -> bool:
        """Determine if system needs optimization based on evaluation results.
        
        Args:
            evaluation_results: Evaluation results
            
        Returns:
            True if optimization is needed
        """
        return evaluation_results.get("optimization_needed", False)
    
    async def _collect_structure_metrics(self, user_id: str) -> Dict[str, Any]:
        """Collect structure metrics for the knowledge graph.
        
        Args:
            user_id: The user ID
            
        Returns:
            Structure metrics
        """
        # Get nodes
        nodes = await self.storage.find_documents(
            "nodes",
            {"user_id": user_id}
        )
        
        # Get edges
        edges = await self.storage.find_documents(
            "edges",
            {"user_id": user_id, "is_active": True}
        )
        
        # Get active nodes
        active_nodes = [node for node in nodes if node.get("status") == "active"]
        
        # Get topics
        topics = set()
        for node in nodes:
            topic_id = node.get("topic_cluster_id")
            if topic_id:
                topics.add(topic_id)
        
        # Calculate metrics
        node_count = len(nodes)
        active_node_count = len(active_nodes)
        edge_count = len(edges)
        topic_count = len(topics)
        
        # Calculate average node degree
        node_degrees = {}
        for edge in edges:
            source_id = edge.get("source_node_id")
            target_id = edge.get("target_node_id")
            
            if source_id not in node_degrees:
                node_degrees[source_id] = 0
            if target_id not in node_degrees:
                node_degrees[target_id] = 0
                
            node_degrees[source_id] += 1
            node_degrees[target_id] += 1
        
        avg_node_degree = sum(node_degrees.values()) / len(node_degrees) if node_degrees else 0
        
        # Calculate graph density
        max_possible_edges = node_count * (node_count - 1) if node_count > 1 else 1
        graph_density = edge_count / max_possible_edges if max_possible_edges > 0 else 0
        
        # Count connected components (simplistic approach)
        # A full graph analysis would be more complex
        visited = set()
        connected_components = 0
        
        # Build adjacency list
        adjacency_list = {}
        for edge in edges:
            source_id = edge.get("source_node_id")
            target_id = edge.get("target_node_id")
            
            if source_id not in adjacency_list:
                adjacency_list[source_id] = []
            if target_id not in adjacency_list:
                adjacency_list[target_id] = []
                
            adjacency_list[source_id].append(target_id)
            adjacency_list[target_id].append(source_id)
        
        # BFS to count components
        for node in nodes:
            node_id = node.get("_id")
            if node_id not in visited and node_id in adjacency_list:
                # BFS
                queue = [node_id]
                while queue:
                    current = queue.pop(0)
                    if current not in visited:
                        visited.add(current)
                        for neighbor in adjacency_list.get(current, []):
                            if neighbor not in visited:
                                queue.append(neighbor)
                connected_components += 1
        
        # Nodes without edges also count as components
        for node in nodes:
            node_id = node.get("_id")
            if node_id not in visited and node_id not in adjacency_list:
                connected_components += 1
                visited.add(node_id)
        
        return {
            "node_count": node_count,
            "active_node_count": active_node_count,
            "edge_count": edge_count,
            "topic_count": topic_count,
            "avg_node_degree": avg_node_degree,
            "graph_density": graph_density,
            "connected_components": connected_components
        }
    
    async def _collect_content_metrics(self, user_id: str) -> Dict[str, Any]:
        """Collect content quality metrics.
        
        Args:
            user_id: The user ID
            
        Returns:
            Content metrics
        """
        # Get nodes
        nodes = await self.storage.find_documents(
            "nodes",
            {"user_id": user_id}
        )
        
        # Get active nodes
        active_nodes = [node for node in nodes if node.get("status") == "active"]
        dormant_nodes = [node for node in nodes if node.get("status") == "dormant"]
        
        # Calculate metrics
        node_count = len(nodes)
        active_node_count = len(active_nodes)
        dormant_node_count = len(dormant_nodes)
        
        # Calculate certainty scores
        total_certainty = sum(node.get("certainty_score", 0) for node in nodes)
        avg_certainty_score = total_certainty / node_count if node_count > 0 else 0
        
        # Calculate verification ratio
        verified_nodes = [node for node in nodes if node.get("verification_status") == "verified"]
        verified_node_ratio = len(verified_nodes) / node_count if node_count > 0 else 0
        
        # Calculate dormant ratio
        dormant_node_ratio = dormant_node_count / node_count if node_count > 0 else 0
        
        return {
            "avg_certainty_score": avg_certainty_score,
            "verified_node_ratio": verified_node_ratio,
            "dormant_node_ratio": dormant_node_ratio
        }
    
    async def _collect_diversity_metrics(self, user_id: str) -> Dict[str, Any]:
        """Collect diversity metrics.
        
        Args:
            user_id: The user ID
            
        Returns:
            Diversity metrics
        """
        # Get nodes
        nodes = await self.storage.find_documents(
            "nodes",
            {"user_id": user_id, "status": "active"}
        )
        
        # Count topics
        topic_counts = {}
        abstraction_levels = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        
        for node in nodes:
            # Count by topic
            topic_id = node.get("topic_cluster_id")
            if topic_id:
                if topic_id not in topic_counts:
                    topic_counts[topic_id] = 0
                topic_counts[topic_id] += 1
            
            # Count by abstraction level
            level = node.get("abstraction_level", 2)  # Default to CONCEPT (2)
            if isinstance(level, str):
                # Convert string enum value to integer
                level_map = {"INSTANCE": 1, "CONCEPT": 2, "RULE": 3, "PRINCIPLE": 4, "PARADIGM": 5}
                level = level_map.get(level, 2)
            
            if level in abstraction_levels:
                abstraction_levels[level] += 1
        
        # Calculate topic entropy (Shannon entropy)
        topic_entropy = 0
        total_nodes = len(nodes)
        
        if total_nodes > 0:
            for count in topic_counts.values():
                p = count / total_nodes
                if p > 0:
                    topic_entropy -= p * math.log2(p)
        
        # Normalize topic entropy (0-1 scale)
        max_entropy = math.log2(len(topic_counts)) if topic_counts else 0
        normalized_entropy = topic_entropy / max_entropy if max_entropy > 0 else 0
        
        # Calculate abstraction level distribution as percentages
        abstraction_level_percentages = {}
        for level, count in abstraction_levels.items():
            abstraction_level_percentages[level] = count / total_nodes if total_nodes > 0 else 0
        
        return {
            "topic_entropy": normalized_entropy,
            "abstraction_level_distribution": abstraction_level_percentages
        }
    
    async def _collect_performance_metrics(self, user_id: str) -> Dict[str, Any]:
        """Collect performance metrics.
        
        Args:
            user_id: The user ID
            
        Returns:
            Performance metrics
        """
        # Get query logs from the past week
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        
        query_logs = await self.storage.find_documents(
            "query_logs",
            {
                "user_id": user_id,
                "timestamp": {"$gte": one_week_ago}
            }
        )
        
        # Get extraction logs from the past week
        extraction_logs = await self.storage.find_documents(
            "extraction_logs",
            {
                "user_id": user_id,
                "timestamp": {"$gte": one_week_ago}
            }
        )
        
        # Calculate average query time
        total_query_time = sum(log.get("elapsed_ms", 0) for log in query_logs)
        avg_query_time = total_query_time / len(query_logs) if query_logs else None
        
        # Calculate extraction success rate
        successful_extractions = sum(1 for log in extraction_logs if log.get("success", False))
        extraction_success_rate = successful_extractions / len(extraction_logs) if extraction_logs else None
        
        return {
            "avg_query_time_ms": avg_query_time,
            "extraction_success_rate": extraction_success_rate
        }
    
    def _calculate_health_score(self, 
                               structure_metrics: Dict[str, Any], 
                               content_metrics: Dict[str, Any], 
                               diversity_metrics: Dict[str, Any], 
                               performance_metrics: Dict[str, Any]) -> float:
        """Calculate overall system health score.
        
        Args:
            structure_metrics: Structure metrics
            content_metrics: Content metrics
            diversity_metrics: Diversity metrics
            performance_metrics: Performance metrics
            
        Returns:
            Health score (0.0 to 1.0)
        """
        # Define weights for each category
        structure_weight = 0.25
        content_weight = 0.30
        diversity_weight = 0.25
        performance_weight = 0.20
        
        # Calculate structure score
        structure_score = 0.0
        if structure_metrics:
            # Graph density (closer to optimal density of ~0.1 is better)
            density = structure_metrics.get("graph_density", 0)
            optimal_density = 0.1
            density_score = 1.0 - min(1.0, abs(density - optimal_density) * 5)
            
            # Node degree (higher is better, up to ~10)
            degree = min(10, structure_metrics.get("avg_node_degree", 0))
            degree_score = degree / 10
            
            # Component ratio (fewer components relative to nodes is better)
            component_ratio = structure_metrics.get("connected_components", 1) / max(1, structure_metrics.get("node_count", 1))
            component_score = 1.0 - min(1.0, component_ratio * 5)
            
            structure_score = (density_score * 0.4) + (degree_score * 0.4) + (component_score * 0.2)
        
        # Calculate content score
        content_score = 0.0
        if content_metrics:
            # Certainty (higher is better)
            certainty_score = content_metrics.get("avg_certainty_score", 0)
            
            # Verification (higher is better)
            verified_score = content_metrics.get("verified_node_ratio", 0)
            
            # Dormancy (lower is better)
            dormant_score = 1.0 - min(1.0, content_metrics.get("dormant_node_ratio", 0) * 2)
            
            content_score = (certainty_score * 0.4) + (verified_score * 0.3) + (dormant_score * 0.3)
        
        # Calculate diversity score
        diversity_score = 0.0
        if diversity_metrics:
            # Topic entropy (higher is better)
            entropy_score = diversity_metrics.get("topic_entropy", 0)
            
            # Abstraction balance (more even distribution is better)
            levels = diversity_metrics.get("abstraction_level_distribution", {})
            level_scores = []
            ideal_distribution = {1: 0.3, 2: 0.3, 3: 0.2, 4: 0.15, 5: 0.05}
            
            for level, ideal in ideal_distribution.items():
                actual = levels.get(level, 0)
                level_scores.append(1.0 - min(1.0, abs(actual - ideal) * 3))
            
            abstraction_score = sum(level_scores) / len(level_scores) if level_scores else 0
            
            diversity_score = (entropy_score * 0.6) + (abstraction_score * 0.4)
        
        # Calculate performance score
        performance_score = 0.0
        if performance_metrics:
            # Query time (lower is better, with 100ms as excellent)
            query_time = performance_metrics.get("avg_query_time_ms", 1000)
            query_score = 1.0 - min(1.0, query_time / 1000)
            
            # Extraction success (higher is better)
            extraction_score = performance_metrics.get("extraction_success_rate", 0.5)
            
            performance_score = (query_score * 0.5) + (extraction_score * 0.5)
        
        # Calculate weighted average
        total_score = (
            (structure_score * structure_weight) +
            (content_score * content_weight) +
            (diversity_score * diversity_weight) +
            (performance_score * performance_weight)
        )
        
        return total_score
    
    async def _load_performance_thresholds(self) -> None:
        """Load performance thresholds from database."""
        # Load global thresholds
        global_thresholds = await self.storage.find_documents(
            "performance_thresholds",
            {"user_id": "global"}
        )
        
        # Store in dictionary for quick access
        for threshold in global_thresholds:
            metric_name = threshold.get("metric_name")
            if metric_name:
                self.performance_thresholds[f"global:{metric_name}"] = threshold
    
    async def _check_performance_thresholds(self, user_id: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Check metrics against performance thresholds.
        
        Args:
            user_id: The user ID
            metrics: Current metrics
            
        Returns:
            Threshold check results
        """
        # Load user-specific thresholds
        user_thresholds = await self.storage.find_documents(
            "performance_thresholds",
            {"user_id": user_id}
        )
        
        # Add user thresholds to dictionary
        for threshold in user_thresholds:
            metric_name = threshold.get("metric_name")
            if metric_name:
                self.performance_thresholds[f"{user_id}:{metric_name}"] = threshold
        
        # Check metrics against thresholds
        violations = []
        satisfactory = []
        
        # First check user-specific thresholds
        for metric_name, value in metrics.items():
            if not isinstance(value, (int, float)):
                continue
                
            # Check user threshold first
            threshold_key = f"{user_id}:{metric_name}"
            threshold = self.performance_thresholds.get(threshold_key)
            
            # Fall back to global threshold if no user threshold
            if not threshold:
                threshold_key = f"global:{metric_name}"
                threshold = self.performance_thresholds.get(threshold_key)
            
            if not threshold:
                continue
            
            min_threshold = threshold.get("min_threshold")
            max_threshold = threshold.get("max_threshold")
            target_value = threshold.get("target_value")
            importance_weight = threshold.get("importance_weight", 1.0)
            
            # Check against min threshold
            if min_threshold is not None and value < min_threshold:
                violations.append({
                    "metric_name": metric_name,
                    "current_value": value,
                    "threshold_value": min_threshold,
                    "type": "min",
                    "importance_weight": importance_weight
                })
                continue
            
            # Check against max threshold
            if max_threshold is not None and value > max_threshold:
                violations.append({
                    "metric_name": metric_name,
                    "current_value": value,
                    "threshold_value": max_threshold,
                    "type": "max",
                    "importance_weight": importance_weight
                })
                continue
            
            # Check against target value
            if target_value is not None:
                # Calculate how far we are from target (as a percentage)
                if value == 0:  # Avoid division by zero
                    deviation_pct = 100
                else:
                    deviation_pct = abs(value - target_value) / abs(value) * 100
                
                # If we're more than 20% off target, it's a violation
                if deviation_pct > 20:
                    violations.append({
                        "metric_name": metric_name,
                        "current_value": value,
                        "threshold_value": target_value,
                        "type": "target",
                        "deviation_percentage": deviation_pct,
                        "importance_weight": importance_weight
                    })
                    continue
            
            # If we get here, the metric is satisfactory
            satisfactory.append({
                "metric_name": metric_name,
                "current_value": value
            })
        
        return {
            "threshold_violations": len(violations),
            "violations": violations,
            "satisfactory": satisfactory
        }
    
    async def _analyze_system_trajectory(self, user_id: str) -> Dict[str, Any]:
        """Analyze system trajectory over time.
        
        Args:
            user_id: The user ID
            
        Returns:
            Trajectory analysis
        """
        # Get metrics history (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        metrics_history = await self.storage.find_documents(
            "metrics_records",
            {
                "user_id": user_id,
                "timestamp": {"$gte": thirty_days_ago}
            },
            sort=[("timestamp", 1)]
        )
        
        if not metrics_history:
            return {
                "trend": "unknown",
                "stability": "unknown",
                "growth_rate": 0.0,
                "health_trend": "stable",
                "anomalies": []
            }
        
        # Extract key metrics for trend analysis
        health_scores = []
        node_counts = []
        timestamps = []
        
        for metrics in metrics_history:
            health_scores.append(metrics.get("health_score", 0.5))
            node_counts.append(metrics.get("node_count", 0))
            timestamps.append(metrics.get("timestamp", datetime.utcnow()))
        
        # Calculate health trend
        health_trend = "stable"
        if len(health_scores) >= 3:
            # Calculate linear regression slope
            n = len(health_scores)
            sum_x = sum(range(n))
            sum_y = sum(health_scores)
            sum_xy = sum(i*y for i, y in enumerate(health_scores))
            sum_xx = sum(i*i for i in range(n))
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x) if (n * sum_xx - sum_x * sum_x) != 0 else 0
            
            if slope > 0.01:
                health_trend = "improving"
            elif slope < -0.01:
                health_trend = "declining"
        
        # Calculate growth rate
        growth_rate = 0.0
        if len(node_counts) >= 2:
            first_count = node_counts[0]
            last_count = node_counts[-1]
            days = (timestamps[-1] - timestamps[0]).days or 1  # Avoid division by zero
            
            if first_count > 0:
                total_growth_pct = (last_count - first_count) / first_count
                growth_rate = total_growth_pct / days  # Daily growth rate
        
        # Check for stability (coefficient of variation)
        stability = "stable"
        if len(health_scores) >= 3:
            mean = sum(health_scores) / len(health_scores)
            variance = sum((x - mean) ** 2 for x in health_scores) / len(health_scores)
            std_dev = variance ** 0.5
            
            cv = std_dev / mean if mean > 0 else 0
            
            if cv > 0.2:
                stability = "unstable"
            elif cv < 0.05:
                stability = "very_stable"
        
        # Detect anomalies (simple z-score method)
        anomalies = []
        if len(health_scores) >= 5:
            mean = sum(health_scores) / len(health_scores)
            variance = sum((x - mean) ** 2 for x in health_scores) / len(health_scores)
            std_dev = variance ** 0.5
            
            for i, score in enumerate(health_scores):
                z_score = (score - mean) / std_dev if std_dev > 0 else 0
                
                if abs(z_score) > 2:
                    anomalies.append({
                        "timestamp": timestamps[i].isoformat(),
                        "health_score": score,
                        "z_score": z_score
                    })
        
        # Determine overall trend
        trend = "growing" if growth_rate > 0.01 else "stable" if growth_rate >= 0 else "shrinking"
        
        return {
            "trend": trend,
            "stability": stability,
            "growth_rate": growth_rate,
            "health_trend": health_trend,
            "anomalies": anomalies
        }
    
    async def _cleanup_old_metrics(self, user_id: str) -> None:
        """Clean up old metrics records.
        
        Args:
            user_id: The user ID
        """
        retention_days = settings.evaluation.metrics_retention_days
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        await self.storage.delete_documents(
            "metrics_records",
            {
                "user_id": user_id,
                "timestamp": {"$lt": cutoff_date}
            }
        )
    
    async def _start_experiment(self, user_id: str, priority_areas: List[Dict[str, Any]]) -> str:
        """Start a new optimization experiment.
        
        Args:
            user_id: The user ID
            priority_areas: Priority areas for optimization
            
        Returns:
            Experiment ID
        """
        # Collect baseline metrics
        baseline_metrics = await self.collect_system_metrics(user_id)
        baseline_metrics_dict = baseline_metrics.model_dump()
        
        # Create experiment record
        experiment = {
            "user_id": user_id,
            "name": f"Optimization experiment {datetime.utcnow().isoformat()}",
            "description": f"Automatic optimization experiment for priority areas: {', '.join(area['area'] for area in priority_areas[:3])}",
            "start_time": datetime.utcnow(),
            "status": "starting",
            "priority_areas": priority_areas,
            "baseline_metrics": baseline_metrics_dict,
            "parameters": {}
        }
        
        # Save experiment
        experiment_id = await self.storage.save_document("optimization_experiments", experiment)
        
        # Add to active experiments
        self.active_experiments[str(experiment_id)] = experiment
        
        return str(experiment_id)
    
    async def _update_experiment(self, experiment_id: str, updates: Dict[str, Any]) -> None:
        """Update an optimization experiment.
        
        Args:
            experiment_id: The experiment ID
            updates: Updates to apply
        """
        await self.storage.update_document(
            "optimization_experiments",
            experiment_id,
            updates
        )
        
        # Update in-memory cache
        if experiment_id in self.active_experiments:
            for key, value in updates.items():
                self.active_experiments[experiment_id][key] = value
    
    async def _complete_experiment(self, experiment_id: str, status: str) -> None:
        """Complete an optimization experiment.
        
        Args:
            experiment_id: The experiment ID
            status: Completion status
        """
        await self.storage.update_document(
            "optimization_experiments",
            experiment_id,
            {
                "end_time": datetime.utcnow(),
                "status": status
            }
        )
        
        # Remove from active experiments
        if experiment_id in self.active_experiments:
            del self.active_experiments[experiment_id]
    
    async def _get_active_experiments(self, user_id: str) -> List[Dict[str, Any]]:
        """Get active experiments for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of active experiments
        """
        return await self.storage.find_documents(
            "optimization_experiments",
            {
                "user_id": user_id,
                "status": {"$in": ["starting", "in_progress"]}
            }
        )