import json
from pymongo import MongoClient
from bson import ObjectId

# Connect to MongoDB
client = MongoClient("mongodb+srv://django_user:2002@cluster0.cszgl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["sample_analytics"]

print("✅ Connected to MongoDB")

# Get all collection names
collections = db.list_collection_names()
print(f"📌 Found {len(collections)} collections: {collections}")

# Dictionary to store schema information
schema_info = {}

# Function to analyze documents
def analyze_document(doc):
    """Analyze a document to extract field types, including arrays and nested objects."""
    field_types = {}

    for key, value in doc.items():
        if isinstance(value, ObjectId):
            field_types[key] = "ObjectId"
        elif isinstance(value, str) and len(value) == 24:  # Possible ObjectId in string format
            field_types[key] = "ObjectId (string)"
        elif isinstance(value, int):
            field_types[key] = "int"
        elif isinstance(value, float):
            field_types[key] = "float"
        elif isinstance(value, bool):
            field_types[key] = "bool"
        elif isinstance(value, list):
            if len(value) > 0:
                first_item = value[0]
                if isinstance(first_item, dict):
                    field_types[key] = {"type": "array", "items": analyze_document(first_item)}
                else:
                    field_types[key] = {"type": "array", "items": type(first_item).__name__}
            else:
                field_types[key] = {"type": "array", "items": "unknown"}
        elif isinstance(value, dict):
            field_types[key] = {"type": "object", "fields": analyze_document(value)}
        else:
            field_types[key] = type(value).__name__

    return field_types

# Function to process a sample document (limit arrays to one item)
def process_sample_document(doc):
    """Modifies the sample document to include only the first item in arrays."""
    modified_doc = {}

    for key, value in doc.items():
        if isinstance(value, list) and len(value) > 0:
            modified_doc[key] = [value[0]]  # Keep only the first item
        else:
            modified_doc[key] = value  # Keep everything else unchanged

    return modified_doc

# Function to get schema for a collection
def get_collection_schema(collection_name):
    """Fetches sample documents and extracts schema."""
    print(f"🔍 Analyzing collection: {collection_name}...")

    collection = db[collection_name]
    sample_doc = collection.find_one()

    if not sample_doc:
        print(f"⚠️ No documents found in {collection_name}. Skipping...")
        return None

    # Analyze the first document to determine field types
    schema = analyze_document(sample_doc)
    print(f"✅ Extracted schema for {collection_name}")

    return {
        "fields": schema,
        "sample_document": process_sample_document(sample_doc)  # Modify the sample doc
    }

# Process all collections
for col in collections:
    schema = get_collection_schema(col)
    if schema:
        schema_info[col] = schema

# Commenting out relationship detection for now
# relationships = []

# print("🔎 Detecting relationships between collections...")
# for col, schema in schema_info.items():
#     for field, field_type in schema["fields"].items():
#         # Check if the field is an ObjectId or string ObjectId
#         if isinstance(field_type, str) and "ObjectId" in field_type:
#             value_str = schema["sample_document"].get(field, "")

#             for target_col, id_set in id_map.items():
#                 if value_str in id_set and target_col != col:
#                     print(f"✅ Found: {field} in {col} references {target_col}")
#                     relationships.append({
#                         "from_collection": col,
#                         "from_field": field,
#                         "to_collection": target_col,
#                         "relationship_type": "Manual Foreign Key"
#                     })

# Save schema (without relationships) to JSON
output_data = {
    "collections": schema_info,
    # "relationships": relationships  # Commented out
}

with open("mongo_schema.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, default=str, indent=4)

print("📂 Schema saved to mongo_schema.json 🎉")
