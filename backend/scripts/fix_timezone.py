"""把库里按 UTC 写入的历史时间整体平移为北京时间（UTC+8）。

背景：早期版本用 datetime.utcnow() 写 created_at / last_login_at，容器默认 UTC，
库里存的时间比北京时间早 8 小时（界面上看到的、图上烧录的时间戳都偏早 8 小时）。
代码已统一改为北京时间（backend/app/core/clock.py），这个脚本用来修正已经落库的旧数据。

默认只预演不写库，确认无误后加 --apply 执行。

注意：脚本不可重复执行，跑两次会多加 8 小时。执行前请先备份数据库文件。
"""

import argparse
import sys
from datetime import timedelta
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.models import Task, User


def main() -> None:
    parser = argparse.ArgumentParser(description="把历史时间从 UTC 平移为北京时间")
    parser.add_argument("--apply", action="store_true", help="真正写入数据库，默认只预演")
    parser.add_argument("--hours", type=int, default=8, help="平移小时数，默认 8（UTC -> UTC+8）")
    args = parser.parse_args()
    shift = timedelta(hours=args.hours)

    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id).all()
        tasks = db.query(Task).order_by(Task.created_at).all()
        print(f"数据库: {settings.database_url}")
        print(f"users={len(users)} tasks={len(tasks)} 平移=+{args.hours}h")
        for user in users[:3]:
            login = f"{user.last_login_at} -> {user.last_login_at + shift}" if user.last_login_at else "None"
            print(f"  user {user.username}: created_at {user.created_at} -> {user.created_at + shift} | last_login_at {login}")
        for task in tasks[:3]:
            print(f"  task {task.task_id[:8]}: created_at {task.created_at} -> {task.created_at + shift}")
        if tasks:
            print(f"  ...任务时间范围 {tasks[0].created_at} ~ {tasks[-1].created_at}"
                  f" -> {tasks[0].created_at + shift} ~ {tasks[-1].created_at + shift}")

        if not args.apply:
            print("\n预演结束，未写入数据库。确认无误后加 --apply 执行。")
            return

        for user in users:
            user.created_at = user.created_at + shift
            if user.last_login_at:
                user.last_login_at = user.last_login_at + shift
        for task in tasks:
            task.created_at = task.created_at + shift
        db.commit()
        print(f"\n已平移 {len(users)} 个用户、{len(tasks)} 条任务记录。请勿重复执行本脚本。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
