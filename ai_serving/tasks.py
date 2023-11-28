import os

import numpy as np

from celery import Celery
from celery.utils.log import get_task_logger

from . import models, object_storage
from .database import SessionLocal
from .model_worker import ModelWorker

EncodedInputs = bytes


REDIS_URL = os.getenv('REDIS_URL')

app = Celery('tasks', backend='rpc://', broker=REDIS_URL)

model_workers = {}  # model_id -> ModelWorker

logger = get_task_logger(__name__)


def load_model(model_id: int):
    global model_workers

    if model_id in model_workers:
        # Model already loaded
        return

    db = SessionLocal()
    print(f'Setting up model {model_id}')
    model = db.query(models.Model).filter(models.Model.id == model_id).one()
    model_workers[model_id] = ModelWorker(model)


@app.task
def preprocess(job_id: int):
    db = SessionLocal()
    print(f'Preprocessing job {job_id}')
    job = db.query(models.Job).filter(models.Job.id == job_id).one()

    job.status = models.JobStatus.PREPROCESSING
    db.add(job)
    db.commit()

    try:
        # Ensure model is loaded
        load_model(job.model_id)

        inputs = model_workers[job.model_id].preprocess(job.argument_path)
    except Exception as e:
        job.status = models.JobStatus.FAILED
        job.failed_log = str(e)
        db.add(job)
        db.commit()
        raise e

    job.status = models.JobStatus.PREPROCESSED
    db.add(job)
    db.commit()

    inference.delay(job_id, inputs)


@app.task
def inference(job_id: int, inputs: EncodedInputs):
    db = SessionLocal()
    print(f'Inferencing job {job_id}')
    job = db.query(models.Job).filter(models.Job.id == job_id).one()

    job.status = models.JobStatus.INFERENCING
    db.add(job)
    db.commit()

    try:
        # Ensure model is loaded
        load_model(job.model_id)

        outputs = model_workers[job.model_id].inference(inputs)
    except Exception as e:
        job.status = models.JobStatus.FAILED
        job.failed_log = str(e)
        db.add(job)
        db.commit()
        raise e

    job.status = models.JobStatus.INFERENCED
    db.add(job)
    db.commit()

    postprocess.delay(job_id, outputs)


@app.task
def postprocess(job_id: int, outputs: list[np.ndarray]):
    db = SessionLocal()
    print(f'Postprocessing job {job_id}')
    job = db.query(models.Job).filter(models.Job.id == job_id).one()

    job.status = models.JobStatus.POSTPROCESSING
    db.add(job)
    db.commit()

    try:
        # Ensure model is loaded
        load_model(job.model_id)

        result_path = model_workers[job.model_id].postprocess(job, outputs)
    except Exception as e:
        job.status = models.JobStatus.FAILED
        job.failed_log = str(e)
        db.add(job)
        db.commit()
        raise e

    job.status = models.JobStatus.COMPLETED
    job.result_path = result_path
    db.add(job)
    db.commit()
