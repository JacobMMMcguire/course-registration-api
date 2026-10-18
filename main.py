from fastapi import FastAPI

from app.routers import admin, catalog, students

app = FastAPI(title="Course Catalog API")

app.include_router(catalog.router)
app.include_router(admin.router)
app.include_router(students.router)
