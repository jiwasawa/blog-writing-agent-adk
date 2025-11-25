"""
Example: URL-based Blog Post Creation

This script demonstrates how to create a blog post from URL content.
The agent automatically detects URLs in the request, reads the content,
and creates a blog post based on it.

Key Concepts Demonstrated:
- Custom Tools: The read_link() tool is automatically invoked by the Blog Writer Agent
- URL Processing: Automatic detection and processing of URLs in user input
- Content Extraction: Converting HTML web content to markdown for agent processing

This example shows how the system can:
1. Accept a URL in the user's request
2. Automatically fetch and process the URL content
3. Generate a blog post based on the extracted content
"""

import asyncio
import os
from blog_agent_system import create_blog_post


def extract_blog_text(response):
    """
    Extract the blog post text from an ADK response.
    
    The response from create_blog_post is a list of events.
    This function extracts the text content from the final response event.
    
    Args:
        response: The response object (list of events) from create_blog_post
        
    Returns:
        str: The blog post text content, or the string representation if extraction fails
    """
    # If response is a string, return it directly
    if isinstance(response, str):
        return response
    
    # If response is iterable (list of events), get the last one
    if not hasattr(response, '__iter__'):
        return str(response)
    
    events = list(response)
    if not events:
        return str(response)
    
    # Get the last event which should be the final response
    last_event = events[-1]
    
    # Extract text from content parts
    if hasattr(last_event, 'content') and last_event.content:
        if hasattr(last_event.content, 'parts'):
            text_parts = [
                part.text for part in last_event.content.parts
                if hasattr(part, 'text') and part.text
            ]
            if text_parts:
                return '\n'.join(text_parts)
        
        if hasattr(last_event.content, 'text') and last_event.content.text:
            return last_event.content.text
    
    # If event has text directly
    if hasattr(last_event, 'text') and last_event.text:
        return last_event.text
    
    # Fallback: return string representation
    return str(response)


async def main():
    """Main function to demonstrate URL-based blog post creation."""
    
    # Check if API key is set
    if not os.environ.get("GOOGLE_API_KEY"):
        print("❌ Error: GOOGLE_API_KEY environment variable not set.")
        print("   Please set it before running this script:")
        print("   export GOOGLE_API_KEY='your-api-key-here'")
        return
    
    print("="*80)
    print("Blog Post Creation System - URL Content Example")
    print("="*80)
    print()
    
    # URL-based blog post
    print("Example: Blog Post from URL Content")
    print("-" * 80)
    topic = "Write a blog post based on this transcript of a podcast interview with Satya Nadella: https://www.dwarkesh.com/p/satya-nadella-2"
    print(f"Topic: {topic}\n")
    print("Note: The agent will automatically detect the URL, read its content, and create a blog post based on it.\n")
    
    # Create blog post with custom session
    response = await create_blog_post(topic, session_id="url-blog-session")
    print("\n" + "="*80)
    print("Blog Post:")
    print("="*80)
    blog_text = extract_blog_text(response)
    print(blog_text)


if __name__ == "__main__":
    asyncio.run(main())

