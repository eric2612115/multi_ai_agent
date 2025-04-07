"""WebSocket security manager.

This module provides security functionality for WebSocket connections,
including rate limiting, IP filtering, and abuse protection.
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
import json
import ipaddress

from fastapi import WebSocket, status
from src.common.config import get_settings

# Setup logging
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Default security settings
MAX_CONNECTIONS_PER_IP = int(getattr(settings, "MAX_CONNECTIONS_PER_IP", "50"))
RATE_LIMIT_REQUESTS = int(getattr(settings, "RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(getattr(settings, "RATE_LIMIT_WINDOW", "60"))  # seconds
CONNECTION_BURST_LIMIT = int(getattr(settings, "CONNECTION_BURST_LIMIT", "10"))
CONNECTION_BURST_WINDOW = int(getattr(settings, "CONNECTION_BURST_WINDOW", "10"))  # seconds

class SecurityManager:
    """Security manager for WebSocket connections.
    
    Provides:
    - Rate limiting
    - IP filtering
    - Abuse detection
    - Blacklisting
    - Security event logging
    """
    
    def __init__(self):
        """Initialize the security manager."""
        self.blacklisted_ips: Set[str] = set()
        self.suspicious_ips: Dict[str, float] = {}  # IP -> suspicion score
        self.ip_connection_count: Dict[str, int] = {}
        self.rate_limit_counters: Dict[str, List[datetime]] = {}
        self.connection_history: Dict[str, List[datetime]] = {}
        self.security_lock = asyncio.Lock()
        self.redis_client = None
        self.distributed_mode = getattr(settings, "USE_DISTRIBUTED_MODE", False)
        
        # Load whitelist networks
        self.whitelisted_networks = []
        whitelist_str = getattr(settings, "IP_WHITELIST", "127.0.0.1/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16")
        for network_str in whitelist_str.split(','):
            try:
                network = ipaddress.ip_network(network_str.strip())
                self.whitelisted_networks.append(network)
            except ValueError:
                logger.warning(f"Invalid IP network in whitelist: {network_str}")
    
    async def initialize(self):
        """Initialize the security manager."""
        if self.distributed_mode:
            try:
                import redis.asyncio as redis
                redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
                self.redis_client = redis.from_url(redis_url)
                await self.redis_client.ping()
                
                # Load blacklisted IPs from Redis
                await self._load_blacklist_from_redis()
                
                logger.info("Security manager initialized with Redis backend")
            except ImportError:
                logger.warning("Redis package not available, using in-memory security manager")
                self.distributed_mode = False
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                logger.warning("Falling back to in-memory security manager")
                self.distributed_mode = False
        
        if not self.distributed_mode:
            logger.info("Security manager initialized with in-memory backend")
    
    async def _load_blacklist_from_redis(self):
        """Load blacklisted IPs from Redis."""
        if not self.redis_client:
            return
            
        try:
            # Get all blacklisted IPs
            blacklist_key = "ws_security:blacklisted_ips"
            blacklisted_ips = await self.redis_client.smembers(blacklist_key)
            
            # Update local cache
            self.blacklisted_ips = set(ip.decode('utf-8') for ip in blacklisted_ips)
            
            logger.info(f"Loaded {len(self.blacklisted_ips)} blacklisted IPs from Redis")
        except Exception as e:
            logger.error(f"Error loading blacklist from Redis: {str(e)}")
    
    async def allow_connection(self, user_id: str, client_ip: Optional[str], websocket: WebSocket) -> bool:
        """Check if a connection should be allowed.
        
        Args:
            user_id: User ID.
            client_ip: Client IP address.
            websocket: WebSocket connection.
            
        Returns:
            True if connection is allowed, False otherwise.
        """
        if not client_ip:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing client IP")
            return False
        
        # Check if IP is in a whitelisted network
        try:
            ip_obj = ipaddress.ip_address(client_ip)
            for network in self.whitelisted_networks:
                if ip_obj in network:
                    logger.debug(f"Connection from {client_ip} allowed (whitelisted network)")
                    return True
        except ValueError:
            logger.warning(f"Invalid IP address format: {client_ip}")
        
        async with self.security_lock:
            # Check if IP is blacklisted
            if client_ip in self.blacklisted_ips:
                logger.warning(f"Connection from {client_ip} rejected (blacklisted)")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="IP address is blacklisted")
                return False
            
            # Check distributed blacklist if enabled
            if self.distributed_mode and self.redis_client:
                blacklist_key = "ws_security:blacklisted_ips"
                is_blacklisted = await self.redis_client.sismember(blacklist_key, client_ip)
                if is_blacklisted:
                    # Update local cache
                    self.blacklisted_ips.add(client_ip)
                    logger.warning(f"Connection from {client_ip} rejected (distributed blacklist)")
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="IP address is blacklisted")
                    return False
            
            # Check connection rate limiting
            if client_ip in self.connection_history:
                recent_connections = [
                    ts for ts in self.connection_history[client_ip]
                    if (datetime.now() - ts).total_seconds() < CONNECTION_BURST_WINDOW
                ]
                
                if len(recent_connections) >= CONNECTION_BURST_LIMIT:
                    logger.warning(f"Connection burst limit exceeded for {client_ip}")
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Connection rate limit exceeded")
                    
                    # Increase suspicion score
                    self.suspicious_ips[client_ip] = self.suspicious_ips.get(client_ip, 0) + 1
                    
                    # Check if IP should be blacklisted
                    if self.suspicious_ips[client_ip] >= 3:
                        await self.blacklist_ip(client_ip, reason="Repeated connection bursts")
                    
                    return False
                
                # Update connection history
                self.connection_history[client_ip] = recent_connections + [datetime.now()]
            else:
                self.connection_history[client_ip] = [datetime.now()]
            
            # Track connection count
            self.ip_connection_count[client_ip] = self.ip_connection_count.get(client_ip, 0) + 1
            
            # Check max connections per IP
            if self.ip_connection_count[client_ip] > MAX_CONNECTIONS_PER_IP:
                logger.warning(f"Too many connections from {client_ip}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Too many connections from this IP")
                
                # Increase suspicion score
                self.suspicious_ips[client_ip] = self.suspicious_ips.get(client_ip, 0) + 1
                
                # Check if IP should be blacklisted
                if self.suspicious_ips[client_ip] >= 3:
                    await self.blacklist_ip(client_ip, reason="Too many simultaneous connections")
                
                return False
        
        return True
    
    async def track_disconnection(self, user_id: str, client_ip: Optional[str] = None):
        """Track a client disconnection.
        
        Args:
            user_id: User ID.
            client_ip: Client IP address.
        """
        if not client_ip:
            return
            
        async with self.security_lock:
            # Update connection count
            if client_ip in self.ip_connection_count:
                self.ip_connection_count[client_ip] = max(0, self.ip_connection_count[client_ip] - 1)
    
    async def check_rate_limit(self, user_id: str, client_ip: Optional[str]) -> bool:
        """Check if a user or IP has exceeded rate limits.
        
        Args:
            user_id: User ID.
            client_ip: Client IP address.
            
        Returns:
            True if rate limit exceeded, False otherwise.
        """
        now = datetime.now()
        
        # Check user rate limit
        if user_id:
            async with self.security_lock:
                if user_id not in self.rate_limit_counters:
                    self.rate_limit_counters[user_id] = []
                
                # Clean up old timestamps
                self.rate_limit_counters[user_id] = [
                    ts for ts in self.rate_limit_counters[user_id] 
                    if (now - ts).total_seconds() < RATE_LIMIT_WINDOW
                ]
                
                # Check if limit exceeded
                if len(self.rate_limit_counters[user_id]) >= RATE_LIMIT_REQUESTS:
                    logger.warning(f"Rate limit exceeded for user {user_id}")
                    return True
                
                # Add current timestamp
                self.rate_limit_counters[user_id].append(now)
        
        # Check IP rate limit if client_ip is provided
        if client_ip:
            rate_limit_key = f"ip:{client_ip}"
            
            async with self.security_lock:
                if rate_limit_key not in self.rate_limit_counters:
                    self.rate_limit_counters[rate_limit_key] = []
                
                # Clean up old timestamps
                self.rate_limit_counters[rate_limit_key] = [
                    ts for ts in self.rate_limit_counters[rate_limit_key] 
                    if (now - ts).total_seconds() < RATE_LIMIT_WINDOW
                ]
                
                # Check if limit exceeded
                if len(self.rate_limit_counters[rate_limit_key]) >= RATE_LIMIT_REQUESTS:
                    logger.warning(f"Rate limit exceeded for IP {client_ip}")
                    
                    # Increase suspicion score
                    self.suspicious_ips[client_ip] = self.suspicious_ips.get(client_ip, 0) + 1
                    
                    # Check if IP should be blacklisted
                    if self.suspicious_ips[client_ip] >= 5:
                        await self.blacklist_ip(client_ip, reason="Repeated rate limit violations")
                    
                    return True
                
                # Add current timestamp
                self.rate_limit_counters[rate_limit_key].append(now)
        
        return False
    
    async def blacklist_ip(self, ip_address: str, reason: str = "Security violation") -> bool:
        """Add an IP address to the blacklist.
        
        Args:
            ip_address: IP address to blacklist.
            reason: Reason for blacklisting.
            
        Returns:
            True if successful, False otherwise.
        """
        if not ip_address:
            return False
        
        # Skip whitelisted IPs
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            for network in self.whitelisted_networks:
                if ip_obj in network:
                    logger.warning(f"Attempted to blacklist whitelisted IP: {ip_address}")
                    return False
        except ValueError:
            logger.warning(f"Invalid IP address format: {ip_address}")
            return False
        
        # Add to local blacklist
        async with self.security_lock:
            self.blacklisted_ips.add(ip_address)
        
        # Log security event
        logger.warning(f"IP {ip_address} blacklisted: {reason}")
        
        # Add to distributed blacklist if enabled
        if self.distributed_mode and self.redis_client:
            try:
                # Add to Redis set
                blacklist_key = "ws_security:blacklisted_ips"
                await self.redis_client.sadd(blacklist_key, ip_address)
                
                # Log security event
                security_log_key = "ws_security:events"
                event = {
                    "timestamp": datetime.now().isoformat(),
                    "event_type": "ip_blacklisted",
                    "ip_address": ip_address,
                    "reason": reason
                }
                
                await self.redis_client.lpush(security_log_key, json.dumps(event))
                await self.redis_client.ltrim(security_log_key, 0, 999)  # Keep last 1000 events
                
                # Publish security event
                await self.redis_client.publish(
                    "ws_security",
                    json.dumps({
                        "action": "ip_blacklisted",
                        "ip_address": ip_address,
                        "reason": reason,
                        "timestamp": datetime.now().isoformat()
                    })
                )
            except Exception as e:
                logger.error(f"Error adding IP to distributed blacklist: {str(e)}")
        
        return True
    
    async def unblacklist_ip(self, ip_address: str) -> bool:
        """Remove an IP address from the blacklist.
        
        Args:
            ip_address: IP address to unblacklist.
            
        Returns:
            True if successful, False otherwise.
        """
        if not ip_address:
            return False
        
        # Remove from local blacklist
        async with self.security_lock:
            if ip_address in self.blacklisted_ips:
                self.blacklisted_ips.remove(ip_address)
            
            # Clear suspicion score
            if ip_address in self.suspicious_ips:
                del self.suspicious_ips[ip_address]
        
        # Log security event
        logger.info(f"IP {ip_address} removed from blacklist")
        
        # Remove from distributed blacklist if enabled
        if self.distributed_mode and self.redis_client:
            try:
                # Remove from Redis set
                blacklist_key = "ws_security:blacklisted_ips"
                await self.redis_client.srem(blacklist_key, ip_address)
                
                # Log security event
                security_log_key = "ws_security:events"
                event = {
                    "timestamp": datetime.now().isoformat(),
                    "event_type": "ip_unblacklisted",
                    "ip_address": ip_address
                }
                
                await self.redis_client.lpush(security_log_key, json.dumps(event))
                
                # Publish security event
                await self.redis_client.publish(
                    "ws_security",
                    json.dumps({
                        "action": "ip_unblacklisted",
                        "ip_address": ip_address,
                        "timestamp": datetime.now().isoformat()
                    })
                )
            except Exception as e:
                logger.error(f"Error removing IP from distributed blacklist: {str(e)}")
        
        return True
    
    async def get_blacklisted_ips(self) -> Set[str]:
        """Get all blacklisted IP addresses.
        
        Returns:
            Set of blacklisted IP addresses.
        """
        # If in distributed mode, get from Redis
        if self.distributed_mode and self.redis_client:
            try:
                blacklist_key = "ws_security:blacklisted_ips"
                blacklisted_ips = await self.redis_client.smembers(blacklist_key)
                
                # Update local cache
                self.blacklisted_ips = set(ip.decode('utf-8') for ip in blacklisted_ips)
            except Exception as e:
                logger.error(f"Error getting blacklisted IPs from Redis: {str(e)}")
        
        return self.blacklisted_ips
    
    async def log_security_event(self, event_type: str, details: Dict[str, Any]) -> bool:
        """Log a security event.
        
        Args:
            event_type: Type of security event.
            details: Event details.
            
        Returns:
            True if successful, False otherwise.
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            **details
        }
        
        # Log locally
        logger.warning(f"Security event: {event_type} - {details}")
        
        # Log to Redis if enabled
        if self.distributed_mode and self.redis_client:
            try:
                security_log_key = "ws_security:events"
                await self.redis_client.lpush(security_log_key, json.dumps(event))
                await self.redis_client.ltrim(security_log_key, 0, 999)  # Keep last 1000 events
                
                # Publish security event
                await self.redis_client.publish(
                    "ws_security",
                    json.dumps({
                        "action": "security_event",
                        "event_type": event_type,
                        "details": details,
                        "timestamp": datetime.now().isoformat()
                    })
                )
                
                return True
            except Exception as e:
                logger.error(f"Error logging security event to Redis: {str(e)}")
                return False
        
        return True
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.distributed_mode and self.redis_client:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.error(f"Error closing Redis connection: {str(e)}")
                
        self.blacklisted_ips.clear()
        self.suspicious_ips.clear()
        self.ip_connection_count.clear()
        self.rate_limit_counters.clear()
        self.connection_history.clear()
