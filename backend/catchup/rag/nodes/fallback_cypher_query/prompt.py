from langchain_core.prompts import PromptTemplate


CYPHER_GENERATION_TEMPLATE = """
Task: Generate Cypher statement to query a graph database.

Instructions:
1. **Schema Compliance:** Use ONLY the provided relationship types and properties in the schema. Do not use any other relationship types or properties that are not provided.
2. **Output Format:** Do not include any explanations or apologies in your responses. Do not include any text except the generated Cypher statement.
3. **Security:** Do not use DELETE, DROP, MERGE, CREATE, SET, REMOVE. Only use MATCH, RETURN, WHERE, WITH, UNWIND, ORDER BY, LIMIT.

4. **Structural Return (CRITICAL):** When the question implies retrieving specific nodes or relationships (not just counting), 
   please ALIAS the return values as `source`, `rel`, and `target` to support system parsing.
   
   - `source`: The starting node (or its name/id)
   - `rel`: The relationship type (using `type(r)` function)
   - `target`: The ending node (or its name/id)

   Example:
   MATCH (p:Person)-[r:ASSIGNED_TO]->(i:Issue)
   RETURN p.name AS source, type(r) AS rel, i.summary AS target

Schema:
{schema}

The question is:
{question}
"""

CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question"], template=CYPHER_GENERATION_TEMPLATE
)
