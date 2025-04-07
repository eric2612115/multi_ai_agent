#!/usr/bin/env python3
"""Test client for AI Knowledge Forest API.

This script provides a command-line interface for testing the API.
"""
import asyncio
import json
import uuid
import sys
import argparse
import aiohttp
import websockets
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown

# Create console for rich output
console = Console()

# API base URL
API_BASE_URL = "http://localhost:8001"

async def test_auth():
    """Test user authentication."""
    console.print("\n[bold cyan]Testing Authentication[/bold cyan]")
    
    # Login with default credentials
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            f"{API_BASE_URL}/api/auth/login",
            data={
                "username": "user123",
                "password": "forest2024"
            }
        )
        
        if response.status == 200:
            data = await response.json()
            token = data.get("access_token")
            console.print("[green]Login successful[/green]")
            console.print(f"User: [bold]{data.get('user', {}).get('username')}[/bold]")
            return token
        else:
            error = await response.text()
            console.print(f"[red]Login failed: {error}[/red]")
            return None

async def test_public_api():
    """Test public API endpoints."""
    console.print("\n[bold cyan]Testing Public API Endpoints[/bold cyan]")
    
    user_id = "user123"  # Fixed test user ID
    
    # Test knowledge graph retrieval
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            f"{API_BASE_URL}/api/public/knowledge/graph?user_id={user_id}"
        )
        
        if response.status == 200:
            data = await response.json()
            nodes_count = len(data.get("nodes", []))
            edges_count = len(data.get("edges", []))
            console.print(f"[green]Knowledge graph retrieved successfully[/green]")
            console.print(f"Nodes: {nodes_count}, Edges: {edges_count}")
        else:
            error = await response.text()
            console.print(f"[red]Failed to retrieve knowledge graph: {error}[/red]")
    
    # Test knowledge search
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            f"{API_BASE_URL}/api/public/knowledge/search?query=test&user_id={user_id}"
        )
        
        if response.status == 200:
            data = await response.json()
            results_count = len(data.get("results", []))
            console.print(f"[green]Knowledge search completed successfully[/green]")
            console.print(f"Results: {results_count}")
        else:
            error = await response.text()
            console.print(f"[red]Failed to search knowledge: {error}[/red]")
    
    # Test conversation retrieval
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            f"{API_BASE_URL}/api/public/conversations/user/{user_id}"
        )
        
        if response.status == 200:
            data = await response.json()
            conversations_count = len(data.get("conversations", []))
            console.print(f"[green]Conversations retrieved successfully[/green]")
            console.print(f"Conversations: {conversations_count}")
        else:
            error = await response.text()
            console.print(f"[red]Failed to retrieve conversations: {error}[/red]")

async def create_conversation(user_id: str, title: str = None):
    """Create a new conversation."""
    console.print("\n[bold cyan]Creating New Conversation[/bold cyan]")
    
    # Generate a title if none provided
    if not title:
        title = f"Test Conversation {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            f"{API_BASE_URL}/api/public/conversations/",
            json={
                "user_id": user_id,
                "title": title
            }
        )
        
        if response.status == 200:
            data = await response.json()
            conversation_id = data.get("id")
            console.print(f"[green]Conversation created successfully[/green]")
            console.print(f"ID: [bold]{conversation_id}[/bold], Title: {title}")
            return conversation_id
        else:
            error = await response.text()
            console.print(f"[red]Failed to create conversation: {error}[/red]")
            return None

