from fastapi import APIRouter, HTTPException, Request
from .account_models import StudentCreateRequest, StudentUpdateRequest, AccountSubscriptionRequest
from .account_store import (
    ensure_account, ensure_default_student, list_students, create_student,
    update_student, student_belongs_to_account, create_subscription,
    get_account_overview,
)


def build_account_router(resolve_username, require_admin):
    router = APIRouter(prefix="/api")

    def current_account(request: Request):
        username = resolve_username(request)
        if not username:
            raise HTTPException(status_code=401, detail="Login required")
        account = ensure_account(username)
        ensure_default_student(account["id"])
        return account

    @router.get("/account")
    async def account_detail(request: Request):
        account = current_account(request)
        return {"success": True, **get_account_overview(account["email"])}

    @router.get("/students")
    async def students(request: Request):
        account = current_account(request)
        return {"success": True, "students": list_students(account["id"])}

    @router.post("/students")
    async def add_student(request: Request, body: StudentCreateRequest):
        account = current_account(request)
        student = create_student(account["id"], body.name, body.year_group, body.age)
        return {"success": True, "student": student}

    @router.put("/students/{student_id}")
    async def edit_student(student_id: str, request: Request, body: StudentUpdateRequest):
        account = current_account(request)
        if not student_belongs_to_account(student_id, account["id"]):
            raise HTTPException(status_code=404, detail="Student not found")
        student = update_student(student_id, account["id"], **body.model_dump(exclude_unset=True))
        return {"success": True, "student": student}

    @router.post("/admin/account-subscriptions")
    async def admin_add_subscription(request: Request, body: AccountSubscriptionRequest):
        require_admin(request)
        account = ensure_account(body.email)
        sub = create_subscription(
            account["id"], body.plan, body.status, body.duration_days,
            body.stripe_customer_id, body.stripe_subscription_id,
        )
        return {"success": True, "account": account, "subscription": sub}

    @router.get("/admin/accounts/{email}")
    async def admin_account(email: str, request: Request):
        require_admin(request)
        return {"success": True, **get_account_overview(email)}

    return router
