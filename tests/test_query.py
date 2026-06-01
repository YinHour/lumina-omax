import os
import sys

sys.path.append(os.path.dirname(__file__))
import asyncio

from dotenv import load_dotenv

load_dotenv()
from open_notebook.database.repository import repo_query


async def main():
    res = await repo_query("""
        SELECT 
            id, 
            title,
            (SELECT VALUE id FROM kg_entity WHERE source_id = type::string($parent.id) LIMIT 1) != [] AS kg_extracted,
            (SELECT VALUE id FROM kg_entity WHERE source_id = $parent.id LIMIT 1) != [] AS kg_extracted_raw
        FROM source
        LIMIT 5;
    """)
    print(res)

if __name__ == "__main__":
    asyncio.run(main())