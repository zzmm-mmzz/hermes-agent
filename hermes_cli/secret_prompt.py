"""
Secret prompt utilities — securely prompt for passwords/tokens/keys
with masked input (no echo).
"""

import sys
import getpass


def masked_secret_prompt(prompt: str = "Secret: ") -> str:
    """Prompt for a secret value with masked input (no terminal echo).

    Falls back to ``input()`` when running in non-interactive environments
    (e.g. CI, piped stdin, IDE terminals without getpass support).

    Args:
        prompt: The prompt text shown to the user.

    Returns:
        The entered value as a string.
    """
    # getpass may not work in every environment (IDE, CI, Docker with no TTY).
    # Fall back to regular input so the prompt doesn't silently hang.
    try:
        if not sys.stdin.isatty():
            return input(prompt)
        return getpass.getpass(prompt)
    except (OSError, EOFError, KeyboardInterrupt):
        # If anything goes wrong (e.g. no TTY after all), fall back
        return input(prompt)
