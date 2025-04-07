"""Energy management system for the knowledge forest.

This module provides functionality for managing energy distribution,
consumption, and replenishment across the knowledge forest system.
Implements the energy allocation, consumption, replenishment, and tracking
systems that simulate biological energy principles in the knowledge forest.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from src.forest.energy.models import (
    EnergyAllocation, EnergyTransaction, 
    EnergyPoolType, EnergyTransactionType
)
from src.forest.models import StringId
from src.storage.mongodb import MongoDBProvider
from src.common.config import get_settings
from src.common.exceptions import EnergyError

settings = get_settings()
logger = logging.getLogger(__name__)


class EnergyManager:
    """Manager for the energy system of the knowledge forest."""
    
    def __init__(self, 
                storage_provider: Optional[MongoDBProvider] = None):
        """Initialize the energy manager.
        
        Args:
            storage_provider: Optional storage provider
        """
        self.storage = storage_provider
        
        # Lazy initialize storage if not provided
        if self.storage is None:
            self.storage = MongoDBProvider()
            
        # Default allocation template
        self.default_allocation = {
            "reflection_pct": 30.0,
            "extraction_pct": 20.0,
            "placement_pct": 15.0,
            "abstraction_pct": 15.0,
            "exploration_pct": 10.0,
            "system_pct": 5.0,
            "reserve_pct": 5.0
        }
        
        # Replenishment settings
        self.replenish_interval = timedelta(hours=1)  # Replenish every hour
        self.replenish_amount = 10.0  # Energy replenished per interval
        self.max_energy = 100.0  # Maximum total energy
        
        # Task scheduling
        self._replenishment_task = None
        self._is_running = False
    
    #--------------------------------------------------------------------------
    # Lifecycle management methods
    #--------------------------------------------------------------------------
    
    async def start(self):
        """Start the energy manager and scheduling tasks."""
        if self._is_running:
            return
            
        logger.info("Starting energy manager")
        self._is_running = True
        
        # Start the replenishment task
        self._replenishment_task = asyncio.create_task(self._run_replenishment_scheduler())
        
    async def stop(self):
        """Stop the energy manager and cancel all tasks."""
        if not self._is_running:
            return
            
        logger.info("Stopping energy manager")
        self._is_running = False
        
        # Cancel the replenishment task
        if self._replenishment_task:
            self._replenishment_task.cancel()
            try:
                await self._replenishment_task
            except asyncio.CancelledError:
                pass
            self._replenishment_task = None
    
    #--------------------------------------------------------------------------
    # Energy allocation and retrieval methods
    #--------------------------------------------------------------------------
    
    async def get_user_energy(self, user_id: str) -> EnergyAllocation:
        """Get the current energy allocation for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Current energy allocation
            
        Raises:
            EnergyError: If retrieval fails
        """
        try:
            # Find existing allocation
            allocations = await self.storage.find_documents(
                "energy_allocations",
                {"user_id": user_id},
                limit=1
            )
            
            if allocations and len(allocations) > 0:
                # Convert to model
                allocation = EnergyAllocation(**allocations[0])
                return allocation
                
            # Create default allocation
            new_allocation = await self._create_default_allocation(user_id)
            return new_allocation
            
        except Exception as e:
            logger.error(f"Failed to get user energy: {str(e)}")
            raise EnergyError(f"Failed to get user energy: {str(e)}")
    
    async def allocate_energy(self, 
                           user_id: str, 
                           allocation: Dict[str, float]) -> EnergyAllocation:
        """Update the energy allocation for a user.
        
        Args:
            user_id: The user ID
            allocation: Dictionary with pool percentages
            
        Returns:
            Updated energy allocation
            
        Raises:
            EnergyError: If allocation fails
        """
        try:
            # Get current allocation
            current = await self.get_user_energy(user_id)
            
            # Update with new values
            update_data = {f"{k}_pct": v for k, v in allocation.items() if k.endswith("_pct")}
            
            # Create updated model to validate
            updated = EnergyAllocation(
                user_id=user_id,
                total_energy=current.total_energy,
                reflection_pct=update_data.get("reflection_pct", current.reflection_pct),
                extraction_pct=update_data.get("extraction_pct", current.extraction_pct),
                placement_pct=update_data.get("placement_pct", current.placement_pct),
                abstraction_pct=update_data.get("abstraction_pct", current.abstraction_pct),
                exploration_pct=update_data.get("exploration_pct", current.exploration_pct),
                system_pct=update_data.get("system_pct", current.system_pct),
                reserve_pct=update_data.get("reserve_pct", current.reserve_pct),
                updated_at=datetime.utcnow(),
                last_replenishment=current.last_replenishment
            )
            
            # Update in database
            await self.storage.update_document(
                "energy_allocations",
                current.id,
                updated.dict(exclude={"id"})
            )
            
            # Record the transaction
            transaction = EnergyTransaction(
                user_id=user_id,
                transaction_type=EnergyTransactionType.ALLOCATION,
                amount=0.0,  # No energy change, just reallocation
                pool=EnergyPoolType.SYSTEM,
                component="energy_manager",
                reason="Manual reallocation of energy pools"
            )
            
            await self.storage.save_document("energy_transactions", transaction.dict())
            
            return updated
            
        except Exception as e:
            logger.error(f"Failed to allocate energy: {str(e)}")
            raise EnergyError(f"Failed to allocate energy: {str(e)}")
    
    #--------------------------------------------------------------------------
    # Energy consumption and transfer methods
    #--------------------------------------------------------------------------
    
    async def consume_energy(self, 
                          user_id: str, 
                          pool: EnergyPoolType, 
                          amount: float,
                          component: str,
                          task_id: Optional[str] = None,
                          reason: str = "Energy consumption") -> Tuple[bool, float]:
        """Consume energy from a specific pool.
        
        Args:
            user_id: The user ID
            pool: The energy pool to consume from
            amount: Amount of energy to consume
            component: Which component is consuming the energy
            task_id: Optional associated task ID
            reason: Reason for consumption
            
        Returns:
            Tuple of (success, remaining_energy)
            
        Raises:
            EnergyError: If consumption fails
        """
        try:
            # Get current allocation
            allocation = await self.get_user_energy(user_id)
            
            # Check if enough energy
            current_amount = allocation.get_pool_amount(pool)
            
            if current_amount < amount:
                # Check if we can use reserve energy
                if pool != EnergyPoolType.RESERVE and allocation.reserve_amount > 0:
                    reserve_amount = min(allocation.reserve_amount, amount - current_amount)
                    
                    # First consume from pool
                    await self._update_pool_energy(user_id, allocation.id, pool, -current_amount)
                    
                    # Then consume from reserve
                    await self._update_pool_energy(user_id, allocation.id, EnergyPoolType.RESERVE, -reserve_amount)
                    
                    # Record both transactions
                    pool_transaction = EnergyTransaction(
                        user_id=user_id,
                        transaction_type=EnergyTransactionType.CONSUMPTION,
                        amount=current_amount,
                        pool=pool,
                        component=component,
                        task_id=task_id,
                        reason=reason
                    )
                    
                    reserve_transaction = EnergyTransaction(
                        user_id=user_id,
                        transaction_type=EnergyTransactionType.TRANSFER,
                        amount=reserve_amount,
                        pool=EnergyPoolType.RESERVE,
                        source_pool=EnergyPoolType.RESERVE,
                        component=component,
                        task_id=task_id,
                        reason=f"Reserve energy used for {pool.value}: {reason}"
                    )
                    
                    await self.storage.save_document("energy_transactions", pool_transaction.dict())
                    await self.storage.save_document("energy_transactions", reserve_transaction.dict())
                    
                    # Return remaining energy (which is zero)
                    return True, 0.0
                    
                # Not enough energy
                return False, current_amount
            
            # Update pool energy
            await self._update_pool_energy(user_id, allocation.id, pool, -amount)
            
            # Record transaction
            transaction = EnergyTransaction(
                user_id=user_id,
                transaction_type=EnergyTransactionType.CONSUMPTION,
                amount=amount,
                pool=pool,
                component=component,
                task_id=task_id,
                reason=reason
            )
            
            await self.storage.save_document("energy_transactions", transaction.dict())
            
            # Return remaining energy
            return True, current_amount - amount
            
        except Exception as e:
            logger.error(f"Failed to consume energy: {str(e)}")
            raise EnergyError(f"Failed to consume energy: {str(e)}")

    async def replenish_energy(self,
                             user_id: str,
                             amount: Optional[float] = None) -> EnergyAllocation:
        """Replenish energy for a user, distributed according to allocation.

        Args:
            user_id: The user ID
            amount: Optional amount to replenish (uses default if None)

        Returns:
            Updated energy allocation

        Raises:
            EnergyError: If replenishment fails
        """
        try:
            # Get current allocation
            allocation = await self.get_user_energy(user_id)

            # Use default amount if not specified
            replenish_amount = amount if amount is not None else self.replenish_amount

            # Check if at max energy
            if allocation.total_energy >= self.max_energy:
                return allocation

            # Cap to max energy
            replenish_amount = min(replenish_amount, self.max_energy - allocation.total_energy)

            # Calculate new total
            new_total = allocation.total_energy + replenish_amount

            # Update all pools according to percentages
            for pool_type in EnergyPoolType:
                pool_pct = getattr(allocation, f"{pool_type.value}_pct", 0)
                pool_amount = replenish_amount * (pool_pct / 100.0)

                # Skip tiny amounts
                if pool_amount < 0.01:
                    continue

                # Update pool
                await self._update_pool_energy(user_id, allocation.id, pool_type, pool_amount)

            # Update total energy and replenishment timestamp
            await self.storage.update_document(
                "energy_allocations",
                allocation.id,
                {
                    "total_energy": new_total,
                    "last_replenishment": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            )

            # Record transaction
            transaction = EnergyTransaction(
                user_id=user_id,
                transaction_type=EnergyTransactionType.REPLENISHMENT,
                amount=replenish_amount,
                pool=EnergyPoolType.SYSTEM,  # System-wide replenishment
                component="energy_manager",
                reason="Periodic energy replenishment"
            )

            await self.storage.save_document("energy_transactions", transaction.dict())

            # Return updated allocation
            return await self.get_user_energy(user_id)

        except Exception as e:
            logger.error(f"Failed to replenish energy: {str(e)}")
            raise EnergyError(f"Failed to replenish energy: {str(e)}")

    async def transfer_energy(self,
                            user_id: str,
                            from_pool: EnergyPoolType,
                            to_pool: EnergyPoolType,
                            amount: float,
                            component: str,
                            reason: str = "Energy transfer") -> bool:
        """Transfer energy between pools.

        Args:
            user_id: The user ID
            from_pool: Source pool
            to_pool: Destination pool
            amount: Amount to transfer
            component: Which component is requesting the transfer
            reason: Reason for transfer

        Returns:
            True if successful

        Raises:
            EnergyError: If transfer fails
        """
        try:
            # Get current allocation
            allocation = await self.get_user_energy(user_id)

            # Check if enough energy
            source_amount = allocation.get_pool_amount(from_pool)

            if source_amount < amount:
                return False

            # Update both pools
            await self._update_pool_energy(user_id, allocation.id, from_pool, -amount)
            await self._update_pool_energy(user_id, allocation.id, to_pool, amount)

            # Record transaction
            transaction = EnergyTransaction(
                user_id=user_id,
                transaction_type=EnergyTransactionType.TRANSFER,
                amount=amount,
                pool=to_pool,
                source_pool=from_pool,
                component=component,
                reason=reason
            )

            await self.storage.save_document("energy_transactions", transaction.dict())

            return True

        except Exception as e:
            logger.error(f"Failed to transfer energy: {str(e)}")
            raise EnergyError(f"Failed to transfer energy: {str(e)}")
    
    #--------------------------------------------------------------------------
    # Energy monitoring and reporting methods
    #--------------------------------------------------------------------------

    async def get_energy_history(self,
                               user_id: str,
                               days: int = 7,
                               limit: int = 100) -> List[Dict[str, Any]]:
        """Get energy transaction history.

        Args:
            user_id: The user ID
            days: Number of days to look back
            limit: Maximum number of transactions to return

        Returns:
            List of energy transactions

        Raises:
            EnergyError: If retrieval fails
        """
        try:
            # Calculate cutoff time
            cutoff = datetime.utcnow() - timedelta(days=days)

            # Find transactions
            transactions = await self.storage.find_documents(
                "energy_transactions",
                {
                    "user_id": user_id,
                    "timestamp": {"$gte": cutoff}
                },
                sort=[("timestamp", -1)],  # Most recent first
                limit=limit
            )

            return transactions

        except Exception as e:
            logger.error(f"Failed to get energy history: {str(e)}")
            raise EnergyError(f"Failed to get energy history: {str(e)}")

    async def get_pool_consumption(self,
                                 user_id: str,
                                 days: int = 7) -> Dict[str, float]:
        """Get energy consumption by pool.

        Args:
            user_id: The user ID
            days: Number of days to look back

        Returns:
            Dict mapping pool type to total consumption

        Raises:
            EnergyError: If retrieval fails
        """
        try:
            # Calculate cutoff time
            cutoff = datetime.utcnow() - timedelta(days=days)

            # Aggregate consumption by pool
            pipeline = [
                {"$match": {
                    "user_id": user_id,
                    "timestamp": {"$gte": cutoff},
                    "transaction_type": "consumption"
                }},
                {"$group": {
                    "_id": "$pool",
                    "total": {"$sum": "$amount"}
                }}
            ]

            result = await self.storage.aggregate("energy_transactions", pipeline)

            # Convert to dict
            consumption = {}
            for item in result:
                pool = item.get("_id")
                if pool:
                    consumption[pool] = item.get("total", 0.0)

            return consumption

        except Exception as e:
            logger.error(f"Failed to get pool consumption: {str(e)}")
            raise EnergyError(f"Failed to get pool consumption: {str(e)}")
    
    #--------------------------------------------------------------------------
    # Energy maintenance methods
    #--------------------------------------------------------------------------

    async def apply_decay(self, user_id: str, decay_rate: float = 0.01) -> None:
        """Apply energy decay to simulate natural energy dissipation.

        Args:
            user_id: The user ID
            decay_rate: Rate of decay (0-1)

        Raises:
            EnergyError: If decay application fails
        """
        try:
            # Get current allocation
            allocation = await self.get_user_energy(user_id)

            # Apply decay to each pool
            for pool_type in EnergyPoolType:
                pool_amount = allocation.get_pool_amount(pool_type)
                decay_amount = pool_amount * decay_rate

                # Skip tiny amounts
                if decay_amount < 0.01:
                    continue

                # Update pool
                await self._update_pool_energy(user_id, allocation.id, pool_type, -decay_amount)

            # Update total energy
            total_decay = allocation.total_energy * decay_rate
            new_total = allocation.total_energy - total_decay

            await self.storage.update_document(
                "energy_allocations",
                allocation.id,
                {
                    "total_energy": new_total,
                    "updated_at": datetime.utcnow()
                }
            )

            # Record transaction
            transaction = EnergyTransaction(
                user_id=user_id,
                transaction_type=EnergyTransactionType.DECAY,
                amount=total_decay,
                pool=EnergyPoolType.SYSTEM,
                component="energy_manager",
                reason="Natural energy decay"
            )

            await self.storage.save_document("energy_transactions", transaction.dict())

        except Exception as e:
            logger.error(f"Failed to apply energy decay: {str(e)}")
            raise EnergyError(f"Failed to apply energy decay: {str(e)}")

    async def rebalance_pools(self, user_id: str) -> None:
        """Rebalance energy pools based on allocation percentages.

        Args:
            user_id: The user ID

        Raises:
            EnergyError: If rebalancing fails
        """
        try:
            # Get current allocation
            allocation = await self.get_user_energy(user_id)

            # Calculate target amounts for each pool
            total_energy = allocation.total_energy
            target_amounts = {}

            for pool_type in EnergyPoolType:
                pool_pct = getattr(allocation, f"{pool_type.value}_pct", 0)
                target_amounts[pool_type.value] = total_energy * (pool_pct / 100.0)

            # Update each pool to match target
            update_data = {}
            for pool_type in EnergyPoolType:
                current = allocation.get_pool_amount(pool_type)
                target = target_amounts[pool_type.value]

                # Only update if significant difference
                if abs(target - current) > 0.1:
                    update_data[f"{pool_type.value}_amount"] = target

            # If we have updates, apply them
            if update_data:
                update_data["updated_at"] = datetime.utcnow()

                await self.storage.update_document(
                    "energy_allocations",
                    allocation.id,
                    update_data
                )

                # Record transaction
                transaction = EnergyTransaction(
                    user_id=user_id,
                    transaction_type=EnergyTransactionType.ADJUSTMENT,
                    amount=0.0,  # No change in total
                    pool=EnergyPoolType.SYSTEM,
                    component="energy_manager",
                    reason="Pool rebalancing"
                )

                await self.storage.save_document("energy_transactions", transaction.dict())

        except Exception as e:
            logger.error(f"Failed to rebalance energy pools: {str(e)}")
            raise EnergyError(f"Failed to rebalance energy pools: {str(e)}")
    
    #--------------------------------------------------------------------------
    # Private helper methods
    #--------------------------------------------------------------------------

    async def _create_default_allocation(self, user_id: str) -> EnergyAllocation:
        """Create default energy allocation for a user.

        Args:
            user_id: The user ID

        Returns:
            Created energy allocation
        """
        # Create allocation
        allocation = EnergyAllocation(
            user_id=user_id,
            total_energy=self.max_energy,
            **self.default_allocation
        )

        # Save to database
        allocation_dict = allocation.dict(exclude={"id"})
        allocation_id = await self.storage.save_document("energy_allocations", allocation_dict)

        # Set the ID
        allocation.id = allocation_id

        logger.info(f"Created default energy allocation for user {user_id}")

        return allocation

    async def _update_pool_energy(self,
                               user_id: str,
                               allocation_id: str,
                               pool: EnergyPoolType,
                               delta: float) -> None:
        """Update energy in a specific pool.

        Args:
            user_id: The user ID
            allocation_id: Allocation document ID
            pool: The energy pool to update
            delta: Amount to add (positive) or subtract (negative)
        """
        # Update the appropriate field
        field_name = f"{pool.value}_amount"

        # Use MongoDB field increment operator
        update = {
            "$inc": {field_name: delta},
            "$set": {"updated_at": datetime.utcnow()}
        }

        await self.storage.update_document(
            "energy_allocations",
            allocation_id,
            update,
            raw_update=True
        )

    async def _run_replenishment_scheduler(self) -> None:
        """Task that periodically replenishes energy for all users."""
        try:
            while self._is_running:
                # Get all users with allocations
                allocations = await self.storage.find_documents(
                    "energy_allocations",
                    {}
                )

                # Check which need replenishment
                now = datetime.utcnow()

                for allocation in allocations:
                    user_id = allocation.get("user_id")
                    last_replenishment = allocation.get("last_replenishment", datetime.min)

                    # Check if due for replenishment
                    if now - last_replenishment >= self.replenish_interval:
                        try:
                            await self.replenish_energy(user_id)
                            logger.debug(f"Replenished energy for user {user_id}")
                        except Exception as e:
                            logger.error(f"Failed to replenish energy for user {user_id}: {str(e)}")

                # Sleep until next check
                await asyncio.sleep(60)  # Check every minute

        except asyncio.CancelledError:
            logger.info("Energy replenishment task cancelled")
        except Exception as e:
            logger.error(f"Error in energy replenishment task: {str(e)}")
