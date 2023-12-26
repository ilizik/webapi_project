from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, ForeignKey, Enum
from sqlalchemy.exc import IntegrityError, NoResultFound

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base, relationship


async def init_db(engine: AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, index=True)

    tasks = relationship("Task", back_populates="owner")

    def __repr__(self):
        data = self.__dict__
        del data["_sa_instance_state"]
        return str(data)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    status = Column(String, default="to_do", index=True)

    owner = relationship("User", back_populates="tasks")

    def __repr__(self):
        data = self.__dict__
        del data["_sa_instance_state"]
        return str(data)

