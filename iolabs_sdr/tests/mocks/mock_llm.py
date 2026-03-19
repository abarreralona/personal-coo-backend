"""
IOlabs AI SDR Platform — Mock LLM Client (Step 9)

Returns deterministic fixture responses instead of calling the Anthropic API.
Eliminates API cost from test runs and makes tests fully deterministic.

Fixtures keyed by (prompt_type, input_hash) or by signal name.
"""


class MockLLMClient:
    """
    Drop-in replacement for the Anthropic client.
    Used in tests via dependency injection / monkeypatching.
    """

    # TODO: Step 9 — implement fixture registry
    # Maps prompt patterns to canned responses for:
    #   - visual_ai classification
    #   - llm_pickup signals
    #   - opening paragraph generation
    #   - reply classification
    #   - interested reply generation

    async def messages_create(self, **kwargs) -> object:
        """Returns a mock Anthropic Messages response object."""
        # TODO: Step 9 — implement with fixture lookup
        raise NotImplementedError("MockLLMClient: implemented in Step 9")
