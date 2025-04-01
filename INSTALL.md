# Installation Guide

This guide will help you set up and run the Multi-AI Agent.

## Prerequisites

- Python 3.8 or higher
- API keys for:
  - Google Gemini
  - Anthropic Claude
  - Firecrawl

## Installation

### Using uv (Recommended)

1. Clone the repository:
   ```
   git clone https://your-repo-url/multi_ai_agent.git
   cd multi_ai_agent
   ```

2. Create a virtual environment and install dependencies:
   ```
   uv venv
   uv pip install -e ".[dev]"
   ```

### Using pip

1. Clone the repository:
   ```
   git clone https://your-repo-url/multi_ai_agent.git
   cd multi_ai_agent
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```

## Configuration

1. Create a `.env` file in the project root by copying the example:
   ```
   cp .env.example .env
   ```

2. Edit the `.env` file and add your API keys:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   FIRECRAWL_API_KEY=your_firecrawl_api_key_here
   
   # Optional configuration
   DEFAULT_AI_SERVICE=gemini  # Options: gemini, claude
   MAX_TOKENS=1024
   ```

## Running Tests

Run the tests to make sure everything is working correctly:

```
pytest tests/
```

Or test individual components:

```
pytest tests/test_gemini.py
pytest tests/test_claude.py
pytest tests/test_firecrawl.py
```

## Running the Agent

### Using MCP Inspector (Development Mode)

```
mcp dev src/multi_ai_agent/main.py
```

### Using the CLI

```
# Start the server
multi-ai start

# Generate text
multi-ai generate "Write a poem about AI"

# Generate text with specific service
multi-ai generate "Write a poem about AI" --service claude

# Scrape a URL
multi-ai scrape https://example.com

# Search the web
multi-ai search "What is the Model Context Protocol?"
```

### Using Claude Desktop

To install the Multi-AI Agent in Claude Desktop:

```
mcp install src/multi_ai_agent/main.py --name "Multi-AI Agent"
```

Then open Claude Desktop and use the tools through the interface.

## Troubleshooting

### API Key Issues

If you encounter errors related to API keys:

1. Make sure your `.env` file contains the correct keys
2. Ensure the keys have the necessary permissions
3. Check for any whitespace or extra characters in the keys

### Running the Server

If you encounter issues running the server:

1. Make sure MCP is installed correctly: `mcp --version`
2. Check if Python is in your PATH
3. Try running with verbose output: `mcp dev --verbose src/multi_ai_agent/main.py`
