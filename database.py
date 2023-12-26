import os
import json
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound, IntegrityError

from fastapi import FastAPI, HTTPException, Depends, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect

from models import User, Task, init_db
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./cache.sqlite"


async def get_db_session():
    engine = create_async_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    await init_db(engine)

    sessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
    async with sessionLocal() as session:
        try:
            yield session
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            raise HTTPException(status_code=400, detail=str(e))