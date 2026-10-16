import json
import time
import uuid
from datetime import timedelta
from pathlib import Path
from time import sleep

import cv2
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .core.clock import beijing_now, beijing_today
from .core.security import create_token, decode_token, hash_password, verify_password
from .database import Base, engine, get_db
from .models import Task, User
from .services.counting import count_objects
from .services.image_io import load_image

app = FastAPI(title=settings.app_name)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
settings.storage_path.joinpath("uploads").mkdir(parents=True, exist_ok=True)
settings.storage_path.joinpath("results").mkdir(parents=True, exist_ok=True)
# 只暴露 uploads / results 两个子目录。以前挂在 STORAGE_DIR 根上，
# 导致 /files/app.db（含密码哈希的数据库文件）可以被直接下载。
# URL 形状不变（原图 /files/uploads/*，标注图 /files/results/*），历史记录仍可访问。
app.mount("/files/uploads", StaticFiles(directory=settings.storage_path / "uploads"), name="uploads")
app.mount("/files/results", StaticFiles(directory=settings.storage_path / "results"), name="results")
security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6)
    role: str = "user"
    daily_quota: int = Field(default=100, ge=1)


class UserUpdate(BaseModel):
    role: str | None = None
    status: int | None = None
    daily_quota: int | None = Field(default=None, ge=1)


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=6)


class InstanceEdit(BaseModel):
    instances: list[dict]


def ok(data):
    return {"code": 0, "message": "ok", "data": data}


def fail(message: str, code: int = 1):
    return {"code": code, "message": message, "data": None}