async def test_websocket_chat(user_id: str, conversation_id: Optional[str] = None):
    """Test WebSocket chat functionality."""
    console.print("\n[bold cyan]Testing WebSocket Chat[/bold cyan]")
    
    # Create WebSocket URL with user_id and optional conversation_id
    ws_url = f"ws://localhost:8001/ws/chat/ws?user_id={user_id}"
    if conversation_id:
        ws_url += f"&conversation_id={conversation_id}"
    
    console.print(f"Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            # Wait for welcome message
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            console.print(f"[green]Connected successfully[/green]")
            console.print(Panel(welcome_data.get("text", "Welcome message"), title="Server"))
            
            # Interactive chat loop
            console.print("\n[bold]Interactive Chat Session[/bold] (Type 'exit' to quit)")
            while True:
                user_message = Prompt.ask("You")
                if user_message.lower() == "exit":
                    break
                
                # Send message to server
                await websocket.send(json.dumps({
                    "query": user_message,
                    "options": {
                        "conversation_id": conversation_id,
                        "enhanced": False
                    }
                }))
                
                # Receive responses
                while True:
                    response = await websocket.recv()
                    response_data = json.loads(response)
                    
                    message_type = response_data.get("message_type", "")
                    
                    # Display based on message type
                    if message_type == "message" and response_data.get("sender") == "user":
                        # User message echo - skip
                        pass
                    elif message_type == "thinking":
                        console.print(f"[yellow]{response_data.get('text', 'Thinking...')}[/yellow]")
                    elif message_type == "message" and response_data.get("sender") == "ai":
                        # AI response - display and break the receiving loop
                        ai_response = response_data.get("text", "")
                        console.print(Panel(Markdown(ai_response), title="AI", border_style="green"))
                        break
                    elif message_type == "error":
                        console.print(f"[red]Error: {response_data.get('text')}[/red]")
                        break
                    elif message_type == "heartbeat" or message_type == "ping":
                        # Ignore heartbeats
                        pass
                    else:
                        # Other message types
                        console.print(f"[blue]Received: {json.dumps(response_data)}[/blue]")
            
            console.print("[yellow]Chat session ended[/yellow]")
            
    except Exception as e:
        console.print(f"[red]WebSocket error: {str(e)}[/red]")

async def extract_knowledge(user_id: str, conversation_id: str, content: str):
    """Test knowledge extraction."""
    console.print("\n[bold cyan]Testing Knowledge Extraction[/bold cyan]")
    
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            f"{API_BASE_URL}/api/public/knowledge/extract",
            json={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "content": content
            }
        )
        
        if response.status == 200:
            data = await response.json()
            task_id = data.get("task_id")
            console.print(f"[green]Knowledge extraction task created successfully[/green]")
            console.print(f"Task ID: [bold]{task_id}[/bold]")
            
            # Check task status
            status = await check_task_status(task_id)
            return status
        else:
            error = await response.text()
            console.print(f"[red]Failed to extract knowledge: {error}[/red]")
            return None

async def check_task_status(task_id: str):
    """Check the status of a task."""
    console.print(f"\n[bold cyan]Checking Task Status: {task_id}[/bold cyan]")
    
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            f"{API_BASE_URL}/api/public/knowledge/task/{task_id}"
        )
        
        if response.status == 200:
            data = await response.json()
            status = data.get("status")
            console.print(f"[green]Task status: {status}[/green]")
            console.print(f"Message: {data.get('message')}")
            return data
        else:
            error = await response.text()
            console.print(f"[red]Failed to check task status: {error}[/red]")
            return None

async def view_node(user_id: str, node_id: str):
    """View details of a knowledge node."""
    console.print(f"\n[bold cyan]Viewing Node: {node_id}[/bold cyan]")
    
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            f"{API_BASE_URL}/api/public/knowledge/node/{node_id}?user_id={user_id}&include_neighbors=true"
        )
        
        if response.status == 200:
            data = await response.json()
            console.print(f"[green]Node retrieved successfully[/green]")
            
            # Create table for node details
            table = Table(title=f"Node: {data.get('label')}")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("ID", data.get("id"))
            table.add_row("Type", data.get("type"))
            table.add_row("Summary", data.get("summary"))
            table.add_row("Created", data.get("created_at"))
            table.add_row("Updated", data.get("updated_at"))
            
            console.print(table)
            
            # Display neighbors if available
            neighbors = data.get("neighbors", [])
            if neighbors:
                neigh_table = Table(title="Connected Nodes")
                neigh_table.add_column("ID", style="dim")
                neigh_table.add_column("Label", style="cyan")
                neigh_table.add_column("Type", style="green")
                
                for neighbor in neighbors:
                    neigh_table.add_row(
                        neighbor.get("id"),
                        neighbor.get("label"),
                        neighbor.get("type")
                    )
                
                console.print(neigh_table)
            
            return data
        else:
            error = await response.text()
            console.print(f"[red]Failed to retrieve node: {error}[/red]")
            return None

