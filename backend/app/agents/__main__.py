"""Chat with the CFO agent from a terminal.

    cd backend
    python -m app.agents                      # interactive
    python -m app.agents "Why did profit drop in September?"
"""

import sys

from strands.handlers.callback_handler import PrintingCallbackHandler

from app.agents import finance_api
from app.agents.cfo_agent import build_agent


def main() -> None:
    stubbed = finance_api.using_stubs()
    if stubbed:
        print(f"[using stub data for: {', '.join(stubbed)}]\n")

    agent = build_agent(callback_handler=PrintingCallbackHandler())
    if len(sys.argv) > 1:
        agent(" ".join(sys.argv[1:]))
        print()
        return

    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if question:
            print("\nCFO: ", end="")
            agent(question)
            print()


if __name__ == "__main__":
    main()
