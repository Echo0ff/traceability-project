import os
import uuid
from datetime import datetime

from fastapi import APIRouter, File, Form, UploadFile

from app.core.config import UPLOAD_DIRECTORY, settings
from app.models import ResponseBase

router = APIRouter()


@router.post("/single", response_model=ResponseBase)
def upload_single_file(file: UploadFile = File(...), field: str = Form(...)):
    temp_dir = os.path.join(UPLOAD_DIRECTORY, "temp")
    os.makedirs(temp_dir, exist_ok=True)

    # 生成唯一文件名，包含原始文件名
    file_name, file_extension = os.path.splitext(file.filename)
    unique_filename = f"{file_name}_{uuid.uuid4().hex}_{int(datetime.now().timestamp())}{file_extension}"

    file_location = os.path.join(temp_dir, unique_filename)
    with open(file_location, "wb") as f:
        f.write(file.file.read())

    file_url = f"https://{settings.DOMAIN}/{temp_dir}/{unique_filename}"
    data = {
        "file_name": unique_filename,
        "file_url": file_url,
        "field": field,
    }
    return ResponseBase(code=200,
                        message="File uploaded successfully",
                        data=data)
