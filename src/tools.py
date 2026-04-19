"""
tools.py — LangChain tools available to the ReAct agent.

Tools:
    1. pak_econ_search   — broad semantic search over all chunks
    2. section_lookup    — retrieve a specific Wikipedia section by name
    3. table_search      — search only table rows/summaries
    4. calculate         — safe arithmetic evaluator
"""

from langchain_core.tools import tool

from src.retriever import format_results, retrieve

# ---------------------------------------------------------------------------
# Tool 1: General semantic search
# ---------------------------------------------------------------------------


@tool
def pak_econ_search(query: str) -> str:
    """
    Search the Pakistan Economy knowledge base for information relevant to a query.

    Use this tool to find facts, statistics, historical data, and descriptions
    about Pakistan's economy — including GDP, inflation, sectors, trade,
    remittances, debt, investment, and more.

    Args:
        query: A natural-language question or keyword phrase.

    Returns:
        The top 5 most relevant text passages with their sources.
    """
    results = retrieve(query, top_k=5)
    return format_results(results)


# ---------------------------------------------------------------------------
# Tool 2: Section-specific lookup
# ---------------------------------------------------------------------------

KNOWN_SECTIONS = [
    "Introduction", "Inception", "1950s", "1960s", "1970s", "1980s",
    "1990s", "2000s", "Gross domestic product (GDP)", "Stock market",
    "Informal economy", "Middle class", "Poverty alleviation expenditures",
    "Employment", "Government revenues and expenditures", "Rupee",
    "Foreign exchange rate", "Foreign exchange reserves", "Structure of economy",
    "Agriculture", "Industry", "Manufacturing", "Cement industry",
    "Fertilizer industry", "Defence industry", "Textiles industry",
    "Automobile industry", "Mining", "Energy", "Services",
    "Telecommunications", "Air linkage", "Railway linkage", "Road linkage",
    "Maritime linkage", "Finance", "Housing", "Tourism", "Investment",
    "Foreign trade", "Exports", "Imports", "External imbalances",
    "Economic aid", "Remittances", "Taxation Issues", "The Finance Act 2025",
    "Corruption", "Poverty and Income inequality", "Debt", "Ease of doing business",
]


@tool
def section_lookup(section_name: str) -> str:
    """
    Retrieve detailed information from a specific section of the Pakistan Economy article.

    Use this tool when the user's question is clearly about a named topic
    (e.g., "Agriculture", "Remittances", "Energy", "Debt").

    Available sections include (but are not limited to):
    Introduction, Agriculture, Industry, Manufacturing, Energy, Finance,
    Remittances, Debt, Exports, Imports, Corruption, Telecommunications,
    Tourism, Stock market, GDP, 1980s, 1990s, 2000s, etc.

    Args:
        section_name: The exact or approximate section name (case-insensitive match attempted).

    Returns:
        Top 4 passages from that section.
    """
    # Fuzzy match: find the closest known section
    section_lower = section_name.lower()
    matched = next(
        (s for s in KNOWN_SECTIONS if section_lower in s.lower() or s.lower() in section_lower),
        None,
    )

    if matched:
        results = retrieve(section_name, top_k=4, section=matched)
        if results:
            return format_results(results)
        # Fall back to unfiltered search within the matched section topic
    # Broader fallback
    results = retrieve(section_name, top_k=4)
    return format_results(results)


# ---------------------------------------------------------------------------
# Tool 3: Table / numeric data search
# ---------------------------------------------------------------------------


@tool
def table_search(query: str) -> str:
    """
    Search specifically within table data from the Pakistan Economy article.

    Use this tool when the user asks for specific numeric data, year-by-year
    statistics, GDP figures, inflation rates, unemployment numbers,
    trade values, or any tabular data (e.g., "GDP in 2005", "inflation 1990s").

    Args:
        query: A natural-language query about numeric or tabular data.

    Returns:
        Top 5 matched table rows or table summaries.
    """
    results = retrieve(query, top_k=5, chunk_type="table_row")
    if not results:
        # Fall back to table summaries if no row matches
        results = retrieve(query, top_k=5, chunk_type="table_summary")
    return format_results(results)


# ---------------------------------------------------------------------------
# Tool 4: Safe arithmetic calculator
# ---------------------------------------------------------------------------


@tool
def calculate(expression: str) -> str:
    """
    Evaluate a safe arithmetic expression and return the result.

    Use this tool when you need to perform calculations — for example,
    computing percentage changes, differences between GDP values,
    or unit conversions. Do NOT use Python code, just math expressions.

    Supported: +, -, *, /, **, (, ), integers, floats.

    Examples:
        "410.5 - 184.1"   → difference between two GDP values
        "(25.4 - 22.3) / 22.3 * 100"  → percentage change

    Args:
        expression: A valid arithmetic expression as a string.

    Returns:
        The numeric result as a string, or an error message.
    """
    import ast
    import operator

    SAFE_OPS = {
        ast.Add:  operator.add,
        ast.Sub:  operator.sub,
        ast.Mult: operator.mul,
        ast.Div:  operator.truediv,
        ast.Pow:  operator.pow,
        ast.USub: operator.neg,
    }

    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            op = SAFE_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op = SAFE_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(_eval(node.operand))
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    try:
        tree   = ast.parse(expression.strip(), mode="eval")
        result = _eval(tree.body)
        return str(round(result, 6))
    except Exception as e:
        return f"Calculation error: {e}"


# ---------------------------------------------------------------------------
# Export all tools as a list for easy import into the agent
# ---------------------------------------------------------------------------

ALL_TOOLS = [pak_econ_search, section_lookup, table_search, calculate]
