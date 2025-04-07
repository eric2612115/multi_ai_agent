"""Main FastAPI application.

This module defines the main FastAPI application with all routes and dependencies.
"""
# Make sure environment variables are loaded first
from src.common.env_loader import load_environment_variables

import logging
import asyncio
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Import API routers
from src.api.rest.knowledge_forest import router as knowledge_router
from src.api.rest.knowledge_forest_additional import router as knowledge_additional_router
from src.api.rest.knowledge_forest_public import router as knowledge_public_router
from src.api.rest.conversations import router as conversations_router
from src.api.rest.conversations_public import router as conversations_public_router
from src.api.rest.debug import router as debug_router
from src.api.rest.auth import router as auth_router
from src.api.rest.reflection import router as reflection_router
from src.api.websocket.notifications import router as ws_router
from src.api.websocket.notifications import startup as ws_startup

# Setup logging
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import knowledge distillation router
try:
    from src.api.rest.knowledge_distillation import router as distillation_router
    logger.info("Knowledge distillation router imported successfully")
except ImportError as e:
    logger.warning(f"Failed to import knowledge distillation router: {e}")
    distillation_router = None

# Import dependencies
from src.dependencies.mongodb import initialize_mongodb_provider

# Scheduled task functions
async def run_scheduled_reflection():
    """Run scheduled reflection for all users."""
    try:
        if not reflection_system:
            logger.warning("Cannot run scheduled reflection: Reflection system not initialized")
            return
            
        # Get all users with active nodes
        storage = MongoDBProvider()
        user_query = {"is_active": True}
        active_users = await storage.find_documents("users", user_query, projection={"_id": 1})
        
        logger.info(f"Running scheduled reflection for {len(active_users)} users")
        
        # Start reflection for each user
        for user in active_users:
            user_id = user.get("_id")
            if not user_id:
                continue
                
            try:
                # Check if this user should have reflection
                should_run = await reflection_system.should_trigger_reflection(user_id)
                
                if should_run:
                    logger.info(f"Starting scheduled reflection for user {user_id}")
                    cycle_id = await reflection_system.start_reflection_cycle(
                        user_id=user_id,
                        trigger_source="schedule"
                    )
                    logger.info(f"Scheduled reflection started for user {user_id}: {cycle_id}")
                else:
                    logger.debug(f"Skipping scheduled reflection for user {user_id}")
            except Exception as user_err:
                logger.error(f"Error running reflection for user {user_id}: {str(user_err)}")
                
    except Exception as e:
        logger.error(f"Error in scheduled reflection: {str(e)}")

async def run_lifecycle_maintenance():
    """Run lifecycle maintenance for all users."""
    try:
        if not lifecycle_manager:
            logger.warning("Cannot run lifecycle maintenance: Lifecycle manager not initialized")
            return
            
        # Get all users with active nodes
        storage = MongoDBProvider()
        user_query = {"is_active": True}
        active_users = await storage.find_documents("users", user_query, projection={"_id": 1})
        
        logger.info(f"Running lifecycle maintenance for {len(active_users)} users")
        
        # Run maintenance for each user
        for user in active_users:
            user_id = user.get("_id")
            if not user_id:
                continue
                
            try:
                logger.info(f"Starting lifecycle maintenance for user {user_id}")
                results = await lifecycle_manager.run_lifecycle_maintenance(user_id)
                
                # Log results
                changes = sum(results.values())
                if changes > 0:
                    logger.info(f"Lifecycle maintenance for user {user_id} completed with {changes} changes")
                    logger.debug(f"Lifecycle maintenance results: {results}")
                else:
                    logger.info(f"Lifecycle maintenance for user {user_id} completed with no changes")
            except Exception as user_err:
                logger.error(f"Error running lifecycle maintenance for user {user_id}: {str(user_err)}")
                
    except Exception as e:
        logger.error(f"Error in lifecycle maintenance: {str(e)}")


