"""
app.py — CLI entry point for the Pakistan Economy Agentic RAG chatbot.

Usage:
    python app.py

Commands inside the chat:
    exit / quit / q  → exit the program
    clear            → clear conversation memory
    help             → show available example questions
"""

import sys

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Banners & helpers
# ---------------------------------------------------------------------------

BANNER = r"""
╔══════════════════════════════════════════════════════════╗
║          🇵🇰  PakEconBot — Agentic RAG System            ║
║  Powered by: Groq LLaMA 3 70B · Pinecone · MiniLM       ║
╠══════════════════════════════════════════════════════════╣
║  Type your question and press Enter.                     ║
║  Commands:  exit · clear · help                          ║
╚══════════════════════════════════════════════════════════╝
"""

EXAMPLE_QUESTIONS = """
📋  Example questions you can ask:
  • What is Pakistan's GDP as of 2026?
  • Which sectors drive Pakistan's exports?
  • How did GDP growth in the 1980s compare to the 1970s?
  • What is the size of Pakistan's informal economy?
  • What role do remittances play in the economy?
  • Compare Pakistan's inflation in the 1980s vs 1990s.
  • What industries are included in Pakistan's manufacturing sector?
  • What was Pakistan's trade deficit in FY 2018?
  • How has poverty changed from 2000 to 2025?
"""

SEPARATOR = "─" * 62


def _print_answer(answer: str) -> None:
    print(f"\n\033[92m{answer}\033[0m")   # Green text for answers
    print(SEPARATOR)


def _print_error(msg: str) -> None:
    print(f"\n\033[91m[Error] {msg}\033[0m")
    print(SEPARATOR)


# ---------------------------------------------------------------------------
# Main chat loop
# ---------------------------------------------------------------------------

def main() -> None:
    print(BANNER)

    # Lazy import so startup messages don't interleave
    try:
        from src.agent import create_agent, run_agent
    except KeyError as e:
        sys.exit(
            f"\n[app] Missing environment variable: {e}\n"
            "Please copy .env.example → .env and fill in your API keys."
        )

    print("[app] Initialising agent (loading models…)")
    agent = create_agent()
    print("[app] ✅ Agent ready!\n")
    print(SEPARATOR)

    while True:
        try:
            user_input = input("\n🧑 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n[app] Goodbye!")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        # Control commands
        if cmd in ("exit", "quit", "q"):
            print("\n[app] Goodbye!")
            break

        if cmd == "clear":
            agent.clear_memory()
            print("[app] ✅ Conversation memory cleared.")
            continue

        if cmd == "help":
            print(EXAMPLE_QUESTIONS)
            continue

        # Run the agent
        print(f"\n🤖 PakEconBot:\n{SEPARATOR}")
        try:
            answer = run_agent(agent, user_input)
            _print_answer(answer)
        except Exception as e:
            _print_error(str(e))


if __name__ == "__main__":
    main()