async def test_thinking_mode(user_id: str, conversation_id: str):
    """Test AI thinking mode."""
    console.print("\n[bold cyan]Testing AI Thinking Mode[/bold cyan]")
    
    # Create WebSocket URL with user_id and conversation_id
    ws_url = f"ws://localhost:8001/ws/chat/ws?user_id={user_id}&conversation_id={conversation_id}"
    
    try:
        async with websockets.connect(ws_url) as websocket:
            # Wait for welcome message
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            console.print(f"[green]Connected successfully[/green]")
            
            # Ask a complex question that requires thinking
            question = "Can you analyze the environmental impact of electric vehicles compared to traditional combustion engine vehicles? Consider manufacturing, operation, and end-of-life disposal."
            
            console.print(f"[bold]Asking complex question with thinking mode:[/bold]")
            console.print(question)
            
            # Send message with thinking mode enabled
            await websocket.send(json.dumps({
                "query": question,
                "options": {
                    "conversation_id": conversation_id,
                    "thinking": True  # Enable thinking mode
                }
            }))
            
            # Receive responses
            thinking_steps = []
            final_response = None
            
            while True:
                response = await websocket.recv()
                response_data = json.loads(response)
                
                message_type = response_data.get("message_type", "")
                
                if message_type == "message" and response_data.get("sender") == "user":
                    # User message echo - skip
                    pass
                elif message_type == "thinking":
                    # Collect thinking steps
                    thinking_text = response_data.get("text", "")
                    thinking_steps.append(thinking_text)
                    console.print(f"[yellow]Thinking: {thinking_text}[/yellow]")
                elif message_type == "message" and response_data.get("sender") == "ai":
                    # Final AI response
                    final_response = response_data.get("text", "")
                    console.print(Panel(Markdown(final_response), title="AI Final Response", border_style="green"))
                    break
                elif message_type == "error":
                    console.print(f"[red]Error: {response_data.get('text')}[/red]")
                    break
                elif message_type == "heartbeat" or message_type == "ping":
                    # Ignore heartbeats
                    pass
                else:
                    # Other message types
                    console.print(f"[blue]Received: {json.dumps(response_data)}[/blue]")
            
            # Results summary
            console.print(f"[green]Thinking mode test completed[/green]")
            console.print(f"Thinking steps: {len(thinking_steps)}")
            return {
                "thinking_steps": thinking_steps,
                "final_response": final_response
            }
            
    except Exception as e:
        console.print(f"[red]WebSocket error: {str(e)}[/red]")
        return None

async def test_memory(user_id: str):
    """Test conversation memory across multiple messages."""
    console.print("\n[bold cyan]Testing Conversation Memory[/bold cyan]")
    
    # Create a new conversation for this test
    conversation_id = await create_conversation(user_id, "Memory Test Conversation")
    if not conversation_id:
        console.print("[red]Failed to create conversation for memory test[/red]")
        return
    
    # Connect to WebSocket
    ws_url = f"ws://localhost:8001/ws/chat/ws?user_id={user_id}&conversation_id={conversation_id}"
    
    try:
        async with websockets.connect(ws_url) as websocket:
            # Wait for welcome message
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            console.print(f"[green]Connected successfully[/green]")
            
            # Series of related messages to test memory
            messages = [
                "My name is Test User.",
                "I'm interested in machine learning.",
                "What was my name again?",
                "What field did I say I was interested in?"
            ]
            
            responses = []
            
            for i, message in enumerate(messages):
                console.print(f"\n[bold]Message {i+1}:[/bold] {message}")
                
                # Send message
                await websocket.send(json.dumps({
                    "query": message,
                    "options": {
                        "conversation_id": conversation_id
                    }
                }))
                
                # Receive all responses until we get the AI message
                while True:
                    response = await websocket.recv()
                    response_data = json.loads(response)
                    
                    message_type = response_data.get("message_type", "")
                    
                    if message_type == "message" and response_data.get("sender") == "ai":
                        # AI response
                        ai_response = response_data.get("text", "")
                        console.print(Panel(ai_response, title=f"AI Response {i+1}", border_style="green"))
                        responses.append(ai_response)
                        break
                    elif message_type == "error":
                        console.print(f"[red]Error: {response_data.get('text')}[/red]")
                        break
                    elif message_type not in ["message", "thinking", "heartbeat", "ping"]:
                        # Other message types (except known types to ignore)
                        console.print(f"[blue]Received: {json.dumps(response_data)}[/blue]")
                
                # Brief pause between messages
                await asyncio.sleep(1)
            
            # Memory test evaluation
            memory_successful = False
            if len(responses) >= 4:
                # Check if responses to questions 3 and 4 mention the information provided earlier
                question3_response = responses[2].lower()
                question4_response = responses[3].lower()
                
                name_remembered = "test user" in question3_response
                interest_remembered = "machine learning" in question4_response
                
                if name_remembered and interest_remembered:
                    console.print("[green]Memory test PASSED: AI remembered both name and interest[/green]")
                    memory_successful = True
                elif name_remembered:
                    console.print("[yellow]Memory test PARTIAL: AI remembered name but not interest[/yellow]")
                elif interest_remembered:
                    console.print("[yellow]Memory test PARTIAL: AI remembered interest but not name[/yellow]")
                else:
                    console.print("[red]Memory test FAILED: AI didn't remember information[/red]")
            
            return {
                "conversation_id": conversation_id,
                "memory_successful": memory_successful,
                "responses": responses
            }
            
    except Exception as e:
        console.print(f"[red]WebSocket error: {str(e)}[/red]")
        return None

