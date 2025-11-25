"""
Example: Multi-turn Conversation with Session Management

This script demonstrates how to use session management for conversation continuity.
The agent maintains context across multiple requests when using the same session_id.

Key Concepts Demonstrated:
- Session Management: Using InMemorySessionService to maintain conversation state
- Multi-turn Conversations: Maintaining context across multiple agent interactions
- State Persistence: Session state is preserved between requests

This example shows how to:
1. Create an initial blog post
2. Request modifications in a follow-up request
3. Maintain conversation context using the same session_id
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
    """Main function to demonstrate multi-turn conversation with session management."""
    
    # Check if API key is set
    if not os.environ.get("GOOGLE_API_KEY"):
        print("❌ Error: GOOGLE_API_KEY environment variable not set.")
        print("   Please set it before running this script:")
        print("   export GOOGLE_API_KEY='your-api-key-here'")
        return
    
    print("="*80)
    print("Blog Post Creation System - Multi-turn Conversation Example")
    print("="*80)
    print()
    print("Demonstrating session continuity - the agent can reference previous conversations.\n")
    
    # First turn: Create initial blog post
    print("Turn 1: Creating initial blog post...")
    print("-" * 80)
    response1 = await create_blog_post(
        "Write a blog post about the benefits of AI agents for content creation",
        session_id="multi-turn-session",
        user_id="demo_user"
    )
    print("✅ Initial blog post created in session 'multi-turn-session'")
    blog_text1 = extract_blog_text(response1)
    print("\nBlog Post:")
    print("-" * 80)
    print(blog_text1[:500] + "..." if len(blog_text1) > 500 else blog_text1)
    
    # Second turn: Request modifications (session maintains context)
    print("\n\nTurn 2: Requesting modifications to the blog post...")
    print("-" * 80)
    # Include the previous blog post in the request so the agent can revise it
    # In a real application, you might retrieve this from session state
    revision_request = f"""Please revise the following blog post to make the introduction more engaging and compelling with a stronger hook. Keep all the existing links and content structure, but rewrite the opening paragraph to be more attention-grabbing.

Previous blog post:
{blog_text1}

Please provide the revised version with an improved introduction."""
    
    response2 = await create_blog_post(
        revision_request,
        session_id="multi-turn-session",  # Same session ID = conversation continuity
        user_id="demo_user"
    )
    print("✅ Modification request processed in the same session")
    blog_text2 = extract_blog_text(response2)
    print("\nUpdated Blog Post:")
    print("-" * 80)
    print(blog_text2)
    
    print("\n\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(main())

