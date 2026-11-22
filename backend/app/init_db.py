"""Create tables once before starting multiple workers: python -m app.init_db"""

import asyncio

from .config import get_settings
from .db import Database


async def main() -> None:
    db = Database(get_settings().database_url)
    for attempt in range(30):  # wait for the database to come up
        try:
            await db.create_all()
            break
        except OSError:
            await asyncio.sleep(1)
    else:
        raise SystemExit("database not reachable")
    await db.dispose()
    print("tables ready")


if __name__ == "__main__":
    asyncio.run(main())
