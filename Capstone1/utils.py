import logging
import sqlite3
import streamlit as st
from openai import OpenAI
import json

#using the secrets to safely use the api key
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=OPENAI_API_KEY)

DB_PATH = "data/sales_data.db"
TABLE = "sales_data"

def query_db(sql, params=None):
    """Run a SQL query and return the results."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        return cur.fetchall()

def get_customer_names(_, n=10):
    return [r[0] for r in query_db(f"SELECT DISTINCT Customer FROM {TABLE} LIMIT ?", (n,))]

def get_top_products(_, n=5):
    return [r[0] for r in query_db(
        f"SELECT Product FROM {TABLE} GROUP BY Product ORDER BY SUM(Total) DESC LIMIT ?", (n,)
    )]

def get_sales_by_region(_, region):
    rows = query_db(f"SELECT SUM(Total) FROM {TABLE} WHERE Region=?", (region,))
    return {region: rows[0][0] or 0 if rows else 0}

def get_average_price(_):
    rows = query_db(f"SELECT AVG(Price) FROM {TABLE}")
    return rows[0][0] if rows else 0

def create_support_ticket(_, issue=None):
    logging.info(f"Support ticket created: {issue}")
    return "Your support ticket has been created. Our team will contact you soon."

FUNCTIONS = {
    "get_customer_names": get_customer_names,
    "get_top_products": get_top_products,
    "get_sales_by_region": get_sales_by_region,
    "get_average_price": get_average_price,
    "create_support_ticket": create_support_ticket,
}

function_definitions = [
    
    {
        "name": "get_customer_names",
        "description": "Return a list of customer names.",
        "parameters": {
            "type": "object",
            "properties": {"n": {"type": "integer", "description": "Number of names to show"}},
            "required": ["n"],
        },
    },
    {
        "name": "get_top_products",
        "description": "Show top products by sales.",
        "parameters": {
            "type": "object",
            "properties": {"n": {"type": "integer", "description": "Number of top products"}},
            "required": ["n"],
        },
    },
    {
        "name": "get_sales_by_region",
        "description": "Get total sales for a region.",
        "parameters": {
            "type": "object",
            "properties": {"region": {"type": "string", "description": "Name of region"}},
            "required": ["region"],
        },
    },
    {
        "name": "get_average_price",
        "description": "Get average sale price.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "create_support_ticket",
        "description": "Create a support ticket for a user issue.",
        "parameters": {
            "type": "object",
            "properties": {"issue": {"type": "string", "description": "Issue description"}},
        },
    },
]

def pretty_format(tool, output):
    """Human-style formatting for function outputs."""
    if tool == "get_customer_names":
        return "Customer names: " + ", ".join(output)
    elif tool == "get_top_products":
        return "Top products: " + ", ".join(output)
    elif tool == "get_sales_by_region":
        region, total = next(iter(output.items()))
        return f"Total sales in {region}: {total:,.2f}"
    elif tool == "get_average_price":
        return f"Average sale price: {output:,.2f}"
    elif tool == "create_support_ticket":
        return str(output)
    elif isinstance(output, list):
        return ", ".join(str(x) for x in output)
    elif isinstance(output, dict):
        return ", ".join(f"{k}: {v}" for k, v in output.items())
    elif isinstance(output, (float, int)):
        return f"{output:,.2f}"
    return str(output)

def safe_agent(user_query):
    # Safety: block dangerous SQL-like operations
    blocked = ["delete", "drop", "update", "remove", "insert", "truncate", "alter"]
    if any(kw in user_query.lower() for kw in blocked):
        logging.warning(f"Blocked dangerous query: {user_query}")
        return "Sorry, I cannot perform dangerous operations for your safety."

    # System prompt to make it friendly/helpful!
    SYSTEM_PROMPT = (
        "You are a helpful business data assistant. "
        "Always answer with clear, friendly explanations, including available results or tools where needed."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query}
    ]

    # Call OpenAI, let it use tool/functions if appropriate, else chat
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        functions=function_definitions,
        function_call="auto",
        temperature=0,
        max_tokens=128,
    )
    choice = response.choices[0]

    # checking function handling
    fn_call = getattr(choice.message, "function_call", None)
    if fn_call and choice.finish_reason == "function_call":
        fn_name = fn_call.name
        fn_args = json.loads(fn_call.arguments)
        logging.info(f"Function call: {fn_name}({fn_args})")
        if fn_name in FUNCTIONS:
            output = FUNCTIONS[fn_name](None, **fn_args)
            return pretty_format(fn_name, output)
        return "Unknown tool requested."
    else:
        # friendly/helpful tone
        answer = choice.message.content.strip()
        return answer or "Sorry, I don't know the answer to that yet."
