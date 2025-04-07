"""WebSocket handler for AI chat.

This module provides WebSocket endpoints for AI chat interactions.
"""
import logging
import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, status
from datetime import datetime
import uuid
import traceback

from src.common.auth import get_current_user, User
from src.common.config import get_settings
from src.services.event_bus import EventBus
from .ws_connection_manager import chat_manager
from .message_formatter import MessageFormatter
from src.ai.chat_agent import ChatAgent

# Setup logging
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create router
router = APIRouter(prefix="/ws/chat", tags=["chat-ws"])

# WebSocket endpoint
@router.websocket("/ws")
async def chat_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for AI chat.
    
    Args:
        websocket: The WebSocket connection.
    """
    # Start the cleanup task if not already running
    chat_manager.start_cleanup_task()
    
    # For tracking connection status
    user_id = None
    connection_accepted = False
    
    try:
        # Get user_id and token from query parameters
        user_id = websocket.query_params.get("user_id")
        token = websocket.query_params.get("token")
        client_ip = _get_client_ip(websocket)
        
        # Validate user_id
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing user_id parameter")
            return
        
        # Basic authentication check
        if not token and settings.environment != "development":
            if "demo" not in user_id.lower():
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
                return
        
        # Get initial conversation_id if provided in query params
        conversation_id = websocket.query_params.get("conversation_id") or str(uuid.uuid4())
        logger.info(f"Using conversation ID: {conversation_id}")
        
        # Initialize user if needed
        try:
            from src.common.initialization import initialize_new_user
            # Use lazy initialization to improve startup performance
            await initialize_new_user(user_id, lazy_init=True)
        except Exception as e:
            logger.error(f"Error initializing user {user_id}: {str(e)}")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Error initializing user")
            return
        
        # Connect the WebSocket with rate limiting and connection limits
        connection_accepted = await chat_manager.connect(websocket, user_id, client_ip)
        if not connection_accepted:
            # Connection was rejected and already closed by the connection manager
            return
        
        logger.info(f"WebSocket connection accepted for {user_id} - sending welcome message")
        
        # Add a delay before doing anything to ensure the connection is stable
        await asyncio.sleep(0.5)
        
        # Check MongoDB connection and send welcome message with detailed logging
        try:
            # Check MongoDB connection
            mongo_connected = False
            try:
                from src.storage.mongodb import MongoDBProvider
                mongo_provider = MongoDBProvider()
                mongo_connected = await mongo_provider.connect()
                await mongo_provider.close()
            except Exception as mongo_err:
                logger.error(f"MongoDB connection check failed: {str(mongo_err)}")
                
            # If MongoDB is not connected, send an error message
            if not mongo_connected:
                mongo_error_message = {
                    "message_type": "error",
                    "text": "Cannot connect to MongoDB. Chat history will not be saved. Please refresh or try again later.",
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat(),
                    "sender": "system",
                    "error_code": "MONGODB_CONNECTION_ERROR",
                    "metadata": {
                        "mongodb_connected": False
                    }
                }
                
                if await _is_websocket_connected(websocket):
                    try:
                        await websocket.send_text(json.dumps(mongo_error_message))
                        logger.warning(f"MongoDB connection error message sent to user {user_id}")
                        # Close the websocket after a short delay
                        await asyncio.sleep(0.5)
                        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="MongoDB connection failed")
                        return
                    except Exception as send_error:
                        logger.error(f"Failed to send MongoDB error message: {str(send_error)}")
                        return
            
            # Create welcome message including MongoDB status
            welcome_message = {
                "message_type": "welcome",
                "text": "Welcome to Knowledge Forest Chat",
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "sender": "system",
                "metadata": {
                    "mongodb_connected": mongo_connected
                }
            }
            
            # Check if connection is still open, reduce unnecessary error logs
            if await _is_websocket_connected(websocket):
                try:
                    json_string = json.dumps(welcome_message)
                    logger.debug(f"Welcome message content: {json_string[:200]}...")
                    await websocket.send_text(json_string)
                    logger.info(f"Welcome message sent to user {user_id}")
                    # Allow frontend to process welcome message
                    await asyncio.sleep(1.0)  
                except WebSocketDisconnect:
                    logger.warning(f"Client disconnected while sending welcome message: {user_id}")
                    return
                except Exception as e:
                    logger.error(f"Error sending welcome message: {str(e)}")
                    return
            else:
                logger.warning(f"Cannot send welcome message to {user_id} - connection already closed")
                return
        except WebSocketDisconnect:
            logger.warning(f"Client disconnected while sending welcome message: {user_id}")
            return  # Exit early to avoid more errors
        except Exception as e:
            logger.error(f"Error in WebSocket initialization phase: {str(e)}", exc_info=True)
            return
        
        # Initialize or get chat agent after ensuring welcome message was sent
        agent = None
        try:
            # Add a small delay before initializing the agent
            await asyncio.sleep(0.2)
            
            agent = chat_manager.get_agent_for_user(user_id)
            if not agent:
                try:
                    agent = ChatAgent(user_id=user_id, conversation_id=conversation_id)
                    chat_manager.set_agent_for_user(user_id, agent)
                    logger.info(f"Chat agent created for user {user_id} with conversation {conversation_id}")
                    
                    # Check if agent has at least one initialized provider
                    if not agent.is_llm_initialized:
                        logger.warning(f"Chat agent for user {user_id} has no initialized LLM providers")
                        if await _is_websocket_connected(websocket):
                            try:
                                await websocket.send_text(json.dumps({
                                    "message_type": "error",
                                    "text": "Warning: The system has limited AI capabilities right now. Some features may not work properly.",
                                    "error_code": "LIMITED_CAPABILITY",
                                    "id": str(uuid.uuid4()),
                                    "timestamp": datetime.now().isoformat(),
                                    "sender": "system"
                                }))
                            except Exception as e:
                                logger.error(f"Error sending LLM warning: {str(e)}")
                        # Continue anyway, don't disconnect
                except Exception as e:
                    logger.error(f"Error creating chat agent: {e}")
                    if await _is_websocket_connected(websocket):
                        try:
                            await websocket.send_text(json.dumps({
                                "message_type": "error",
                                "text": "I'm having trouble connecting to the AI services right now. Your messages might be delayed or incomplete.",
                                "error_code": "AGENT_INIT_PARTIAL_ERROR",
                                "id": str(uuid.uuid4()),
                                "timestamp": datetime.now().isoformat(),
                                "sender": "system"
                            }))
                        except Exception as send_error:
                            logger.error(f"Error sending agent initialization error: {str(send_error)}")
                    
                    # Create a minimal agent anyway so the connection stays open
                    try:
                        agent = ChatAgent(user_id=user_id, conversation_id=conversation_id)
                        chat_manager.set_agent_for_user(user_id, agent)
                    except Exception as inner_e:
                        logger.error(f"Fatal error creating chat agent: {inner_e}")
                        if await _is_websocket_connected(websocket):
                            try:
                                await websocket.send_text(json.dumps({
                                    "message_type": "error",
                                    "text": "Critical error initializing chat services.",
                                    "error_code": "AGENT_INIT_ERROR",
                                    "id": str(uuid.uuid4()),
                                    "timestamp": datetime.now().isoformat(),
                                    "sender": "system"
                                }))
                                await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Failed to initialize chat agent")
                            except Exception:
                                pass
                        return
        except Exception as e:
            logger.error(f"Error during agent initialization phase: {e}")
            # Continue and try to keep connection open
        
        # Main message loop
        try:
            while True:
                # Check if connection is still open before receiving message
                if not await _is_websocket_connected(websocket):
                    logger.warning(f"WebSocket connection for {user_id} no longer active, breaking message loop")
                    break
                    
                # Wait for messages from the client
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                except asyncio.TimeoutError:
                    # No message received for a long time, send ping to check connection
                    if await _is_websocket_connected(websocket):
                        try:
                            await websocket.send_json({"type": "ping", "timestamp": datetime.now().isoformat()})
                            continue  # Continue message loop
                        except Exception:
                            # Ping failed, connection may be broken
                            break
                    else:
                        break  # Connection is closed, exit loop
                except RuntimeError as e:
                    # WebSocket is already closed or can't be read
                    if "WebSocket is not connected" in str(e):
                        logger.warning(f"WebSocket for {user_id} is no longer connected, breaking message loop")
                        break
                    raise
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected for user {user_id}")
                    break
                
                # Update activity timestamp
                chat_manager.update_activity(websocket, user_id)
                
                # Parse message data
                try:
                    message_data = json.loads(data)
                    
                    # Handle special message types
                    message_type = message_data.get("type", "")
                    
                    # Handle heartbeat/ping message
                    if message_type == "ping" or message_type == "heartbeat":
                        await websocket.send_json(MessageFormatter.format_heartbeat())
                        continue
                    
                    # Check if this is a subscription message
                    if "action" in message_data and message_data.get("action") == "subscribe":
                        # Use the ChatConnectionManager's subscription handler
                        await chat_manager.handle_subscription_message(message_data, websocket, user_id)
                        continue
                    
                    # Extract message text for regular messages
                    user_text = message_data.get("query", "")
                    if not user_text:
                        # Log the empty message issue
                        logger.warning(f"Empty message received from user {user_id}. Message data: {message_data}")
                        # Don't send error to client, just continue
                        continue
                    
                    # Check message length limit
                    if len(user_text) > 32000:  # Reasonable limit for most LLMs
                        await websocket.send_json(MessageFormatter.format_error(
                            "Message too long. Please send a shorter message.",
                            error_code="MESSAGE_TOO_LONG"
                        ))
                        continue
                    
                    # Check if agent is already processing a request
                    if await chat_manager.is_agent_busy(user_id):
                        await websocket.send_json(MessageFormatter.format_error(
                            "Agent is busy processing another request. Please wait.",
                            error_code="AGENT_BUSY"
                        ))
                        continue
                    
                    # Set agent as busy
                    chat_manager.set_agent_busy(user_id, True)
                    
                    # Get existing conversation ID or create new one
                    msg_conversation_id = message_data.get("options", {}).get("conversation_id") or conversation_id
                    message_id = str(uuid.uuid4())
                    
                    # Check if this is the first message for this user
                    # If it is, initialize their knowledge forest
                    try:
                        from src.storage.mongodb import MongoDBProvider
                        from src.common.initialization import initialize_new_user
                        
                        storage = MongoDBProvider()
                        if await storage.is_connected():
                            node_count = await storage.count_documents("nodes", {"user_id": user_id})
                            if node_count == 0:
                                # This is the first real message, create the knowledge forest
                                logger.info(f"First message for user {user_id}, initializing knowledge forest")
                                await initialize_new_user(user_id, lazy_init=False)
                    except Exception as init_err:
                        logger.error(f"Error checking/initializing first-message knowledge forest: {str(init_err)}")
                        # Continue anyway - we don't want to block the chat
                    
                    try:
                        # Process request with timeout protection
                        processing_start = time.time()
                        
                        # Send user message back to confirm receipt
                        user_message = MessageFormatter.format_message("user", user_text)
                        await websocket.send_json(user_message)
                        
                        # Send thinking message
                        await websocket.send_json(MessageFormatter.format_thinking("Processing your request..."))
                        
                        # Determine if enhanced model or special processing is requested
                        options = message_data.get("options", {})
                        use_enhanced_model = options.get("enhanced", False)
                        use_thinking = options.get("thinking", False)
                        use_image_gen = options.get("image", False)
                        
                        # Process with the appropriate method based on options
                        try:
                            # Publish message event to EventBus
                            event_bus = EventBus()
                            await event_bus.publish("message.created", {
                                "user_id": user_id,
                                "conversation_id": msg_conversation_id,
                                "message_id": message_id,
                                "message_type": "user",
                                "content": user_text,
                                "timestamp": datetime.utcnow().isoformat()
                            })

                            if use_image_gen:
                                # Send thinking message for image generation
                                await websocket.send_json(MessageFormatter.format_thinking(
                                    "Generating image based on your description..."
                                ))
                                response = await asyncio.wait_for(
                                    agent.process_image_generation(user_text),
                                    timeout=60  # Longer timeout for image generation
                                )
                                
                                # Check if response is an image URL or text
                                if isinstance(response, dict) and "image_url" in response:
                                    await websocket.send_json(MessageFormatter.format_image_response(
                                        response["image_url"],
                                        response.get("caption", "Generated image"),
                                        metadata={"processing_time": time.time() - processing_start}
                                    ))
                                else:
                                    await websocket.send_json(MessageFormatter.format_ai_response(
                                        response,
                                        processing_time=time.time() - processing_start
                                    ))
                                    
                                    # Publish AI reply message event to EventBus
                                    await event_bus.publish("message.created", {
                                        "user_id": user_id,
                                        "conversation_id": msg_conversation_id,
                                        "message_id": str(uuid.uuid4()),
                                        "message_type": "assistant",
                                        "content": f"User: {user_text}\nAssistant: {response}",
                                        "timestamp": datetime.utcnow().isoformat()
                                    })
                                    
                            elif use_thinking:
                                # Send thinking message
                                await websocket.send_json(MessageFormatter.format_thinking(
                                    "Thinking through your question step by step..."
                                ))
                                response = await asyncio.wait_for(
                                    agent.process_thinking_message(user_text),
                                    timeout=45
                                )
                                await websocket.send_json(MessageFormatter.format_ai_response(
                                    response,
                                    processing_time=time.time() - processing_start
                                ))
                                
                                # Publish AI reply message event to EventBus
                                await event_bus.publish("message.created", {
                                    "user_id": user_id,
                                    "conversation_id": msg_conversation_id,
                                    "message_id": str(uuid.uuid4()),
                                    "message_type": "assistant",
                                    "content": f"User: {user_text}\nAssistant: {response}",
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                                
                            else:
                                # Standard processing with option for enhanced model
                                response = await asyncio.wait_for(
                                    agent.process_message(user_text, use_enhanced_model=use_enhanced_model),
                                    timeout=30
                                )
                                await websocket.send_json(MessageFormatter.format_ai_response(
                                    response,
                                    processing_time=time.time() - processing_start
                                ))
                                
                                # Publish AI reply message event to EventBus
                                await event_bus.publish("message.created", {
                                    "user_id": user_id,
                                    "conversation_id": msg_conversation_id,
                                    "message_id": str(uuid.uuid4()),
                                    "message_type": "assistant",
                                    "content": f"User: {user_text}\nAssistant: {response}",
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                                
                        except asyncio.TimeoutError:
                            logger.warning(f"Request processing timeout for user {user_id}")
                            await websocket.send_json(MessageFormatter.format_error(
                                "Request processing took too long. Please try a shorter or simpler request.",
                                error_code="PROCESSING_TIMEOUT"
                            ))
                            
                    except Exception as e:
                        logger.exception(f"Error processing message: {e}")
                        try:
                            await websocket.send_json(MessageFormatter.format_error(
                                f"Error processing your request: {str(e)}",
                                error_code="PROCESSING_ERROR"
                            ))
                        except Exception:
                            pass
                    finally:
                        # Set agent as not busy
                        chat_manager.set_agent_busy(user_id, False)
                        
                except json.JSONDecodeError:
                    try:
                        await websocket.send_json(MessageFormatter.format_error(
                            "Invalid message format. Please send valid JSON.",
                            error_code="INVALID_JSON"
                        ))
                    except Exception:
                        pass
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for user {user_id}")
        
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id if user_id else 'unknown'}: {str(e)}", exc_info=True)
        logger.debug(traceback.format_exc())
        try:
            if not connection_accepted:
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
        except Exception as close_error:
            logger.error(f"Error closing WebSocket connection: {str(close_error)}")
    finally:
        # Clean up
        if user_id and connection_accepted:
            try:
                await chat_manager.disconnect(websocket, user_id)
                logger.info(f"WebSocket disconnected and cleaned up for user {user_id}")
            except Exception as cleanup_error:
                logger.error(f"Error during WebSocket cleanup: {cleanup_error}")


def _get_client_ip(websocket: WebSocket) -> Optional[str]:
    """Extract client IP address from WebSocket connection.
    
    Args:
        websocket: The WebSocket connection.
        
    Returns:
        The client IP address or None if not available.
    """
    client = websocket.client
    if client:
        return client.host
    
    # Try to get from headers (X-Forwarded-For)
    headers = websocket.headers
    if headers and "x-forwarded-for" in headers:
        return headers["x-forwarded-for"].split(",")[0].strip()
    
    return None


async def _is_websocket_connected(websocket: WebSocket) -> bool:
    """Check if WebSocket connection is still open.
    
    Args:
        websocket: WebSocket connection.
        
    Returns:
        True if connection is still open, False otherwise.
    """
    try:
        # Try to get client state, will raise exception if connection is closed
        client = websocket.client
        return client is not None
    except Exception:
        return False


@router.on_event("startup")
async def startup_event():
    """Initialize connection manager on startup."""
    chat_manager.start_cleanup_task()


@router.on_event("shutdown")
async def shutdown_event():
    """Clean up connection manager on shutdown."""
    await chat_manager.stop()
