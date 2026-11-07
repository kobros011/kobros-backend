from fastapi import FastAPI, Request
import os
from app.presentation.routes import user_routes, auth_routes, brand_routes, client_routes, expense_routes, liquidation_routes, loan_routes, payment_routes, route_routes, client_route_routes, expenses_concepts_routes, report_routes, route_movement_routes
from app.infrastructure.utils.lifespan import lifespan
from app.core.exceptions import AppException
from app.core.logger import logger
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Fast Api cobros", lifespan=lifespan)

# Origins (local + CORS_ORIGINS separadas por coma para Render/prod)
_default_origins = [
    "http://localhost",
    "http://localhost:5050",
    "http://localhost:5173",
]
_extra = os.getenv("CORS_ORIGINS", "")
origins = _default_origins + [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Excepciones
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "Error de validación", "details": exc.errors()},
    )

# Rutas
app.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
app.include_router(user_routes.router, prefix="/users", tags=["users"])
app.include_router(brand_routes.router, prefix="/brands", tags=["brands"])
app.include_router(client_routes.router, prefix="/clients", tags=["clients"])
app.include_router(expense_routes.router, prefix="/expenses", tags=["expenses"])
app.include_router(liquidation_routes.router, prefix="/liquidations", tags=["liquidations"])
app.include_router(loan_routes.router, prefix="/loans", tags=["loans"])
app.include_router(payment_routes.router, prefix="/payments", tags=["payments"])
app.include_router(route_routes.router, prefix="/routes", tags=["routes"])
app.include_router(client_route_routes.router, prefix="/clientroute", tags=["clientsroutes"])
app.include_router(expenses_concepts_routes.router, prefix="/expensesconcepts", tags=["expensesconcepts"])
app.include_router(report_routes.router, prefix="/reports", tags=["reports"])
app.include_router(route_movement_routes.router, prefix="/route-movements", tags=["route-movements"])