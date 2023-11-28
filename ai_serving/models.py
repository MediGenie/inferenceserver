import enum

from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Model(Base):
    __tablename__ = 'models'

    id: Mapped[int] = mapped_column(nullable=False, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default='now()')
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default='now()')

    name: Mapped[str] = mapped_column(nullable=False, unique=True)
    module_path: Mapped[str] = mapped_column(nullable=False)


class JobStatus(enum.Enum):
    PENDING = 'pending'

    PREPROCESSING = 'preprocessing'
    PREPROCESSED = 'preprocessed'

    INFERENCING = 'inferencing'
    INFERENCED = 'inferenced'

    POSTPROCESSING = 'postprocessing'

    COMPLETED = 'completed'
    FAILED = 'failed'


class Job(Base):
    __tablename__ = 'jobs'

    id: Mapped[int] = mapped_column(nullable=False, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default='now()')
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default='now()')

    status: Mapped[JobStatus] = mapped_column(default=JobStatus.PENDING, index=True)
    model_id = mapped_column(ForeignKey(Model.id), index=True)
    argument_path: Mapped[str] = mapped_column(nullable=False)
    result_path: Mapped[str | None] = mapped_column()

    failed_log: Mapped[str | None] = mapped_column()

    model: Mapped[Model] = relationship(Model, backref='jobs')
