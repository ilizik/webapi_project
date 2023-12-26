import uvicorn
import os
import json
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from fastapi import FastAPI, HTTPException, Depends, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect

from models import User, Task
from database import get_db_session

app = FastAPI()
ITEMS = {}
connected_clients = set()


@app.get("/", response_class=HTMLResponse)
async def read_root():
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, 'static', 'app', 'index.html')
    with open(file_path, 'r') as file:
        html_content = file.read()
    return HTMLResponse(content=html_content)


# Методы с задачами
@app.get("/tasks", tags=["Tasks"])
async def read_root(session=Depends(get_db_session)):
    """
    Получение всех задач
    """
    stmt = select(Task)
    tasks = await session.scalars(stmt)
    data = tasks.all()
    return data


@app.get("/tasks/{task_id}", tags=["Tasks"])
async def read_task(task_id: int, session=Depends(get_db_session)):
    """
    Получение одной задачи
    """
    try:
        stmt = select(Task).where(Task.id == task_id)
        task = await session.scalars(stmt)
        return task.one()
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tasks", tags=["Tasks"])
async def create_item(data: dict, session=Depends(get_db_session)):
    """
    Создание задачи
    """
    task = Task(
        title=data["title"],
        description=data["description"],
        user_id=data["user_id"]
    )
    session.add(task)
    await session.flush()

    task_info = task.__repr__()
    for client in connected_clients:
        await client.send_text(json.dumps({"type": "new_task", "message": f"New task added: {task_info}"}))

    return task_info


@app.put("/tasks/{task_id}", tags=["Tasks"])
async def update_task(task_id: int, data: dict, session=Depends(get_db_session)):
    """
    Обновление задачи
    """
    stmt = select(Task).where(Task.id == task_id)
    task = await session.scalars(stmt)
    task = task.one()
    task.title = data["title"]
    task.description = data["description"]
    task.user_id = data["user_id"]
    response_data = task.__dict__
    return response_data


@app.patch("/tasks/{task_id}/assign_user/{user_id}", tags=["Tasks"])
async def assign_user_to_task(task_id: int, user_id: int, session=Depends(get_db_session)):
    """
    Назначение задачи пользователю
    """
    try:
        task = await session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        task.user_id = user_id
        await session.commit()
        return task
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/tasks/{task_id}", tags=["Tasks"])
async def delete_task(task_id: int, session=Depends(get_db_session)):
    """
    Удаление задачи
    """
    try:
        stmt = select(Task).where(Task.id == task_id)
        task_to_delete = await session.scalars(stmt)
        task_to_delete = task_to_delete.one()
        data = task_to_delete.__dict__
        await session.delete(task_to_delete)
        await session.commit()
        return data
    except NoResultFound as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e))


@app.patch("/tasks/{task_id}/status", tags=["Tasks"])
async def update_task_status(task_id: int, new_status: str, session=Depends(get_db_session)):
    """
    Изменение статуса задачи
    """
    valid_statuses = ["to_do", "done"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")

    try:
        stmt = select(Task).where(Task.id == task_id)
        item = await session.scalars(stmt)
        task = item.one()
        task.status = new_status
        await session.commit()

        message = f"Task {task_id} status updated to {new_status}"
        for client in connected_clients:
            await client.send_text(json.dumps({"type": "status_update", "message": f"{message}"}))
        return {"message": "Task status updated"}
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Task not found")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# Методы с пользователями
@app.get("/users/{user_id}/tasks", tags=["Users"])
async def read_user_tasks(user_id: int, session=Depends(get_db_session)):
    """
    Получение всех задач у пользователя
    """
    try:
        stmt = select(Task).where(Task.user_id == user_id)
        tasks = await session.scalars(stmt)
        return tasks.all()
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/users", tags=["Users"])
async def read_root(session=Depends(get_db_session)):
    """
    Получение всех пользователей
    """
    stmt = select(User)
    items = await session.scalars(stmt)
    data = items.all()
    return data


@app.get("/users/{user_id}", tags=["Users"])
async def read_user(user_id: int, session=Depends(get_db_session)):
    """
    Получение одного пользователя
    """
    try:
        stmt = select(User).where(User.id == user_id)
        user = await session.scalars(stmt)
        return user.one()
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/users", tags=["Users"])
async def create_user(data: dict, session=Depends(get_db_session)):
    """
    Создание пользователя
    """
    user = User(
        name=data["name"],
        email=data["email"]
    )
    session.add(user)
    await session.flush()

    user_info = user.__repr__()
    for client in connected_clients:
        await client.send_text(json.dumps({"type": "new_user", "message": f"New user added: {user_info}"}))

    return user_info


@app.put("/users/{user_id}", tags=["Users"])
async def update_user(user_id: int, data: dict, session=Depends(get_db_session)):
    """
    Обновление пользователя
    """
    stmt = select(User).where(User.id == user_id)
    user = await session.scalars(stmt)
    user = user.one()
    user.name = data["name"]
    user.email = data["email"]
    response_data = user.__dict__
    return response_data


@app.delete("/users/{user_id}", tags=["Users"])
async def delete_user(user_id: int, session=Depends(get_db_session)):
    """
    Удаление пользователя
    """
    try:
        stmt = select(User).where(User.id == user_id)
        user_to_delete = await session.scalars(stmt)
        user_to_delete = user_to_delete.one()
        data = user_to_delete.__dict__
        await session.delete(user_to_delete)
        await session.commit()
        return data
    except NoResultFound as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
    except WebSocketDisconnect:
        connected_clients.remove(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
