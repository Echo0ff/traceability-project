import os
import json
import uuid
from typing import Any, Optional, List

from fastapi import APIRouter, HTTPException, Form, UploadFile, File, BackgroundTasks
from sqlmodel import func, select
from app.models import ResponseBase

from app.api.deps import CurrentUser, SessionDep
from app.core.redis_conf import redis_client
from app.core.config import settings, UPLOAD_DIRECTORY, QR_CODE_DIRECTORY


router = APIRouter()


@router.post("/single", response_model=ResponseBase)
def upload_single_file(file: UploadFile = File(...), field: str = Form(...)):
    temp_dir = os.path.join(UPLOAD_DIRECTORY, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    file_location = os.path.join(temp_dir, file.filename)
    with open(file_location, "wb") as f:
        f.write(file.file.read())

    file_url = os.path.join("https", settings.DOMAIN, temp_dir, file.filename)
    data = {
        "file_name": file.filename,
        "file_url": file_url,
        "field": field,
    }
    return ResponseBase(code=200, message="File uploaded successfully", data=data)
