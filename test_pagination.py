import asyncio
from open_notebook.database.repository import repo_query

async def main():
    # Insert multiple sources with the same updated time
    # (Assuming we have a lot of sources already to test)
    res1 = await repo_query("SELECT id, updated FROM source ORDER BY updated DESC LIMIT 5 START 0")
    res2 = await repo_query("SELECT id, updated FROM source ORDER BY updated DESC LIMIT 5 START 5")
    print("Page 1:", [r['id'] for r in res1])
    print("Page 2:", [r['id'] for r in res2])
    
    # Check if there's overlap or missing items if we run it multiple times?
    # Or just check if ordering by updated without id causes issues.
    
    res1_stable = await repo_query("SELECT id, updated FROM source ORDER BY updated DESC, id DESC LIMIT 5 START 0")
    res2_stable = await repo_query("SELECT id, updated FROM source ORDER BY updated DESC, id DESC LIMIT 5 START 5")
    print("Stable Page 1:", [r['id'] for r in res1_stable])
    print("Stable Page 2:", [r['id'] for r in res2_stable])

asyncio.run(main())
