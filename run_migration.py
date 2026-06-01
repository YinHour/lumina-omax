import asyncio

from dotenv import load_dotenv

load_dotenv()
from open_notebook.database.repository import repo_query


async def main():
    print("Running migration...")
    await repo_query("DEFINE FIELD IF NOT EXISTS is_aggregated ON TABLE notebook TYPE option<bool> DEFAULT False;")
    print("Migration done!")

if __name__ == "__main__":
    asyncio.run(main())