import os

from fastapi import APIRouter, File, Form, UploadFile

from app.core.config import UPLOAD_DIRECTORY, settings
from app.models import ResponseBase

router = APIRouter()


@router.post("/single", response_model=ResponseBase)
def upload_single_file(file: UploadFile = File(...), field: str = Form(...)):
    temp_dir = os.path.join(UPLOAD_DIRECTORY, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    file_location = os.path.join(temp_dir, file.filename)
    with open(file_location, "wb") as f:
        f.write(file.file.read())

    file_url = os.path.join("https://", settings.DOMAIN, temp_dir, file.filename)
    data = {
        "file_name": file.filename,
        "file_url": file_url,
        "field": field,
    }
    return ResponseBase(code=200, message="File uploaded successfully", data=data)
