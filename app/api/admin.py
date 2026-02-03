# backend/app/api/admin.py

from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import get_db
from app.api.auth import get_current_user, UserInDB

router = APIRouter()


def _require_admin(user: UserInDB):
    if not user or user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


@router.get("/clients")
async def list_clients(current_user: UserInDB = Depends(get_current_user), db=Depends(get_db)):
    _require_admin(current_user)

    cursor = db.users.find({}, {"hashed_password": 0})
    users = []
    async for u in cursor:
        u["id"] = str(u.get("_id"))
        u.pop("_id", None)
        users.append(u)

    return {"users": users}
