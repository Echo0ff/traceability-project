from fastapi import APIRouter

from app.api.routes import index, transactions, uploads, login, users

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
# api_router.include_router(utils.router, prefix="/utils", tags=["utils"])
# api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(index.router, prefix="/index", tags=["index"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
# api_router.include_router(grower.router, prefix="/grower", tags=["grower"])
# api_router.include_router(middleman.router, prefix="/middleman", tags=["middleman"])
# api_router.include_router(verify.router, prefix="/verify", tags=["verify"])
api_router.include_router(transactions.router,
                          prefix="/trac",
                          tags=["transactions"])
