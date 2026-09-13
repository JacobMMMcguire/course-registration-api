from fastapi import FastAPI

from app.routers import admin, catalog

app = FastAPI(title="Course Catalog API")

app.include_router(catalog.router)
app.include_router(admin.router)