def current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        payload = decode_token(credentials.credentials)
        user = db.get(User, int(payload["sub"]))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="登录状态已失效") from exc
    if not user or not user.status:
        raise HTTPException(status_code=401, detail="账号不可用")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def serialize_user(user: User) -> dict:
    return {"id": user.id, "username": user.username, "role": user.role, "status": user.status, "daily_quota": user.daily_quota, "created_at": user.created_at.isoformat(), "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None}


def task_data(task: Task, include_user: bool = False) -> dict:
    data = {"task_id": task.task_id, "count": task.count, "mode": task.mode, "annotated_url": f"/files/{task.annotated_path}", "original_url": f"/files/{task.original_path}", "instances": json.loads(task.instances_json), "elapsed_ms": task.elapsed_ms, "width": task.width, "height": task.height, "status": task.status, "created_at": task.created_at.isoformat(), "error_msg": task.error_msg}
    if include_user:
        data["username"] = task.user.username if task.user else None
    return data


def get_task(task_id: str, user: User, db: Session) -> Task:
    task = db.scalar(select(Task).where(Task.task_id == task_id))
    if not task or (task.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)


@app.get("/api/health")
def health():
    return ok({"status": "healthy"})


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not user.status or not verify_password(payload.password, user.password_hash):
        sleep(1)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user.last_login_at = beijing_now()
    db.commit()
    access = create_token(user.id, user.username, user.role, "access", timedelta(minutes=settings.access_token_expire_minutes))
    refresh = create_token(user.id, user.username, user.role, "refresh", timedelta(days=settings.refresh_token_expire_days))
    return ok({"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_in": settings.access_token_expire_minutes * 60, "user": serialize_user(user)})


@app.post("/api/auth/refresh")
def refresh(payload: dict, db: Session = Depends(get_db)):
    try:
        claims = decode_token(payload.get("refresh_token", ""), "refresh")
        user = db.get(User, int(claims["sub"]))
        if not user or not user.status:
            raise ValueError
    except Exception as exc:
        raise HTTPException(status_code=401, detail="刷新令牌无效") from exc
    return ok({"access_token": create_token(user.id, user.username, user.role, "access", timedelta(minutes=settings.access_token_expire_minutes)), "expires_in": settings.access_token_expire_minutes * 60})


@app.post("/api/auth/logout")
def logout(user: User = Depends(current_user)):
    return ok({})


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return ok(serialize_user(user))


@app.post("/api/auth/change-password")
def change_password(payload: ChangePasswordRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return ok({})


@app.post("/api/count")
async def count(file: UploadFile = File(...), mode: str = Form("pills"), params: str = Form("{}"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    if mode not in {"pills", "beans", "cells"}:
        raise HTTPException(status_code=422, detail="无效的计数模式")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp", "image/bmp"}:
        raise HTTPException(status_code=400, detail="仅支持 jpg、png、webp、bmp 图片")
    raw = await file.read()
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="图片超过大小限制")
    task_id = uuid.uuid4().hex
    try:
        options = json.loads(params or "{}")
        image, width, height = load_image(raw, int(options.get("max_side", settings.default_max_side)))
        started = time.perf_counter()
        annotated, instances, warnings = count_objects(image, mode, options)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        original_path = f"uploads/{task_id}_original.jpg"
        annotated_path = f"results/{task_id}_annotated.jpg"
        cv2.imwrite(str(settings.storage_path / original_path), image, [cv2.IMWRITE_JPEG_QUALITY, 88])
        cv2.imwrite(str(settings.storage_path / annotated_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 72])
        task = Task(task_id=task_id, user_id=user.id, mode=mode, params_json=json.dumps(options), original_path=original_path, annotated_path=annotated_path, count=len(instances), instances_json=json.dumps(instances), width=width, height=height, elapsed_ms=elapsed_ms)
        db.add(task)
        db.commit()
        return ok({**task_data(task), "warnings": warnings})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"图片处理失败: {exc}") from exc


@app.get("/api/count/{task_id}")
def count_result(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(task_data(get_task(task_id, user, db)))


@app.post("/api/count/{task_id}/edit")
def edit_count(task_id: str, payload: InstanceEdit, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = get_task(task_id, user, db)
    task.instances_json = json.dumps(payload.instances)
    task.count = len(payload.instances)
    db.commit()
    return ok(task_data(task))


@app.get("/api/tasks")
def tasks(page: int = 1, page_size: int = 20, mode: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Task).order_by(Task.created_at.desc()) if user.role == "admin" else select(Task).where(Task.user_id == user.id).order_by(Task.created_at.desc())
    if mode:
        query = query.where(Task.mode == mode)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return ok({"items": [task_data(item, include_user=user.role == "admin") for item in items], "total": total, "page": page, "page_size": page_size})


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = get_task(task_id, user, db)
    for relative in (task.original_path, task.annotated_path):
        path = settings.storage_path / relative
        if path.exists():
            path.unlink()
    db.delete(task)
    db.commit()
    return ok({})


def stats_for(query):
    total = len(query)
    success = sum(task.status == "success" for task in query)
    return {"total_tasks": total, "success_tasks": success, "failed_tasks": total - success, "total_objects": sum(task.count for task in query), "avg_elapsed_ms": round(sum(task.elapsed_ms for task in query) / success) if success else 0}


@app.get("/api/stats/me/summary")
def summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    all_tasks = db.scalars(select(Task).where(Task.user_id == user.id)).all()
    today = beijing_today()
    today_tasks = sum(task.created_at.date() == today and task.status == "success" for task in all_tasks)
    return ok({**stats_for(all_tasks), "today_tasks": today_tasks})


@app.get("/api/stats/me/by-mode")
def by_mode(user: User = Depends(current_user), db: Session = Depends(get_db)):
    all_tasks = db.scalars(select(Task).where(Task.user_id == user.id)).all()
    return ok([{"mode": mode, "tasks": sum(task.mode == mode for task in all_tasks), "objects": sum(task.count for task in all_tasks if task.mode == mode)} for mode in ("pills", "beans", "cells")])


@app.get("/api/stats/me/daily")
def daily(days: int = 30, user: User = Depends(current_user), db: Session = Depends(get_db)):
    all_tasks = db.scalars(select(Task).where(Task.user_id == user.id)).all()
    dates = sorted({task.created_at.date().isoformat() for task in all_tasks})[-days:]
    return ok([{ "date": date, "tasks": sum(task.created_at.date().isoformat() == date for task in all_tasks), "objects": sum(task.count for task in all_tasks if task.created_at.date().isoformat() == date), "avg_elapsed_ms": 0} for date in dates])


@app.get("/api/admin/users")
def admin_users(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    return ok({"items": [serialize_user(item) for item in db.scalars(select(User).order_by(User.id)).all()]})


@app.get("/api/admin/users/{user_id}")
def admin_user_detail(user_id: int, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ok(serialize_user(target))


@app.post("/api/admin/users")
def create_user(payload: UserCreate, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=409, detail="用户名已存在")
    target = User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role, daily_quota=payload.daily_quota)
    db.add(target)
    db.commit()
    db.refresh(target)
    return ok(serialize_user(target))


@app.patch("/api/admin/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(target, key, value)
    db.commit()
    return ok(serialize_user(target))


@app.delete("/api/admin/users/{user_id}")
def remove_user(user_id: int, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target or target.id == user.id:
        raise HTTPException(status_code=400, detail="不能删除当前管理员")
    db.delete(target)
    db.commit()
    return ok({})


@app.post("/api/admin/users/{user_id}/reset-password")
def reset_password(user_id: int, payload: PasswordReset, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    target.password_hash = hash_password(payload.new_password)
    db.commit()
    return ok({})


@app.get("/api/admin/overview")
def admin_overview(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    all_tasks = db.scalars(select(Task)).all()
    today = beijing_today()
    return ok({"user_count": db.scalar(select(func.count(User.id))) or 0, "task_count": len(all_tasks), "today_tasks": sum(task.created_at.date() == today for task in all_tasks), "success_rate": round(sum(task.status == "success" for task in all_tasks) / len(all_tasks) * 100, 1) if all_tasks else 0})


@app.get("/api/admin/tasks")
def admin_tasks(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    return ok({"items": [task_data(task, include_user=True) for task in db.scalars(select(Task).order_by(Task.created_at.desc())).all()]})


@app.get("/api/admin/stats/users")
def admin_user_stats(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.username)).all()
    rows = []
    for target in users:
        user_tasks = db.scalars(select(Task).where(Task.user_id == target.id)).all()
        successful = [task for task in user_tasks if task.status == "success"]
        rows.append({"user_id": target.id, "username": target.username, "task_count": len(user_tasks), "success_count": len(successful), "failed_count": len(user_tasks) - len(successful), "total_objects": sum(task.count for task in successful), "avg_elapsed_ms": round(sum(task.elapsed_ms for task in successful) / len(successful)) if successful else 0})
    return ok(rows)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