async def run_balance_cycle():
    """Run balance cycle for all users."""
    try:
        if not balance_manager:
            logger.warning("Cannot run balance cycle: Balance manager not initialized")
            return
            
        # Get all users with active nodes
        storage = MongoDBProvider()
        user_query = {"is_active": True}
        active_users = await storage.find_documents("users", user_query, projection={"_id": 1})
        
        logger.info(f"Running balance cycle for {len(active_users)} users")
        
        # Run balance cycle for each user
        for user in active_users:
            user_id = user.get("_id")
            if not user_id:
                continue
                
            try:
                logger.info(f"Starting balance cycle for user {user_id}")
                results = await balance_manager.run_balance_cycle(user_id)
                
                # Log results
                if results["success"]:
                    topic_changes = results.get("topic_balance_results", {}).get("topics_balanced", 0)
                    density_changes = results.get("connection_density_results", {}).get("connections_affected", 0)
                    growth_action = results.get("growth_regulation_results", {}).get("action_taken", "none")
                    
                    logger.info(f"Balance cycle for user {user_id} completed successfully")
                    logger.info(f"Topics balanced: {topic_changes}, Connections affected: {density_changes}, Growth action: {growth_action}")
                else:
                    logger.info(f"Balance cycle for user {user_id} completed with no changes")
            except Exception as user_err:
                logger.error(f"Error running balance cycle for user {user_id}: {str(user_err)}")
                
    except Exception as e:
        logger.error(f"Error in balance cycle: {str(e)}")


async def run_system_evaluation():
    """Run system evaluation for all users."""
    try:
        if not evaluation_system:
            logger.warning("Cannot run system evaluation: Evaluation system not initialized")
            return
            
        # Get all users with active nodes
        storage = MongoDBProvider()
        user_query = {"is_active": True}
        active_users = await storage.find_documents("users", user_query, projection={"_id": 1})
        
        logger.info(f"Running system evaluation for {len(active_users)} users")
        
        # Run evaluation for each user
        for user in active_users:
            user_id = user.get("_id")
            if not user_id:
                continue
                
            try:
                logger.info(f"Starting system evaluation for user {user_id}")
                evaluation_results = await evaluation_system.evaluate_system(user_id)
                
                # Check if optimization is needed
                if evaluation_system.needs_optimization(evaluation_results):
                    logger.info(f"Starting system optimization for user {user_id}")
                    optimization_result = await evaluation_system.optimize_system(user_id, evaluation_results)
                    logger.info(f"System optimization completed: {optimization_result}")
                else:
                    logger.info(f"No optimization needed for user {user_id}")
                    
            except Exception as user_err:
                logger.error(f"Error during system evaluation for user {user_id}: {str(user_err)}")
                
    except Exception as e:
        logger.error(f"Error in system evaluation: {str(e)}")
# Import chat WebSocket router
try:
    from src.api.websocket.chat.ws_chat import router as chat_ws_router
    logger.info("Chat WebSocket router imported successfully")
except ImportError as e:
    logger.warning(f"Failed to import chat WebSocket router: {e}")
    chat_ws_router = None

# Import thinking WebSocket router
try:
    from src.api.websocket.chat.ws_thinking import router as thinking_ws_router
    logger.info("Thinking WebSocket router imported successfully")
except ImportError as e:
    logger.warning(f"Failed to import thinking WebSocket router: {e}")
    thinking_ws_router = None

# Import MCP integration
from src.api.mcp.knowledge_tools import register_knowledge_tools
from src.api.mcp.mcp_integration import get_mcp_integration

# Import services
from src.forest.tasks import KnowledgeForestTaskHandler
from src.services.event_bus import EventBus
from src.services.task_queue import TaskQueue
from src.services.message_storage import MessageStorageService
from src.storage.mongodb import MongoDBProvider
from src.forest.graph import KnowledgeGraphManager
from src.forest.extraction import KnowledgeExtractor
from src.forest.extraction_service import KnowledgeExtractionService
from src.forest.placement import KnowledgePlacementService

# Import common functionality
from src.common.config import get_settings
from src.common.initialization import initialize_new_user

# Get settings
settings = get_settings()

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global services
task_handler = None
event_bus = None
task_queue = None
mongo_db = None
graph_manager = None
extraction_service = None
placement_service = None
message_storage_service = None

# Self-evolving system components
energy_manager = None
lifecycle_manager = None
abstraction_generator = None
reflection_system = None
balance_manager = None
evaluation_system = None

# Task scheduler
scheduler = None

# Setup lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app.
    
    This replaces the deprecated on_event("startup") and on_event("shutdown") functions.
    """
    global task_handler, event_bus, task_queue, message_storage_service
    
    # ===== STARTUP PHASE =====
    logger.info("Starting AI Knowledge Forest API")

    # Initialize event bus
    event_bus = EventBus()

    # Initialize task queue
    task_queue = TaskQueue()
    await task_queue.start()
    
    # Initialize message storage service
    message_storage_service = MessageStorageService()
    
    # Initialize MongoDB connection
    try:
        logger.info("Initializing MongoDB connection")
        mongo_db = MongoDBProvider()
        success = await mongo_db.connect()
        if success:
            logger.info("MongoDB connected successfully")
            # Initialize the MongoDB provider dependency
            initialize_mongodb_provider(mongo_db)
            
            # Start message storage service now that MongoDB is connected
            try:
                await message_storage_service.start()
                logger.info("Message storage service started successfully")
                
                # Register message event handlers
                try:
                    from src.api.rest.message_handlers import register_message_handlers
                    await register_message_handlers()
                    logger.info("Message handlers registered successfully")
                except Exception as handler_err:
                    logger.error(f"Failed to register message handlers: {str(handler_err)}")
            except Exception as msg_err:
                logger.error(f"Failed to start message storage service: {str(msg_err)}")
        else:
            logger.error("MongoDB connection failed without error - check settings")
            # 如果MongoDB未连接成功，应用程序不应继续处理对话
            raise RuntimeError("Cannot start application without MongoDB connection")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        logger.error("API will run with limited functionality - no data will be saved")
        mongo_db = None

    # Initialize knowledge services with MongoDB connection
    if mongo_db:
        try:
            logger.info("Initializing Knowledge Graph Manager")
            graph_manager = KnowledgeGraphManager(storage_provider=mongo_db)
            logger.info("Knowledge Graph Manager initialized successfully")

            logger.info("Initializing Knowledge Extraction Service")
            extraction_service = KnowledgeExtractionService()
            logger.info("Knowledge Extraction Service initialized successfully")

            logger.info("Initializing Knowledge Placement Service")
            placement_service = KnowledgePlacementService(storage_provider=mongo_db)
            logger.info("Knowledge Placement Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize knowledge services: {str(e)}")
            logger.error("API will run with limited functionality")
            # Reset any services that may have failed
            graph_manager = None if 'graph_manager' not in locals() else graph_manager
            extraction_service = None if 'extraction_service' not in locals() else extraction_service
            placement_service = None if 'placement_service' not in locals() else placement_service

    try:
        # Initialize task handler
        try:
            logger.info("Initializing Knowledge Forest Task Handler")
            # Import all AI models first to ensure registration
            try:
                import ai.gemini
                import ai.claude
            except ImportError as e:
                logger.warning(f"Some AI models could not be imported: {e}")
                
            # Initialize task handler with our initialized services
            task_handler = KnowledgeForestTaskHandler(
                event_bus=event_bus,
                task_queue=task_queue,
                extraction_service=extraction_service if 'extraction_service' in locals() else None,
                placement_service=placement_service if 'placement_service' in locals() else None,
                graph_manager=graph_manager if 'graph_manager' in locals() else None
            )
            await task_handler.start()
            logger.info("Knowledge Forest Task Handler started successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Knowledge Forest Task Handler: {str(e)}")
            logger.error("API will run with limited functionality")
            # Create a minimal task handler as fallback
            task_handler = None
            
        # Initialize self-evolving system components
        if mongo_db and graph_manager:
            try:
                # Initialize Energy System
                logger.info("Initializing Energy Management System")
                from src.forest.energy.manager_combined import EnergyManager
                energy_manager = EnergyManager(storage_provider=mongo_db)
                try:
                    await energy_manager.start()
                    logger.info("Energy Management System initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize Energy Management System: {str(e)}")
                    energy_manager = None
                
                # Initialize Lifecycle Management System
                logger.info("Initializing Lifecycle Management System")
                from src.forest.lifecycle.manager_combined import LifecycleManager
                lifecycle_manager = LifecycleManager(storage_provider=mongo_db, graph_manager=graph_manager)
                logger.info("Lifecycle Management System initialized successfully")
                
                # Initialize Abstraction System
                logger.info("Initializing Abstraction Management System")
                from src.forest.abstraction.generator_combined import AbstractionGenerator
                abstraction_generator = AbstractionGenerator(storage_provider=mongo_db, graph_manager=graph_manager)
                logger.info("Abstraction Management System initialized successfully")
                
                # Initialize Balance Manager
                logger.info("Initializing Balance Manager")
                from src.forest.balance.manager import BalanceManager
                balance_manager = BalanceManager(
                    storage_provider=mongo_db,
                    energy_manager=energy_manager,
                    lifecycle_manager=lifecycle_manager
                )
                try:
                    await balance_manager.start()
                    logger.info("Balance Manager initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize Balance Manager: {str(e)}")
                    balance_manager = None
                
                # Initialize Reflection System
                logger.info("Initializing Reflection System")
                from src.forest.reflection.core import ReflectionSystem
                reflection_system = ReflectionSystem(
                    storage_provider=mongo_db,
                    energy_manager=energy_manager,
                    abstraction_generator=abstraction_generator
                )
                logger.info("Reflection System initialized successfully")
                
                # Initialize and start task scheduler
                logger.info("Initializing Task Scheduler")
                scheduler = AsyncIOScheduler()
                
                # Setup periodic reflection schedule for all users
                if reflection_system and settings.reflection.enable_autonomous:
                    reflection_interval = settings.reflection.cycle_interval_hours
                    scheduler.add_job(
                        run_scheduled_reflection,
                        IntervalTrigger(hours=reflection_interval),
                        id="periodic_reflection",
                        replace_existing=True
                    )
                    logger.info(f"Scheduled periodic reflection every {reflection_interval} hours")
                
                # Setup periodic lifecycle maintenance
                if lifecycle_manager and settings.lifecycle.enable_auto_pruning:
                    pruning_interval = settings.lifecycle.pruning_interval_hours
                    scheduler.add_job(
                        run_lifecycle_maintenance,
                        IntervalTrigger(hours=pruning_interval),
                        id="lifecycle_maintenance",
                        replace_existing=True
                    )
                    logger.info(f"Scheduled lifecycle maintenance every {pruning_interval} hours")
                    
                # Setup periodic balance cycle
                if balance_manager and settings.balance.enable_auto_balance:
                    balance_interval = settings.balance.balance_interval_hours
                    scheduler.add_job(
                        run_balance_cycle,
                        IntervalTrigger(hours=balance_interval),
                        id="balance_cycle",
                        replace_existing=True
                    )
                    logger.info(f"Scheduled balance cycle every {balance_interval} hours")
                
                # Initialize Evaluation System
                logger.info("Initializing System Evaluation")
                from src.forest.evaluation.evaluator import SystemEvaluator
                evaluation_system = SystemEvaluator(
                    storage_provider=mongo_db,
                    energy_manager=energy_manager,
                    lifecycle_manager=lifecycle_manager,
                    reflection_system=reflection_system,
                    graph_manager=graph_manager
                )
                try:
                    await evaluation_system.start()
                    logger.info("System Evaluation initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize System Evaluation: {str(e)}")
                    evaluation_system = None
                
                # Schedule periodic evaluation
                if evaluation_system and settings.evaluation.enable_auto_optimization:
                    evaluation_interval = settings.evaluation.evaluation_interval_hours
                    scheduler.add_job(
                        run_system_evaluation,
                        IntervalTrigger(hours=evaluation_interval),
                        id="system_evaluation",
                        replace_existing=True
                    )
                    logger.info(f"Scheduled system evaluation every {evaluation_interval} hours")
                
                # Start the scheduler
                scheduler.start()
                logger.info("Task Scheduler started successfully")
            except Exception as e:
                logger.error(f"Failed to initialize self-evolving systems: {str(e)}")
                logger.error("API will run without self-evolving capabilities")
                # Log more detailed error for debugging
                logger.exception("Self-evolving system initialization error")
                # Reset any failed components
                if energy_manager:
                    await energy_manager.stop()
                energy_manager = None
                lifecycle_manager = None
                abstraction_generator = None
                reflection_system = None

        # Setup WebSocket notifications
        try:
            logger.info("Setting up WebSocket notifications")
            await ws_startup()
            logger.info("WebSocket notifications setup complete")
        except Exception as e:
            logger.error(f"Failed to setup WebSocket notifications: {str(e)}")
            logger.error("API will run without real-time notifications")

        # Initialize and register MCP tools
        try:
            # Initialize MCP integration
            mcp_integration = get_mcp_integration()
            if mcp_integration.initialize():
                logger.info("MCP integration initialized successfully")
                
                # Register knowledge tools
                try:
                    tools = register_knowledge_tools()
                    registered_count = mcp_integration.register_tools(tools)
                    
                    if registered_count > 0:
                        logger.info(f"Successfully registered {registered_count} knowledge tools with MCP")
                        logger.info(f"Registered tools: {', '.join(mcp_integration.get_registered_tools())}")
                    else:
                        logger.warning("No knowledge tools were registered with MCP")
                except Exception as e:
                    logger.error(f"Failed to register knowledge tools: {str(e)}")
                    logger.exception("Knowledge tools registration error")
            else:
                logger.warning("MCP integration initialization failed, running without MCP tools")
        except Exception as e:
            logger.error(f"Failed to initialize MCP integration: {str(e)}")
            logger.error("API will continue without MCP tools")
            # Log more detailed error for debugging
            logger.exception("MCP integration error")

        # Create default user for development
        if settings.environment == "development":
            try:
                from src.common.initialization import create_default_user
                await create_default_user()
                logger.info("Created default user for development environment")
            except Exception as e:
                logger.error(f"Failed to create default user: {str(e)}")
        
        logger.info("AI Knowledge Forest API started")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        logger.error("API may not function correctly due to initialization error")

    # Yield control back to FastAPI, app is now running
    yield
    
    # ===== SHUTDOWN PHASE =====
    logger.info("Shutting down AI Knowledge Forest API")

    # Stop task handler
    if task_handler:
        try:
            logger.info("Stopping Knowledge Forest Task Handler")
            await task_handler.stop()
            logger.info("Knowledge Forest Task Handler stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping task handler: {str(e)}")
            
    # Stop self-evolving system components
    if energy_manager:
        try:
            logger.info("Stopping Energy Management System")
            await energy_manager.stop()
            logger.info("Energy Management System stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping energy manager: {str(e)}")
            
    if balance_manager:
        try:
            logger.info("Stopping Balance Manager")
            await balance_manager.stop()
            logger.info("Balance Manager stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping balance manager: {str(e)}")
            
    if 'evaluation_system' in locals() and evaluation_system:
        try:
            logger.info("Stopping Evaluation System")
            await evaluation_system.stop()
            logger.info("Evaluation System stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping evaluation system: {str(e)}")
            
    # Stop task scheduler
    if 'scheduler' in locals() and scheduler and scheduler.running:
        try:
            logger.info("Stopping Task Scheduler")
            scheduler.shutdown()
            logger.info("Task Scheduler stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping task scheduler: {str(e)}")

    # Stop task queue
    if task_queue:
        try:
            logger.info("Stopping Task Queue")
            await task_queue.stop()
            logger.info("Task Queue stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping task queue: {str(e)}")
            
    # Stop message storage service
    if 'message_storage_service' in locals() and message_storage_service:
        try:
            logger.info("Stopping message storage service")
            await message_storage_service.stop()
            logger.info("Message storage service stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping message storage service: {str(e)}")
    
    # Close MongoDB connection
    if 'mongo_db' in locals() and mongo_db:
        try:
            logger.info("Closing MongoDB connection")
            await mongo_db.close()
            logger.info("MongoDB connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {str(e)}")

    logger.info("AI Knowledge Forest API shutdown complete")

# Create FastAPI application
app = FastAPI(
    title="AI Knowledge Forest API",
    description="API for managing AI knowledge forest",
    version="1.0.0",
    lifespan=lifespan,  # Use the lifespan context manager
)

# Add CORS middleware with proper WebSocket support
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.api.frontend_url, "localhost", "http://localhost:8081", "http://localhost:3000", "http://localhost:5173", "ws://localhost:8000", "ws://localhost:8081", "ws://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(knowledge_router)
app.include_router(knowledge_additional_router)
app.include_router(knowledge_public_router)
app.include_router(conversations_router)
app.include_router(conversations_public_router)
app.include_router(debug_router)
app.include_router(auth_router)
app.include_router(reflection_router)
app.include_router(ws_router)

# Register knowledge distillation router if available
if distillation_router:
    app.include_router(distillation_router)
    logger.info("Knowledge distillation router registered")

# Register chat WebSocket router if available
if chat_ws_router:
    app.include_router(chat_ws_router)
    logger.info("Chat WebSocket router registered")

# Register thinking WebSocket router if available
if thinking_ws_router:
    app.include_router(thinking_ws_router)
    logger.info("Thinking WebSocket router registered")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "AI Knowledge Forest API",
        "version": "1.0.0",
        "status": "online",
        "timestamp": datetime.utcnow().isoformat()
    }

# Debug endpoints
@app.get("/debug/mongo")
async def debug_mongo():
    """Debug MongoDB connection."""
    from src.storage.mongodb import MongoDBProvider
    try:
        mongo_db = MongoDBProvider()
        success = await mongo_db.connect()
        if success:
            # Test collections - run a simple query
            conversations_count = await mongo_db.count_documents("conversations", {})
            messages_count = await mongo_db.count_documents("messages", {})
            
            result = {
                "status": "connected",
                "message": "MongoDB connection successful",
                "uri": mongo_db.connection_uri,
                "database": mongo_db.database_name,
                "stats": {
                    "conversations": conversations_count,
                    "messages": messages_count
                }
            }
            await mongo_db.close()
        else:
            result = {
                "status": "failed",
                "message": "MongoDB connection failed without raising an exception",
                "uri": mongo_db.connection_uri,
                "database": mongo_db.database_name
            }
    except Exception as e:
        result = {
            "status": "error",
            "message": f"Error connecting to MongoDB: {str(e)}",
            "error_type": str(type(e).__name__)
        }
    
    return result


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


# Exception handlers
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle any unhandled exceptions."""
    logger.error(f"Unhandled exception for request {request.url}: {str(exc)}")

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "details": str(exc) if settings.api.debug_mode else None
        }
    )


# Run the application if executed directly
if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run AI Knowledge Forest API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8001")), help="Port to bind to")
    parser.add_argument("--reload", action="store_true", default=settings.api.debug_mode, help="Enable auto-reload")
    args = parser.parse_args()
    
    # Run the application
    uvicorn.run(
        "src.app:app",  # The import string for the app
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )
