from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="Todo API", version="1.0.0")


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    completed: bool = False


class Todo(TodoCreate):
    id: int


todos: List[Todo] = []
_next_id = 1


def get_next_id() -> int:
    global _next_id
    todo_id = _next_id
    _next_id += 1
    return todo_id


@app.get("/")
async def root() -> dict:
    return {"message": "Todo API is running"}


@app.get("/todos", response_model=List[Todo])
async def list_todos() -> List[Todo]:
    return todos


@app.get("/todos/{todo_id}", response_model=Todo)
async def get_todo(todo_id: int) -> Todo:
    for todo in todos:
        if todo.id == todo_id:
            return todo
    raise HTTPException(status_code=404, detail="Todo not found")


@app.post("/todos", response_model=Todo, status_code=201)
async def create_todo(todo: TodoCreate) -> Todo:
    new_todo = Todo(id=get_next_id(), title=todo.title, description=todo.description, completed=todo.completed)
    todos.append(new_todo)
    return new_todo


@app.put("/todos/{todo_id}", response_model=Todo)
async def update_todo(todo_id: int, todo: TodoCreate) -> Todo:
    for index, existing_todo in enumerate(todos):
        if existing_todo.id == todo_id:
            updated_todo = Todo(
                id=existing_todo.id,
                title=todo.title,
                description=todo.description,
                completed=todo.completed,
            )
            todos[index] = updated_todo
            return updated_todo
    raise HTTPException(status_code=404, detail="Todo not found")


@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int) -> dict:
    for index, todo in enumerate(todos):
        if todo.id == todo_id:
            del todos[index]
            return {"message": f"Todo {todo_id} deleted"}
    raise HTTPException(status_code=404, detail="Todo not found")


if __name__ == "__main__":
    uvicorn.run("todos:app", host="0.0.0.0", port=8000, reload=True)

# Docker usage:
# 1) docker build -t todo-api .
# 2) docker run -p 8000:8000 todo-api
# For FastAPI on Docker, include:

