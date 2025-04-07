#!/usr/bin/env python3
"""Knowledge Graph Visualizer.

This script provides a simple web-based visualization of the knowledge graph.
It fetches the graph data from the API and renders it using D3.js.
"""
import asyncio
import json
import aiohttp
import webbrowser
import os
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from pathlib import Path

# API base URL
API_BASE_URL = "http://localhost:8000"

# HTML template for visualization
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Knowledge Forest Visualization</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            overflow: hidden;
        }
        
        #graph-container {
            width: 100vw;
            height: 100vh;
            background-color: #f5f5f5;
        }
        
        .node {
            stroke: #fff;
            stroke-width: 1.5px;
        }
        
        .link {
            stroke: #999;
            stroke-opacity: 0.6;
            stroke-width: 1px;
        }
        
        .node-label {
            font-size: 12px;
            pointer-events: none;
        }
        
        .tooltip {
            position: absolute;
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            font-size: 12px;
            pointer-events: none;
            max-width: 300px;
            z-index: 10;
            box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.1);
        }
    </style>
</head>
<body>
    <div id="graph-container"></div>
    
    <script>
        // Graph data
        const graphData = GRAPH_DATA_PLACEHOLDER;
        
        // D3.js visualization
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        // Create tooltip
        const tooltip = d3.select("body")
            .append("div")
            .attr("class", "tooltip")
            .style("opacity", 0);
        
        // Create SVG
        const svg = d3.select("#graph-container")
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .attr("viewBox", [0, 0, width, height]);
        
        // Define node colors based on type
        const nodeColors = {
            'topic': "#4682B4",
            'concept': "#6A5ACD",
            'entity': "#2E8B57",
            'keyword': "#CD853F",
            'question': "#8B008B",
            'unknown': "#708090"
        };
        
        // Create simulation
        const simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.edges)
                .id(d => d.id)
                .distance(100))
            .force("charge", d3.forceManyBody().strength(-200))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collide", d3.forceCollide().radius(50));
        
        // Create links
        const link = svg.append("g")
            .selectAll("line")
            .data(graphData.edges)
            .join("line")
            .attr("class", "link")
            .attr("stroke-width", d => d.strength ? d.strength * 2 : 1);
        
        // Create nodes
        const node = svg.append("g")
            .selectAll("circle")
            .data(graphData.nodes)
            .join("circle")
            .attr("class", "node")
            .attr("r", d => d.importance_score ? 5 + d.importance_score * 5 : 8)
            .attr("fill", d => nodeColors[d.type] || nodeColors.unknown)
            .call(drag(simulation))
            .on("mouseover", function(event, d) {
                tooltip.transition()
                    .duration(200)
                    .style("opacity", .9);
                    
                let tooltipContent = `<strong>${d.label}</strong><br/>`;
                tooltipContent += `Type: ${d.type}<br/>`;
                
                if (d.summary) {
                    tooltipContent += `<hr/>${d.summary}`;
                }
                
                tooltip.html(tooltipContent)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            })
            .on("mouseout", function(d) {
                tooltip.transition()
                    .duration(500)
                    .style("opacity", 0);
            });
        
        // Add labels to nodes
        const label = svg.append("g")
            .selectAll("text")
            .data(graphData.nodes)
            .join("text")
            .attr("class", "node-label")
            .text(d => d.label)
            .attr("font-size", 10)
            .attr("dx", 12)
            .attr("dy", 4);
        
        // Update positions on tick
        simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
                
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
                
            label
                .attr("x", d => d.x)
                .attr("y", d => d.y);
        });
        
        // Drag functionality
        function drag(simulation) {
            function dragstarted(event) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                event.subject.fx = event.subject.x;
                event.subject.fy = event.subject.y;
            }
            
            function dragged(event) {
                event.subject.fx = event.x;
                event.subject.fy = event.y;
            }
            
            function dragended(event) {
                if (!event.active) simulation.alphaTarget(0);
                event.subject.fx = null;
                event.subject.fy = null;
            }
            
            return d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended);
        }
    </script>
</body>
</html>
"""

async def fetch_knowledge_graph(user_id):
    """Fetch knowledge graph from API."""
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            f"{API_BASE_URL}/api/public/knowledge/graph?user_id={user_id}"
        )
        
        if response.status == 200:
            return await response.json()
        else:
            error = await response.text()
            print(f"Error fetching knowledge graph: {error}")
            return None

def start_http_server(html_path, port=8080):
    """Start a simple HTTP server to serve the visualization."""
    server_dir = os.path.dirname(html_path)
    os.chdir(server_dir)
    
    # Create server
    server = HTTPServer(('localhost', port), SimpleHTTPRequestHandler)
    
    # Start server in a separate thread
    server_thread = Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    return server, port

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Knowledge Graph Visualizer")
    parser.add_argument("--base-url", help="Base URL for API", default="http://localhost:8000")
    parser.add_argument("--user-id", help="User ID for testing", default="user123")
    parser.add_argument("--port", type=int, help="HTTP server port", default=8080)
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    
    args = parser.parse_args()
    
    global API_BASE_URL
    API_BASE_URL = args.base_url
    user_id = args.user_id
    
    print(f"Fetching knowledge graph for user {user_id}...")
    graph_data = await fetch_knowledge_graph(user_id)
    
    if not graph_data:
        print("Failed to fetch knowledge graph. Exiting.")
        return
    
    print(f"Retrieved graph with {len(graph_data.get('nodes', []))} nodes and {len(graph_data.get('edges', []))} edges.")
    
    # Generate HTML with graph data
    html_content = HTML_TEMPLATE.replace("GRAPH_DATA_PLACEHOLDER", json.dumps(graph_data))
    
    # Create output directory
    output_dir = Path("./visualization")
    output_dir.mkdir(exist_ok=True)
    
    # Write HTML file
    html_path = output_dir / "index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # Start HTTP server
    server, port = start_http_server(html_path, args.port)
    
    # Open browser
    url = f"http://localhost:{port}"
    print(f"Visualization available at: {url}")
    
    if not args.no_browser:
        webbrowser.open(url)
    
    try:
        # Keep server running until interrupted
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nVisualization terminated.")