async def test_reflection(user_id: str):
    """Test the reflection system's cognitive abilities."""
    console.print("\n[bold cyan]Testing Reflection System[/bold cyan]")
    
    async with aiohttp.ClientSession() as session:
        # Trigger a reflection cycle
        response = await session.post(
            f"{API_BASE_URL}/api/reflection/trigger",
            json={
                "user_id": user_id
            }
        )
        
        if response.status == 200:
            data = await response.json()
            cycle_id = data.get("cycle_id")
            console.print(f"[green]Reflection cycle triggered successfully[/green]")
            console.print(f"Cycle ID: [bold]{cycle_id}[/bold]")
            
            # Wait for the cycle to complete (may take time)
            console.print("[yellow]Waiting for reflection cycle to complete...[/yellow]")
            await asyncio.sleep(5)
            
            # Check cycle status
            cycle_data = await check_reflection_cycle(user_id, cycle_id)
            return cycle_data
        else:
            error = await response.text()
            console.print(f"[red]Failed to trigger reflection cycle: {error}[/red]")
            return None

async def check_reflection_cycle(user_id: str, cycle_id: str):
    """Check the status of a reflection cycle."""
    console.print(f"\n[bold cyan]Checking Reflection Cycle: {cycle_id}[/bold cyan]")
    
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            f"{API_BASE_URL}/api/reflection/cycle/{cycle_id}?user_id={user_id}"
        )
        
        if response.status == 200:
            data = await response.json()
            status = data.get("status")
            console.print(f"[green]Cycle status: {status}[/green]")
            
            # Display cycle summary
            if data.get("summary"):
                console.print(Panel(data.get("summary"), title="Cycle Summary", border_style="green"))
            
            # Display identified gaps
            gaps = data.get("identified_gaps", [])
            if gaps:
                gap_table = Table(title="Identified Knowledge Gaps")
                gap_table.add_column("Type", style="cyan")
                gap_table.add_column("Description", style="green")
                gap_table.add_column("Severity", style="yellow")
                
                for gap in gaps:
                    gap_table.add_row(
                        gap.get("type", "Unknown"),
                        gap.get("description", "No description"),
                        f"{float(gap.get('severity', 0)) * 100:.0f}%"
                    )
                
                console.print(gap_table)
            
            # Display planned tasks
            tasks = data.get("planned_tasks", [])
            if tasks:
                task_table = Table(title="Planned Tasks")
                task_table.add_column("Type", style="cyan")
                task_table.add_column("Priority", style="green")
                task_table.add_column("Energy", style="yellow")
                
                for task in tasks:
                    task_table.add_row(
                        task.get("type", "Unknown"),
                        str(task.get("priority", 0)),
                        f"{float(task.get('energy_cost', 0)):.1f}"
                    )
                
                console.print(task_table)
            
            # Display quality check results
            quality = data.get("quality_check_results", {})
            if quality:
                console.print(f"Knowledge Quality Score: [bold]{float(quality.get('quality_score', 0)) * 100:.1f}%[/bold]")
                
                failed_rules = [r for r in quality.get("rule_results", []) if r.get("passes") is False]
                if failed_rules:
                    rule_table = Table(title="Failed Quality Rules")
                    rule_table.add_column("Rule", style="cyan")
                    rule_table.add_column("Explanation", style="yellow")
                    
                    for rule in failed_rules:
                        rule_table.add_row(
                            rule.get("rule_name", "Unknown"),
                            rule.get("explanation", "No explanation")
                        )
                    
                    console.print(rule_table)
            
            return data
        else:
            error = await response.text()
            console.print(f"[red]Failed to check reflection cycle: {error}[/red]")
            return None

