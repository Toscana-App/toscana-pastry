from fastapi import APIRouter, Depends

from domain.models import User
from domain.repositories import UserRepository
from domain.use_cases import ListUsers
from api.v1.dependencies import require_admin
from api.v1.auth.dependencies import get_user_repository
from api.v1.admin.schemas import AdminUserItem, UserListResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=UserListResponse)
async def list_users(
    _admin: User = Depends(require_admin),
    user_repo: UserRepository = Depends(get_user_repository),
):
    users = await ListUsers(user_repo).execute()
    items = [
        AdminUserItem(
            user_id=user.id,
            email=user.email,
            role=user.role,
            google_id=user.google_id,
        )
        for user in users
    ]
    return UserListResponse(total=len(items), users=items)
