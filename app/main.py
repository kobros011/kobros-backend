from fastapi import FastAPI, Request
from app.presentation.routes import user_routes
from app.presentation.routes import auth_routes
from app.presentation.routes import brand_routes
from app.presentation.routes import client_routes
from app.presentation.routes import expense_routes
from app.presentation.routes import liquidation_routes
from app.presentation.routes import loan_routes
from app.presentation.routes import payment_routes
from app.presentation.routes import route_routes
import app.infrastructure.models
from app.infrastructure.utils.lifespan import lifespan
from app.core.exceptions import AppException
from app.core.logger import logger
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Fast Api cobros", lifespan=lifespan)

# Origins 

origins = [
    "http://localhost",
    "http://localhost:5050",
    "http://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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