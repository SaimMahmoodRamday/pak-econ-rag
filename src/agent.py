"""
agent.py — Custom ReAct agent powered by Groq (LLaMA 3 70B).

Implements the ReAct (Reason + Act) loop manually using ChatGroq,
so it has zero dependency on LangChain's frequently-changing agent internals.

Usage:
    from src.agent import create_agent, run_agent

    agent = create_agent()
    response = run_agent(agent, "What is Pakistan's current account balance?")
"""

import os
import re
from collections import deque

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from src.prompts import SYSTEM_PROMPT
from src.tools import ALL_TOOLS

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
LLM_MODEL    = "llama-3.3-70b-versatile"
TEMPERATURE  = 0.0      # Deterministic for factual RAG
MAX_TOKENS   = 2048
MAX_ITERS    = 8        # Max ReAct steps before giving up
MEMORY_K     = 5        # Number of past (user, assistant) turns to keep

# ---------------------------------------------------------------------------
# Build a tool lookup map  {tool_name: callable}
# ---------------------------------------------------------------------------

TOOL_MAP: dict = {t.name: t for t in ALL_TOOLS}

TOOLS_DESCRIPTION = "\n".join(
    f"- {t.name}: {t.description.strip().splitlines()[0]}"
    for t in ALL_TOOLS
)
TOOL_NAMES = ", ".join(TOOL_MAP.keys())

# ---------------------------------------------------------------------------
# ReAct system prompt (injected once at conversation start)
# ---------------------------------------------------------------------------

REACT_SYSTEM = f"""{SYSTEM_PROMPT}

## Available Tools
{TOOLS_DESCRIPTION}

Tool names: {TOOL_NAMES}

## Strict Output Format
You MUST use this exact format for every response until you have a final answer:

Thought: <think about what to do>
Action: <one of: {TOOL_NAMES}>
Action Input: <plain string input for the tool>

When you have enough information to answer:
Thought: I now know the final answer
Final Answer: <your complete, well-cited answer>

IMPORTANT:
- Output ONLY one Action per response.
- Never skip the Thought line.
- Action Input must be a plain string (no brackets, no JSON).
- Stop immediately after "Final Answer:" — do not continue.
"""

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_ACTION_RE       = re.compile(r"Action\s*:\s*(.+)", re.IGNORECASE)
_ACTION_INPUT_RE = re.compile(r"Action Input\s*:\s*(.+)", re.IGNORECASE)
_FINAL_RE        = re.compile(r"Final Answer\s*:\s*([\s\S]+)", re.IGNORECASE)


def _parse_react_response(text: str) -> dict:
    """
    Parse one LLM response into its ReAct components.

    Returns a dict with keys:
        "final_answer" (str | None)
        "action"       (str | None)
        "action_input" (str | None)
        "raw"          (str) — full LLM text
    """
    result = {"final_answer": None, "action": None, "action_input": None, "raw": text}

    final_m = _FINAL_RE.search(text)
    if final_m:
        result["final_answer"] = final_m.group(1).strip()
        return result

    action_m       = _ACTION_RE.search(text)
    action_input_m = _ACTION_INPUT_RE.search(text)

    if action_m:
        result["action"] = action_m.group(1).strip()
    if action_input_m:
        result["action_input"] = action_input_m.group(1).strip()

    return result


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