async def view_knowledge_quality(user_id: str):
    """View knowledge quality metrics."""
    console.print("\n[bold cyan]Viewing Knowledge Quality Metrics[/bold cyan]")
    
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            f"{API_BASE_URL}/api/knowledge/quality?user_id={user_id}"
        )
        
        if response.status == 200:
            data = await response.json()
            console.print(f"[green]Knowledge quality metrics retrieved successfully[/green]")
            
            # Display overall quality
            overall_quality = data.get("overall_quality", 0)
            console.print(f"Overall Knowledge Quality: [bold]{overall_quality * 100:.1f}%[/bold]")
            
            # Display metrics
            metrics = data.get("metrics", {})
            if metrics:
                metric_table = Table(title="Knowledge Quality Metrics")
                metric_table.add_column("Metric", style="cyan")
                metric_table.add_column("Value", style="green")
                
                for key, value in metrics.items():
                    formatted_value = f"{value:.2f}" if isinstance(value, float) else str(value)
                    metric_table.add_row(key, formatted_value)
                
                console.print(metric_table)
            
            return data
        else:
            error = await response.text()
            console.print(f"[red]Failed to retrieve knowledge quality metrics: {error}[/red]")
            return None

async def main():
    """Main function to run the tests."""
    parser = argparse.ArgumentParser(description="AI Knowledge Forest Test Client")
    parser.add_argument("--test", "-t", choices=["all", "auth", "api", "chat", "extract", "memory", "thinking", "reflection", "quality"], 
                       default="all", help="Test to run")
    parser.add_argument("--user", "-u", default="user123", help="User ID for testing")
    
    args = parser.parse_args()
    
    # Banner
    console.print(Panel(
        "[bold green]AI Knowledge Forest Test Client[/bold green]\n"
        "This tool tests the functionality of the AI Knowledge Forest API",
        title="Welcome",
        border_style="blue"
    ))
    
    # Run the selected test
    test_type = args.test
    user_id = args.user
    
    if test_type in ["all", "auth"]:
        token = await test_auth()
    
    if test_type in ["all", "api"]:
        await test_public_api()
    
    if test_type in ["all", "chat"]:
        conversation_id = await create_conversation(user_id)
        if conversation_id:
            await test_websocket_chat(user_id, conversation_id)
    
    if test_type in ["all", "extract"]:
        conversation_id = await create_conversation(user_id, "Knowledge Extraction Test")
        if conversation_id:
            content = """
            Artificial Intelligence (AI) refers to computer systems designed to perform tasks 
            that typically require human intelligence. These tasks include learning, reasoning, 
            problem-solving, perception, and language understanding. Machine Learning (ML) is a 
            subset of AI that focuses on enabling systems to learn from data without being explicitly 
            programmed. Deep Learning is a specialized form of ML that uses neural networks with many 
            layers (hence "deep") to analyze various factors of data. Key components of AI systems include 
            algorithms, training data, and computational resources. Ethical considerations in AI development 
            include privacy concerns, bias in decision-making, accountability for AI actions, and long-term 
            societal impacts.
            """
            await extract_knowledge(user_id, conversation_id, content)
            
            # Allow some time for processing to complete
            console.print("[yellow]Waiting for knowledge extraction to process...[/yellow]")
            await asyncio.sleep(10)
            
            # View the knowledge graph
            await test_public_api()
    
    if test_type in ["all", "memory"]:
        await test_memory(user_id)
    
    if test_type in ["all", "thinking"]:
        conversation_id = await create_conversation(user_id, "Thinking Mode Test")
        if conversation_id:
            await test_thinking_mode(user_id, conversation_id)
            
    if test_type in ["all", "reflection"]:
        await test_reflection(user_id)
        
    if test_type in ["all", "quality"]:
        await view_knowledge_quality(user_id)

if __name__ == "__main__":
    asyncio.run(main())
