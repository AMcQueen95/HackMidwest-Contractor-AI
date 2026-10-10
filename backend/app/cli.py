"""Talk to the CFO from the terminal.

    python -m backend.app.cli "Why did profit drop this month?"
    python -m backend.app.cli --demo          # all five demo questions
    python -m backend.app.cli --report 2026-09
    python -m backend.app.cli                 # interactive chat
"""

import argparse
import logging

DEMO_QUESTIONS = [
    "Why did profit drop this month?",
    "Which jobs are losing money?",
    "Can I afford a $15,000 equipment purchase?",
    "Which customers still owe me money?",
    "What expenses increased the most?",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the Toolbelt CFO a question.")
    parser.add_argument("question", nargs="?", help="Question to ask. Omit for interactive chat.")
    parser.add_argument("--demo", action="store_true", help="Run the five demo questions.")
    parser.add_argument("--report", metavar="YYYY-MM", nargs="?", const="", help="Print the monthly report as JSON.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Hide which specialists the CFO consults.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO,
                        format="  · %(message)s")
    for noisy in ("botocore", "httpx", "strands", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    from backend.app.agents import build_cfo_agent, financial_health_report

    if args.report is not None:
        print(financial_health_report(args.report or None).model_dump_json(indent=2))
        return

    agent = build_cfo_agent(stream=True)
    questions = DEMO_QUESTIONS if args.demo else [args.question] if args.question else None

    if questions:
        for q in questions:
            print(f"\n> {q}\n")
            agent(q)
            print()
        return

    print("Toolbelt CFO. Ask about your books. Ctrl+C to quit.")
    while True:
        try:
            q = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if q:
            print()
            agent(q)
            print()


if __name__ == "__main__":
    from anthropic import APIStatusError
    from botocore.exceptions import NoCredentialsError

    try:
        main()
    except RuntimeError as e:
        raise SystemExit(f"\n{e}")
    except APIStatusError as e:
        message = e.body.get("error", {}).get("message") if isinstance(e.body, dict) else None
        raise SystemExit(f"\nAnthropic API error {e.status_code}: {message or e}")
    except NoCredentialsError:
        raise SystemExit(
            "\nMODEL_PROVIDER=bedrock but no AWS credentials were found. Add AWS credentials, "
            "or switch back to MODEL_PROVIDER=anthropic in backend/.env."
        )
