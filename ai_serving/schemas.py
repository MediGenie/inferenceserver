from datetime import datetime

from pydantic import BaseModel

from .models import JobStatus


class ItemBase(BaseModel):
    created_at: datetime
    updated_at: datetime


class Model(ItemBase):
    id: int
    name: str

    class Config:
        orm_mode = True


class ModelCreate(BaseModel):
    name: str


class Job(ItemBase):
    id: int
    status: JobStatus
    result_path: str | None
    failed_log: str | None

    class Config:
        orm_mode = True


class JobCreate(BaseModel):
    model_id: int
    argument_path: str


class FileCreated(BaseModel):
    path: str
