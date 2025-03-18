import json
import re
import sqlglot  # ✅ Pre-validation of SQL queries
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy import create_engine, text
from decimal import Decimal
from datetime import datetime
from fuzzywuzzy import fuzz
import logging
import threading
import os

# Configure logging
logging.basicConfig(filename="sql_agent.log", level=logging.INFO, 
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Define the database connection string
DATABASE_URL = "mssql+pyodbc://django_user:1234@host.docker.internal:1433/AdventureWorks?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"

# Create a SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Test the connection
try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT DB_NAME()"))
        db_name = result.scalar()
        logging.info(f"✅ Connected to Database: {db_name}")
except Exception as e:
    logging.error(f"❌ Database connection failed: {e}")
    exit()


schema_cache = None
schema_lock = threading.Lock()

# def get_schema():
#     """Loads schema once and stores it in memory."""
#     global schema_cache
#     if schema_cache is None:
#         with schema_lock:
#             if schema_cache is None:  
#                 with open("AdventureWorks_schema.json", "r") as f:
#                     schema_cache = json.load(f)
#     return schema_cache

def get_schema():
    """Loads schema once and stores it in memory."""
    global schema_cache
    if schema_cache is None:
        with schema_lock:
            if schema_cache is None:
                # Get the absolute path of the JSON file inside the agent folder
                schema_path = os.path.join(os.path.dirname(__file__), "AdventureWorks_schema.json")
                with open(schema_path, "r") as f:
                    schema_cache = json.load(f)
    return schema_cache

db_schema = get_schema()

tables_info = db_schema["tables"]
foreign_keys_info = db_schema["foreign_keys"]

SYNONYM_MAP = {
    "region": "territory",
    "regions": "territories",
    "area": "territory",
    "location": "territory",
    "revenue": "sales",
    "orders": "salesorder",
    "customer": "person",
}

def expand_query_with_synonyms(user_query):
    """Replaces synonyms in the user query with their mapped values."""
    for word, synonym in SYNONYM_MAP.items():
        user_query = re.sub(rf"\b{word}\b", synonym, user_query, flags=re.IGNORECASE)
    return user_query.lower()

def filter_relevant_schema(user_query):
    """Extracts only relevant tables/columns based on user query using fuzzy matching."""
    user_query = expand_query_with_synonyms(user_query)
    relevant_tables = {}

    logging.info(f"🔍 User Query After Synonym Expansion: {user_query}")

    for table in tables_info:
        table_name = table["TableName"]
        schema_name = table["SchemaName"]

        if schema_name == "Sales":
            columns = table["Columns"]

            # Compute fuzzy match scores
            table_match_score = fuzz.partial_ratio(table_name.lower(), user_query)
            column_match_scores = {
                col["ColumnName"]: fuzz.partial_ratio(col["ColumnName"].lower(), user_query)
                for col in columns
            }

            logging.info(f"\n📌 Checking Table: {table_name} (Score: {table_match_score})")
            for col_name, score in column_match_scores.items():
                logging.info(f"    🔹 Column: {col_name} (Score: {score})")

            # Select table if table name or any column name matches >= 40%
            if table_match_score >= 40 or any(score >= 40 for score in column_match_scores.values()):
                relevant_tables[table_name] = columns

    # Filter relevant foreign keys
    relevant_foreign_keys = [
        fk for fk in foreign_keys_info if fk["ParentTable"] in relevant_tables or fk["ReferencedTable"] in relevant_tables
    ]

    return json.dumps({"tables": relevant_tables, "foreign_keys": relevant_foreign_keys}, indent=2)

# Initialize Gemini LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-thinking-exp", 
    temperature=0.1, top_p=0.1, top_k=5, verbose=True, 
    api_key="AIzaSyCs5-5jWI1e7C2rR6qwMmRUz7HkHq4n9TE"
)

# Define the prompt template
sql_prompt = PromptTemplate(
    input_variables=["schema", "query"],
    template="""
    You are an AI SQL assistant for Microsoft SQL Server. Generate an optimized SQL query.
    
    ### Filtered Database Schema:
    {schema}

    ### User Request:
    {query}

    ### Rules:
    - Use only the provided tables and columns.
    - Format table and column names as [Schema].[Table] and [Column].
    - Format table and column names with square brackets [TableName], [ColumnName].
    - Ensure all calculated fields (aggregations, expressions, or derived columns) have explicit aliases using AS.
    - Return ONLY the SQL query as plain text (No explanations, No Markdown).
    - Use square brackets for reserved keywords, e.g., [Group], [Order], [User].
    - **Ensure 'GROUP BY' is not mistakenly formatted as '[GROUP] BY'.**
    """
)

sql_chain = sql_prompt | llm

def clean_sql_query(raw_query: str) -> str:
    """
    Cleans the generated SQL query by:
    - Removing markdown artifacts
    - Converting backticks to MSSQL-compatible square brackets
    """
    if raw_query is None:
        logging.warning("⚠️ Received None as SQL query, returning empty string.")
        return ""

    raw_query = re.sub(r"sql\n(.*?)\n", r"\1", raw_query, flags=re.DOTALL)
    raw_query = raw_query.replace("`", "").strip()

    return raw_query

def validate_sql(query: str) -> bool:
    """
    Uses sqlglot to validate SQL syntax and detect schema mismatches.
    """
    try:
        sqlglot.parse_one(query, dialect="tsql")  # Parse with SQL Server dialect
        return True  # SQL is valid
    except Exception as e:
        print(f"❌ SQL validation failed: {e}")
        return False
    
def execute_query(query: str):
    """Executes the given SQL query and returns results as JSON."""
    try:
        with engine.connect() as connection:
            result = connection.execute(text(query))
            rows = result.fetchall()
            column_names = result.keys()
            processed_rows = [
                {col: (float(value) if isinstance(value, Decimal) else value.isoformat() if isinstance(value, datetime) else value)
                for col, value in zip(column_names, row)}
                for row in rows
            ]
            return processed_rows, None
    except Exception as e:
        logging.error(f"❌ Query execution error: {e}")
        return None, str(e)

def run_sql_agent(user_query: str):
    """
    End-to-end execution flow: 
    1. Extracts relevant schema
    2. Generates SQL
    3. Validates & auto-corrects SQL
    4. Executes query (if valid)
    """
    logging.info(f"🚀 Generating SQL Query for: {user_query}")

    # Extract only relevant tables
    relevant_schema = filter_relevant_schema(user_query)

    # Generate SQL
    response = sql_chain.invoke({"schema": relevant_schema, "query": user_query})
    raw_query = response.content.strip()
    query = clean_sql_query(raw_query)

    logging.info(f"🔍 Generated SQL:\n{query}")

    # # Validate and auto-correct SQL before execution
    # is_valid, query = validate_sql(query)
    
    if not validate_sql(query):
        return "❌ Invalid SQL generated."

    # Execute the query
    results, error = execute_query(query)

    if error:
        return f"❌ Execution failed: {error}"
    
    return results  # Return final results

if __name__ == "__main__":
    user_prompt = input("Enter your query: ")
    output = run_sql_agent(user_prompt)
    logging.info("\n🎯 Final Output: %s", output)
