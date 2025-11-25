"""
Blog Post Creation System with Link Checking

This system uses three agents:
1. Blog Writer Agent - Creates a draft blog post
2. Link Checker Agent - Uses Google Search to find relevant links and suggests where to insert them
3. Link Integrator Agent - Integrates the suggested links into the blog post to create a final version with embedded links

Features:
- Multi-Agent System: SequentialAgent orchestrates three specialized agents
- Custom Tools: read_link() for URL content extraction
- Built-in Tools: google_search() for link research
- Session Management: Uses InMemorySessionService for conversation state management
- Context Compaction: Automatically compacts conversation history to reduce token usage
- Observability: Logging and event tracking for monitoring and debugging
- Multi-turn Support: Supports conversation continuity across multiple requests

Key Concepts Demonstrated:
- Multi-agent system with sequential orchestration
- Custom and built-in tool integration
- Session and memory management
- Context engineering (compaction)
- Observability (logging, event tracking)
"""

import os
import logging
import httpx
import html2text
from datetime import datetime
from google.adk.agents import Agent, SequentialAgent
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from google.genai import types

# Configure logging for observability
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def setup_api_key():
    """
    Verify Google API key is set in environment variable.
    
    This function checks for the presence of the GOOGLE_API_KEY environment
    variable, which is required for all Gemini API calls. The ADK framework
    will automatically use this environment variable for authentication.
    
    Raises:
        ValueError: If GOOGLE_API_KEY is not set in the environment
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY environment variable not set")
        raise ValueError(
            "GOOGLE_API_KEY environment variable not set. "
            "Please set it before running this script."
        )
    logger.info("API key verified successfully")
    # ADK will automatically use the environment variable


def read_link(url: str) -> dict:
    """
    Custom tool: Reads a URL and converts its content to markdown format.
    
    This is a custom tool that fetches content from a given URL and converts HTML
    to markdown, making it easy for agents to process web content. It demonstrates
    custom tool development with proper error handling and structured responses.
    
    The tool handles various error conditions gracefully and returns structured
    responses following ADK patterns. This enables the Blog Writer Agent to
    automatically read and process content from URLs provided by users.
    
    Args:
        url: The URL to read and convert to markdown. Must be a valid HTTP/HTTPS URL.
        
    Returns:
        Dictionary with status and content information:
        - Success: {"status": "success", "content": "markdown content from the URL"}
        - Error: {"status": "error", "error_message": "description of what went wrong"}
        
    Examples:
        >>> read_link("https://example.com/article")
        {"status": "success", "content": "# Article Title\n\nArticle content..."}
        
        >>> read_link("https://invalid-url-that-does-not-exist.com")
        {"status": "error", "error_message": "Failed to fetch URL: ..."}
    
    Observability:
        This tool logs all operations for monitoring:
        - Tool invocation with URL
        - Success/failure status
        - Error details when failures occur
    """
    logger.info(f"Tool invoked: read_link(url='{url}')")
    start_time = datetime.now()
    
    # Validate URL format
    if not url.startswith(("http://", "https://")):
        error_msg = f"Invalid URL format. URL must start with http:// or https://. Got: {url}"
        logger.warning(f"read_link failed: {error_msg}")
        return {
            "status": "error",
            "error_message": error_msg,
        }
    
    # Fetch the URL content with timeout and redirect following
    try:
        logger.debug(f"Fetching URL: {url}")
        response = httpx.get(url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
        logger.info(f"Successfully fetched URL: {url} (status: {response.status_code})")
    except httpx.TimeoutException:
        error_msg = f"Request timeout: The URL {url} did not respond within 30 seconds."
        logger.error(f"read_link timeout: {error_msg}")
        return {
            "status": "error",
            "error_message": error_msg,
        }
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code}: Failed to fetch {url}"
        logger.error(f"read_link HTTP error: {error_msg}")
        return {
            "status": "error",
            "error_message": error_msg,
        }
    except httpx.RequestError as e:
        error_msg = f"Network error while fetching {url}: {str(e)}"
        logger.error(f"read_link network error: {error_msg}")
        return {
            "status": "error",
            "error_message": error_msg,
        }
    
    # Convert HTML to markdown
    html_content = response.text
    h = html2text.HTML2Text()
    h.ignore_links = False  # Keep links in markdown
    h.ignore_images = False  # Keep images in markdown
    h.body_width = 0  # Don't wrap lines
    
    markdown_content = h.handle(html_content)
    
    if not markdown_content or not markdown_content.strip():
        error_msg = f"URL {url} returned empty or non-HTML content."
        logger.warning(f"read_link empty content: {error_msg}")
        return {
            "status": "error",
            "error_message": error_msg,
        }
    
    duration = (datetime.now() - start_time).total_seconds()
    content_length = len(markdown_content)
    logger.info(f"read_link completed successfully: {content_length} chars in {duration:.2f}s")
    
    return {
        "status": "success",
        "content": markdown_content,
    }


def create_blog_agent_system():
    """
    Create a three-agent system for blog post creation, link checking, and link integration.
    
    This function constructs a SequentialAgent that orchestrates three specialized agents:
    1. Blog Writer Agent - Creates initial blog post drafts
    2. Link Checker Agent - Researches and suggests relevant links
    3. Link Integrator Agent - Integrates links into the final blog post
    
    The agents communicate through session state, with each agent's output serving as
    input to the next agent in the sequence. This demonstrates multi-agent orchestration
    and agent-to-agent communication patterns.
    
    Architecture:
        SequentialAgent (root)
        ├── BlogWriterAgent (with read_link tool)
        ├── LinkCheckerAgent (with google_search tool)
        └── LinkIntegratorAgent (final integration)
    
    Returns:
        SequentialAgent: The root agent that orchestrates blog writing, link checking, and link integration
    
    Observability:
        Logs agent system creation and configuration for monitoring.
    """
    logger.info("Creating blog agent system with 3 specialized agents")
    
    # Configure retry options for API calls
    # This handles rate limits and transient errors gracefully
    retry_config = types.HttpRetryOptions(
        attempts=5,              # Retry up to 5 times
        exp_base=7,             # Exponential backoff base
        initial_delay=1,        # Initial delay in seconds
        http_status_codes=[429, 500, 503, 504],  # Retry on these status codes
    )
    logger.debug(f"Retry configuration: {retry_config}")

    # Agent 1: Blog Writer Agent
    # This agent creates the initial blog post draft
    # It can write from scratch or process content from URLs using the read_link tool
    logger.info("Creating BlogWriterAgent with read_link tool")
    blog_writer_agent = Agent(
        name="BlogWriterAgent",
        model=Gemini(
            model="gemini-2.5-flash-lite",  # Fast and cost-effective model
            retry_options=retry_config
        ),
        description="A specialized agent that writes blog post drafts on given topics or based on URL content.",
        instruction="""You are a professional blog writer. Your task is to write a well-structured 
        blog post draft based on the user's topic or request.
        
        IMPORTANT: Check if the user's request contains a URL (http:// or https://).
        - If a URL is present, you MUST first use the read_link() tool to fetch and read the content from that URL.
        - Base your blog post on the markdown content retrieved from the URL.
        - If the read_link() tool returns an error, inform the user about the issue and proceed with writing based on the topic if possible.
        - If no URL is present, proceed with normal blog writing based on the user's topic.
        
        Guidelines:
        - Write a compelling introduction that hooks the reader
        - Create clear sections with descriptive headings
        - Use engaging, informative content
        - Write 500-800 words
        - Include a conclusion that summarizes key points
        - Write in a clear, professional tone
        - When writing based on URL content, synthesize and summarize the information in your own words
        - Do not simply copy the content; create an original blog post inspired by the source material
        
        Output only the blog post content without any meta-commentary.""",
        tools=[read_link],  # Custom tool for URL content extraction
        output_key="blog_draft",  # Store the draft in session state for next agent
    )

    # Agent 2: Link Checker Agent
    # This agent uses Google Search to find relevant links and suggests where to insert them
    # It reads the blog_draft from session state and uses google_search tool
    logger.info("Creating LinkCheckerAgent with google_search tool")
    link_checker_agent = Agent(
        name="LinkCheckerAgent",
        model=Gemini(
            model="gemini-2.5-flash-lite",
            retry_options=retry_config
        ),
        description="An agent that finds relevant links using Google Search and suggests where to insert them in blog posts.",
        instruction="""You are a link research specialist. Your task is to review a blog post draft 
        and find relevant, high-quality links that would enhance the content.
        
        Process:
        1. Read the blog draft provided: {blog_draft}
        2. Identify key topics, concepts, and claims that would benefit from external links
        3. Use Google Search to find authoritative sources for each topic
        4. For each relevant link found, specify:
           - The exact text or phrase in the blog where the link should be inserted
           - The URL of the link
           - A brief explanation of why this link is relevant
        
        Output format:
        Provide your suggestions in a clear format:
        
        **Link Suggestions:**
        
        1. **Location**: [exact text from blog where link should go]
           **URL**: [link URL]
           **Reason**: [why this link is relevant]
        
        2. [Continue for each link...]
        
        Focus on:
        - Authoritative sources (official websites, reputable publications)
        - Recent and relevant information
        - Links that add value to the reader
        - 3-5 high-quality links maximum
        
        If you cannot find relevant links for certain sections, note that as well.""",
        tools=[google_search],  # Built-in tool for Google Search API
        output_key="link_suggestions",  # Store link suggestions in session state for next agent
    )

    # Agent 3: Link Integrator Agent
    # This agent integrates the suggested links into the blog post
    # It reads both blog_draft and link_suggestions from session state
    logger.info("Creating LinkIntegratorAgent for final link integration")
    link_integrator_agent = Agent(
        name="LinkIntegratorAgent",
        model=Gemini(
            model="gemini-2.5-flash-lite",
            retry_options=retry_config
        ),
        description="An agent that integrates suggested links into blog posts, creating a final version with embedded markdown links.",
        instruction="""You are a link integration specialist. Your task is to integrate suggested links into a blog post draft.

        Process:
        1. Read the original blog draft: {blog_draft}
        2. Read the link suggestions: {link_suggestions}
        3. Parse the link suggestions to extract:
           - The exact text or phrase where each link should be inserted
           - The URL for each link
        4. For each link suggestion:
           - Find the matching text in the blog draft
           - Replace or wrap the text with markdown link syntax: [text](url)
           - Ensure the link is properly formatted and doesn't break the markdown structure
        5. If a suggested location text appears multiple times, use context to determine the best match
        6. If a location text cannot be found exactly, find the closest match or similar phrase
        7. Preserve all original formatting, headings, and structure of the blog post
        8. Ensure all links are properly formatted as markdown: [link text](https://url.com)
        
        Output format:
        Output the complete blog post with all links integrated. The output should be:
        - The full blog post content
        - With markdown links embedded at the suggested locations
        - Properly formatted markdown
        - No additional commentary or explanations
        
        Important:
        - Only integrate links that were suggested in the link_suggestions
        - Maintain the original blog post structure and flow
        - Ensure links are contextually appropriate and enhance readability
        - If you cannot find a match for a suggested link location, skip that link but note it in a brief comment if necessary""",
        output_key="final_blog_post",  # Final output with integrated links
    )

    # Create a SequentialAgent to orchestrate the workflow
    # This ensures the blog is written first, then links are checked, then links are integrated
    # The SequentialAgent manages the flow of data between agents through session state
    logger.info("Creating SequentialAgent to orchestrate the three-agent workflow")
    root_agent = SequentialAgent(
        name="BlogPostSystem",
        sub_agents=[blog_writer_agent, link_checker_agent, link_integrator_agent],
    )
    
    logger.info("Blog agent system created successfully")
    return root_agent


async def create_blog_post(topic: str, session_id: str = "default", user_id: str = "default"):
    """
    Create a blog post with link suggestions using session management and context compaction.
    
    This is the main entry point for the blog post creation system. It orchestrates
    the entire workflow from topic to final blog post with integrated links.
    
    The function demonstrates several key concepts:
    - Session Management: Uses InMemorySessionService to maintain conversation state
    - Context Engineering: Implements EventsCompactionConfig to reduce token usage
    - Multi-Agent Orchestration: Runs the sequential agent system
    - Observability: Logs all major operations for monitoring
    
    Args:
        topic: The topic or prompt for the blog post. Can include URLs (http:// or https://)
        session_id: Optional session ID for conversation continuity (default: "default")
                   Use the same session_id across multiple calls for multi-turn conversations
        user_id: Optional user ID for multi-user support (default: "default")
        
    Returns:
        List of events from the agent system. The final event contains the blog post content.
        Use the extract_blog_text() helper function in examples to extract text content.
        
    Raises:
        ValueError: If GOOGLE_API_KEY is not set in environment variables
    
    Example:
        >>> response = await create_blog_post("Write about AI agents")
        >>> blog_text = extract_blog_text(response)
        >>> print(blog_text)
    
    Observability:
        This function logs:
        - Session creation/retrieval
        - Agent execution start/completion
        - Event collection
        - Error conditions
    """
    logger.info(f"Starting blog post creation: topic='{topic[:50]}...', session_id='{session_id}', user_id='{user_id}'")
    start_time = datetime.now()
    
    # Verify API key is set
    setup_api_key()
    
    # Create the agent system
    logger.debug("Creating agent system")
    agent_system = create_blog_agent_system()
    
    # Create session service for conversation management
    # InMemorySessionService stores session state in memory
    # For production, consider using a persistent session service
    logger.debug("Initializing InMemorySessionService")
    session_service = InMemorySessionService()
    
    # Create App with context compaction configuration
    # This automatically compacts conversation history to reduce token usage
    # Context compaction is a key feature for cost optimization
    logger.debug("Creating App with context compaction (interval=5, overlap=2)")
    app = App(
        name="blog_post_app",
        root_agent=agent_system,
        events_compaction_config=EventsCompactionConfig(
            compaction_interval=5,  # Compact after every 5 agent turns
            overlap_size=2,  # Keep 2 previous turns for context continuity
        ),
    )
    
    # Create runner with session service and app
    # The Runner manages the execution of the agent system
    logger.debug("Creating Runner")
    runner = Runner(
        app=app,
        session_service=session_service,
    )
    
    # Create or retrieve session
    # Sessions maintain conversation state across multiple requests
    try:
        logger.info(f"Creating new session: session_id='{session_id}', user_id='{user_id}'")
        session = await session_service.create_session(
            app_name=app.name,
            user_id=user_id,
            session_id=session_id,
        )
        logger.info(f"Session created: {session.id}")
    except Exception as e:
        # Session already exists, retrieve it
        logger.info(f"Session exists, retrieving: session_id='{session_id}', user_id='{user_id}'")
        session = await session_service.get_session(
            app_name=app.name,
            user_id=user_id,
            session_id=session_id,
        )
        logger.info(f"Session retrieved: {session.id}")
    
    # Convert topic to Content format required by ADK
    user_message = types.Content(
        role="user",
        parts=[types.Part(text=topic)]
    )
    
    # Run the agent with proper session management
    # Collect all events for observability and debugging
    logger.info("Starting agent execution")
    event_count = 0
    events = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=user_message,
    ):
        events.append(event)
        event_count += 1
        # Log significant events for observability
        if hasattr(event, 'agent_name'):
            logger.debug(f"Event from {event.agent_name}: {type(event).__name__}")
    
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"Blog post creation completed: {event_count} events in {duration:.2f}s")
    
    # Return events list (compatible with existing code that expects iterable)
    return events


# Example usage
if __name__ == "__main__":
    import asyncio
    
    # Example: Create a blog post about AI agents
    topic = "Write a blog post about the benefits of using AI agents for content creation"
    
    print("🚀 Starting blog post creation system...")
    print(f"📝 Topic: {topic}\n")
    
    # Run the async function
    response = asyncio.run(create_blog_post(topic))
    
    print("\n✅ Blog post creation complete!")
    print("\n" + "="*80)
    print("FINAL OUTPUT:")
    print("="*80)
    print(response)

