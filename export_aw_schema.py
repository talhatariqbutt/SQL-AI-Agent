import pyodbc
import json
from collections import defaultdict

# SQL Server connection details
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=TTB-DELL;"
    "DATABASE=AdventureWorks;"
    "UID=django_user;"
    "PWD=1234;"
)

def fetch_json_query(query):
    """Execute a query and return JSON result."""
    cursor = conn.cursor()
    cursor.execute(query)
    result = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    cursor.close()  # Close cursor after execution
    return result

# Queries
columns_query = """
SELECT 
    t.TABLE_SCHEMA AS SchemaName, 
    t.TABLE_NAME AS TableName, 
    c.COLUMN_NAME AS ColumnName, 
    c.DATA_TYPE AS DataType, 
    c.CHARACTER_MAXIMUM_LENGTH AS MaxLength
FROM INFORMATION_SCHEMA.TABLES t
JOIN INFORMATION_SCHEMA.COLUMNS c 
    ON t.TABLE_NAME = c.TABLE_NAME AND t.TABLE_SCHEMA = c.TABLE_SCHEMA
WHERE t.TABLE_TYPE = 'BASE TABLE'
ORDER BY SchemaName, TableName, c.ORDINAL_POSITION;
"""

foreign_keys_query = """
SELECT 
    fk.name AS ForeignKeyName,
    ps.name AS ParentSchema,
    tp.name AS ParentTable,
    cp.name AS ParentColumn,
    rs.name AS ReferencedSchema,
    tr.name AS ReferencedTable,
    cr.name AS ReferencedColumn
FROM sys.foreign_keys fk
JOIN sys.tables tp ON fk.parent_object_id = tp.object_id
JOIN sys.schemas ps ON tp.schema_id = ps.schema_id
JOIN sys.tables tr ON fk.referenced_object_id = tr.object_id
JOIN sys.schemas rs ON tr.schema_id = rs.schema_id
JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
JOIN sys.columns cp ON fkc.parent_column_id = cp.column_id AND tp.object_id = cp.object_id
JOIN sys.columns cr ON fkc.referenced_column_id = cr.column_id AND tr.object_id = cr.object_id
ORDER BY ParentSchema, ParentTable, ReferencedTable;
"""

# Fetch data
columns_data = fetch_json_query(columns_query)
foreign_keys_data = fetch_json_query(foreign_keys_query)

# Process table structure
tables_dict = defaultdict(lambda: {"SchemaName": "", "TableName": "", "Columns": []})

for row in columns_data:
    schema_name = row["SchemaName"]
    table_name = row["TableName"]
    table_key = f"{schema_name}.{table_name}"

    if not tables_dict[table_key]["SchemaName"]:
        tables_dict[table_key]["SchemaName"] = schema_name
        tables_dict[table_key]["TableName"] = table_name

    tables_dict[table_key]["Columns"].append({
        "ColumnName": row["ColumnName"],
        "DataType": row["DataType"],
        "MaxLength": row["MaxLength"]
    })

# Convert defaultdict to list
tables_list = list(tables_dict.values())

# Combine into JSON
db_schema = {
    "tables": tables_list,
    "foreign_keys": foreign_keys_data
}

# Save to file
with open("AdventureWorks_schema.json", "w") as f:
    json.dump(db_schema, f, indent=4)

# Close connection
conn.close()

print("✅ Database schema exported successfully to AdventureWorks_schema.json")