class ReActAgent:
    """
    A simple stateful ReAct agent backed by Groq LLaMA 3 70B.

    Maintains a sliding-window conversation memory of the last MEMORY_K turns.
    """

    def __init__(self, llm: ChatGroq):
        self.llm    = llm
        # Deque of (HumanMessage, AIMessage) pairs for memory
        self._memory: deque = deque(maxlen=MEMORY_K)

    def _build_messages(self, user_question: str, scratchpad: str) -> list:
        """Assemble the full message list for one LLM call."""
        messages = [SystemMessage(content=REACT_SYSTEM)]

        # Inject past conversation turns (for context)
        for human_msg, ai_msg in self._memory:
            messages.append(human_msg)
            messages.append(ai_msg)

        # Current turn — include accumulated scratchpad
        current_content = (
            f"Question: {user_question}\n{scratchpad}"
            if scratchpad
            else f"Question: {user_question}"
        )
        messages.append(HumanMessage(content=current_content))
        return messages

    def run(self, question: str, verbose: bool = True) -> str:
        """
        Execute the ReAct loop for a single question.

        Args:
            question: User's natural-language question.
            verbose:  If True, prints each Thought/Action/Observation step.

        Returns:
            The agent's final answer string.
        """
        scratchpad = ""
        final_answer = None

        for step in range(1, MAX_ITERS + 1):
            # ── LLM call ──────────────────────────────────────────────────
            messages = self._build_messages(question, scratchpad)
            response  = self.llm.invoke(messages)
            llm_text  = response.content.strip()

            parsed = _parse_react_response(llm_text)

            if verbose:
                print(f"\n\033[90m[Step {step}]\033[0m")
                print(f"\033[90m{llm_text}\033[0m")

            # ── Final answer reached ───────────────────────────────────────
            if parsed["final_answer"]:
                final_answer = parsed["final_answer"]
                # Save this full exchange to memory
                self._memory.append((
                    HumanMessage(content=question),
                    AIMessage(content=f"Final Answer: {final_answer}"),
                ))
                break

            # ── Tool call ──────────────────────────────────────────────────
            action       = parsed["action"]
            action_input = parsed["action_input"]

            if not action or not action_input:
                # LLM deviated from format — nudge it
                scratchpad += (
                    f"\n{llm_text}\nObservation: Please follow the format exactly. "
                    "Use Action: and Action Input: on separate lines.\n"
                )
                continue

            # Look up and execute the tool
            tool_fn = TOOL_MAP.get(action)
            if tool_fn is None:
                observation = (
                    f"Unknown tool '{action}'. "
                    f"Available tools: {TOOL_NAMES}"
                )
            else:
                try:
                    observation = tool_fn.invoke(action_input)
                except Exception as e:
                    observation = f"Tool error: {e}"

            if verbose:
                print(f"\n\033[94m[Observation]\033[0m\n\033[94m{observation[:600]}\033[0m")

            # Append this step to the scratchpad for the next LLM call
            scratchpad += (
                f"\n{llm_text}\n"
                f"Observation: {observation}\n"
                "Thought:"
            )

        if final_answer is None:
            final_answer = (
                "I was unable to produce a complete answer within the step limit. "
                "Please try rephrasing your question."
            )

        return final_answer

    def clear_memory(self) -> None:
        """Wipe the conversation history."""
        self._memory.clear()


# ---------------------------------------------------------------------------
# Public factory + helper (match the interface app.py expects)
# ---------------------------------------------------------------------------

def create_agent() -> ReActAgent:
    """
    Create and return a ReActAgent instance.

    Returns:
        A configured ReActAgent ready to accept .run(question) calls.
    """
    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=LLM_MODEL,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    return ReActAgent(llm=llm)


def run_agent(agent: ReActAgent, question: str) -> str:
    """
    Run the agent on a single question and return the final answer.

    Args:
        agent:    A ReActAgent created by create_agent().
        question: The user's natural-language question.

    Returns:
        The agent's final answer as a string.
    """
    return agent.run(question, verbose=True)


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    agent = create_agent()
    test_questions = [
        "What is Pakistan's nominal GDP as of 2026?",
        "Which sectors drive Pakistan's exports?",
        "What was GDP growth in the 1980s?",
    ]
    for q in test_questions:
        print(f"\n{'═' * 60}")
        print(f"Q: {q}")
        print(f"{'─' * 60}")
        answer = run_agent(agent, q)
        print(f"\n\033[92mA: {answer}\033[0m")
