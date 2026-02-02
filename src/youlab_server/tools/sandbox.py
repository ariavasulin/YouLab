"""
Self-contained Letta tools for Docker sandbox execution.

IMPORTANT: These tools must:
1. Use only Python stdlib (no external dependencies)
2. Make HTTP calls to YouLab server at YOULAB_SERVER_URL
3. Not import any youlab_server modules
4. Be completely self-contained

The server URL is configurable via the YOULAB_SERVER_URL constant.
For Docker sandbox: http://host.docker.internal:8100
"""

from typing import Any

# =============================================================================
# SANDBOX-COMPATIBLE TOOLS - No external imports allowed!
# =============================================================================

# Server URL - Docker's special DNS for host machine
YOULAB_SERVER_URL = "http://host.docker.internal:8100"

# Short ID length for display
SHORT_ID_LENGTH = 8


def query_honcho(  # noqa: PLR0911
    question: str,
    session_scope: str = "all",
    agent_state: dict[str, Any] | None = None,
) -> str:
    """
    Query conversation history to gain insights about the student.

    Use this tool to understand:
    - What the student has discussed previously
    - Their learning patterns and preferences
    - Progress they've made in past conversations
    - Any concerns or challenges they've mentioned

    Args:
        question: Natural language question about the student (e.g., "What progress has this student made?")
        session_scope: Which conversations to query - "all" (default), "recent", or "current"
        agent_state: Injected by Letta - contains agent_id for context lookup

    Returns:
        Insight about the student based on conversation history, or an error message.

    Example:
        query_honcho("What are this student's main interests?")
        query_honcho("Has the student struggled with any topics?", session_scope="recent")

    """
    import json
    import urllib.error
    import urllib.request

    # Extract user_id from agent metadata
    if agent_state is None:
        return "Error: No agent state available"

    # User ID should be in agent metadata
    user_id = agent_state.get("user_id")
    if not user_id:
        # Try to get from agent metadata
        metadata = agent_state.get("metadata", {})
        user_id = metadata.get("youlab_user_id")

    if not user_id:
        return "Error: Could not determine user_id from agent state"

    # Build request
    url = f"{YOULAB_SERVER_URL}/honcho/query"
    payload = json.dumps(
        {
            "user_id": user_id,
            "question": question,
            "session_scope": session_scope,
        }
    ).encode("utf-8")

    headers = {"Content-Type": "application/json"}

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")  # noqa: S310
        with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
            result = json.loads(response.read().decode("utf-8"))

            if not result.get("success"):
                error = result.get("error", "Unknown error")
                return f"Query failed: {error}"

            insight = result.get("insight")
            if insight:
                return insight
            return "No insight available from conversation history."

    except urllib.error.HTTPError as e:
        return f"Server error: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return f"Error connecting to server: {e.reason}"
    except json.JSONDecodeError:
        return "Error: Invalid response from server"
    except Exception as e:
        return f"Error: {e!s}"


def edit_memory_block(  # noqa: PLR0911
    block: str,
    field: str,
    content: str,
    strategy: str = "append",
    reasoning: str = "",
    agent_state: dict[str, Any] | None = None,
) -> str:
    """
    Propose an update to a memory block field.

    The change will be queued for user approval before being applied.
    Use this to record important observations about the student.

    Args:
        block: Name of the memory block to update (e.g., "progress", "operating_manual")
        field: Specific field within the block (e.g., "notes", "effective_strategies")
        content: The content to add or replace
        strategy: How to apply the change:
            - "append": Add to existing content (default, best for notes)
            - "replace": Replace specific content
            - "full_replace": Replace the entire field
        reasoning: Brief explanation of why you're making this change
        agent_state: Injected by Letta - contains agent_id and user context

    Returns:
        Confirmation message with diff ID, or an error message.

    Example:
        edit_memory_block(
            block="progress",
            field="notes",
            content="Student showed strong interest in essay structure today.",
            reasoning="Recording observation from today's session"
        )

    """
    import json
    import urllib.error
    import urllib.request

    # Extract identifiers from agent state
    if agent_state is None:
        return "Error: No agent state available"

    agent_id = agent_state.get("agent_id")
    if not agent_id:
        return "Error: No agent_id in agent state"

    # Get user_id from metadata
    user_id = agent_state.get("user_id")
    if not user_id:
        metadata = agent_state.get("metadata", {})
        user_id = metadata.get("youlab_user_id")

    if not user_id:
        return "Error: Could not determine user_id from agent state"

    # Build request
    url = f"{YOULAB_SERVER_URL}/users/{user_id}/blocks/{block}/propose"
    payload = json.dumps(
        {
            "agent_id": agent_id,
            "field": field,
            "content": content,
            "strategy": strategy,
            "reasoning": reasoning,
        }
    ).encode("utf-8")

    headers = {"Content-Type": "application/json"}

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")  # noqa: S310
        with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
            result = json.loads(response.read().decode("utf-8"))

            if not result.get("success"):
                error = result.get("error", "Unknown error")
                return f"Failed to propose edit: {error}"

            diff_id = result.get("diff_id", "unknown")
            # Truncate diff_id for readability
            short_id = diff_id[:SHORT_ID_LENGTH] if len(diff_id) > SHORT_ID_LENGTH else diff_id
            return f"Proposed change to {block}.{field} (ID: {short_id}). User will review."

    except urllib.error.HTTPError as e:
        return f"Server error: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return f"Error connecting to server: {e.reason}"
    except json.JSONDecodeError:
        return "Error: Invalid response from server"
    except Exception as e:
        return f"Error: {e!s}"
