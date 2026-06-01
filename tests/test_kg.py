import asyncio

from dotenv import load_dotenv

load_dotenv()

import pytest

from open_notebook.database.repository import db_connection
from open_notebook.domain.notebook import Source
from open_notebook.graphs.knowledge_graph import graph as kg_graph
from open_notebook.utils.logger_config import setup_logging

setup_logging()

@pytest.mark.asyncio
async def test_kg_extraction():
    print("Testing KG extraction...")
    
    from open_notebook.database.repository import repo_query
    sources = await repo_query("SELECT * FROM source LIMIT 1")
    if not sources:
        print("No sources found in the database. Please upload a source first.")
        return
        
    source_data = sources[0]
    source = Source(**source_data)
    print(f"Testing with source: {source.title}")
    
    # Test extraction
    try:
        result = await kg_graph.ainvoke({"source": source})
        print("\n=== EXTRACTED ENTITIES ===")
        for e in result.get("extracted_entities", []):
            print(f"[{e.type}] {e.name}: {e.description}")
            
        print("\n=== EXTRACTED RELATIONS ===")
        for r in result.get("extracted_relations", []):
            print(f"{r.source} -[{r.type}]-> {r.target} (Desc: {r.description})")
            
    except Exception as e:
        print(f"Error during extraction: {e}")

if __name__ == "__main__":
    asyncio.run(test_kg_extraction())
