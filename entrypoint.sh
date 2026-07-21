#!/bin/sh
set -e

until python -c "
import asyncio, asyncpg, os
async def check():
    await asyncpg.connect(os.environ['DATABASE_URL'].replace('postgresql+asyncpg', 'postgresql'))
asyncio.run(check())
" 2>/dev/null; do
  sleep 2
done

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
