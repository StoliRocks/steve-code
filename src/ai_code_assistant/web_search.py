"""Web search functionality for Steve Code."""

import json
import logging
from typing import List, Dict, Optional
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

logger = logging.getLogger(__name__)


class WebSearcher:
    """Provides web search capabilities."""
    
    # We'll use DuckDuckGo HTML search as it doesn't require API keys
    SEARCH_URL = "https://html.duckduckgo.com/html/"
    
    def __init__(self, max_results: int = 5):
        """Initialize the web searcher.
        
        Args:
            max_results: Maximum number of results to return
        """
        self.max_results = max_results
        self.console = Console()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def search(self, query: str) -> List[Dict[str, str]]:
        """Search the web for the given query.
        
        Args:
            query: Search query
            
        Returns:
            List of search results with title, url, and snippet
        """
        try:
            # Make search request
            params = {'q': query}
            response = self.session.post(self.SEARCH_URL, data=params, timeout=10)
            response.raise_for_status()
            
            # Parse results
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Find result divs
            for result_div in soup.find_all('div', class_='result'):
                if len(results) >= self.max_results:
                    break
                
                # Extract title and URL
                title_elem = result_div.find('a', class_='result__a')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')
                
                # Extract snippet
                snippet_elem = result_div.find('a', class_='result__snippet')
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                
                if title and url:
                    results.append({
                        'title': title,
                        'url': url,
                        'snippet': snippet
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch and extract text content from a webpage.
        
        Args:
            url: URL to fetch
            
        Returns:
            Extracted text content or None
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(['script', 'style']):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Limit size
            max_chars = 10000
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
            
            return text
            
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def search_and_summarize(self, query: str, fetch_content: bool = True) -> str:
        """Search and return formatted results.
        
        Args:
            query: Search query
            fetch_content: Whether to fetch page content for top results
            
        Returns:
            Formatted search results
        """
        self.console.print(f"[dim]Searching for: {query}[/dim]")
        
        results = self.search(query)
        
        if not results:
            return "No search results found."
        
        # Format results
        formatted_results = f"## Web Search Results for: {query}\n\n"
        
        for i, result in enumerate(results, 1):
            formatted_results += f"### {i}. {result['title']}\n"
            formatted_results += f"**URL:** {result['url']}\n"
            if result['snippet']:
                formatted_results += f"**Snippet:** {result['snippet']}\n"
            
            # Optionally fetch content from top results
            if fetch_content and i <= 2:  # Only fetch top 2 results
                self.console.print(f"[dim]Fetching content from result {i}...[/dim]")
                content = self.fetch_page_content(result['url'])
                if content:
                    # Truncate content for context
                    preview = content[:1000] + "..." if len(content) > 1000 else content
                    formatted_results += f"\n**Page Preview:**\n```\n{preview}\n```\n"
            
            formatted_results += "\n"
        
        return formatted_results
    
    def format_for_display(self, results: List[Dict[str, str]]) -> None:
        """Display search results in a nice format.
        
        Args:
            results: Search results to display
        """
        if not results:
            self.console.print("[yellow]No search results found[/yellow]")
            return
        
        for i, result in enumerate(results, 1):
            # Create a panel for each result
            content = f"[bold]{result['title']}[/bold]\n"
            content += f"[link={result['url']}]{result['url']}[/link]\n"
            if result['snippet']:
                content += f"\n{result['snippet']}"
            
            self.console.print(Panel(content, title=f"Result {i}", border_style="blue"))


class SmartWebSearch:
    """Enhanced web search with AI-powered summarization."""
    
    def __init__(self, web_searcher: WebSearcher, bedrock_client):
        """Initialize smart web search.
        
        Args:
            web_searcher: WebSearcher instance
            bedrock_client: BedrockClient for AI summarization
        """
        self.web_searcher = web_searcher
        self.bedrock_client = bedrock_client
        self.console = Console()
    
    def search_with_context(self, query: str, context: str = "") -> str:
        """Search and provide AI-summarized results based on context.
        
        Args:
            query: Search query
            context: Additional context for the search
            
        Returns:
            AI-generated summary of search results
        """
        # Get search results
        results = self.web_searcher.search_and_summarize(query, fetch_content=True)
        
        if "No search results found" in results:
            return results
        
        # Create prompt for AI summarization
        prompt = f"""Based on the following web search results, provide a helpful summary that answers the user's query.

User's Query: {query}

Context: {context}

Search Results:
{results}

Please provide a concise, helpful summary that directly addresses the user's query based on the search results. Include relevant links when appropriate."""
        
        # Get AI summary
        from .bedrock_client import Message
        messages = [Message(role="user", content=prompt)]
        
        summary = ""
        self.console.print("[dim]Analyzing search results...[/dim]")
        
        for chunk in self.bedrock_client.send_message(messages, stream=True):
            summary += chunk
        
        return summary