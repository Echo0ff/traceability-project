import os
from fastapi import APIRouter, Form, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.api.deps import SessionDep
from app.models import Middleman, Grower, ResponseBase
from app.core.redis_conf import redis_client
from app.core.config import UPLOAD_DIRECTORY, QR_CODE_DIRECTORY
from app.utils import generate_qr_code, verify_code
import json

router = APIRouter()


@router.post("/", response_model=ResponseBase)
async def verify_form(
    background_tasks: BackgroundTasks,
    session: SessionDep,
    temp_id: str = Form(...),
    verification_code: str = Form(...),
):
    # 获取表单类型
    form_type = redis_client.get(f"pending_form:{temp_id}:type")
    if not form_type:
        raise HTTPException(status_code=400, detail="Invalid or expired temporary ID")

    if isinstance(form_type, bytes):
        form_type = form_type.decode()

    # 获取待验证的数据
    pending_data = redis_client.get(f"pending_form:{temp_id}")
    if not pending_data:
        raise HTTPException(status_code=400, detail="Invalid or expired temporary ID")
    if isinstance(pending_data, bytes):
        pending_data = pending_data.decode()

    data = json.loads(pending_data)

    # 验证码检查
    if not verify_code(data["phone_number"], verification_code):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # 根据表单类型执行不同的操作
    if form_type == "company_middleman":
        result = create_company_middleman(session, data, temp_id)
    elif form_type == "individual_grower":
        result = create_individual_grower(session, data, temp_id)
    elif form_type == "company_grower":
        result = create_company_grower(session, data, temp_id)
    elif form_type == "individual_middleman":
        result = create_individual_middleman(session, data, temp_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid form type")

    # 清理Redis中的临时数据
    redis_client.delete(f"pending_form:{temp_id}")
    redis_client.delete(f"pending_form:{temp_id}:type")
    redis_client.delete(f"pending_form_files:{temp_id}:business_license_photo")
    redis_client.delete(f"pending_form_files:{temp_id}:transaction_contracts")

    return ResponseBase(
        message=f"{form_type} created successfully", code=200, data=result
    )


def create_company_grower(session: SessionDep, data: dict, temp_id: str):
    grower_data = Grower(**data)

    # 生成临时的 QR 码值
    temp_qr_code = ""

    grower = Grower(**grower_data.dict(), qr_code=temp_qr_code)
    session.add(grower)
    session.flush()  # 这会给 grower 分配一个 ID，但不会提交事务

    # 获取文件名
    business_license_photo_filename = redis_client.get(
        f"pending_form_files:{temp_id}:business_license_photo"
    )
    land_ownership_certificate_filename = redis_client.get(
        f"pending_form_files:{temp_id}:land_ownership_certificate"
    )
    crop_type_pic_filenames = redis_client.lrange(
        f"pending_form_files:{temp_id}:crop_type_pic", 0, -1
    )

    # 更新文件路径
    if business_license_photo_filename:
        grower.business_license_photo = os.path.join(
            UPLOAD_DIRECTORY,
            "business_license",
            str(grower.id),
            business_license_photo_filename,
        )

    if land_ownership_certificate_filename:
        grower.land_ownership_certificate = os.path.join(
            UPLOAD_DIRECTORY,
            "land_ownership",
            str(grower.id),
            land_ownership_certificate_filename,
        )

    crop_type_pic_paths = []
    if crop_type_pic_filenames:
        for filename in crop_type_pic_filenames:
            path = os.path.join(
                UPLOAD_DIRECTORY,
                "crop_type_pic",
                str(grower.id),
                filename,
            )
            crop_type_pic_paths.append(path)
    grower.crop_type_pic = crop_type_pic_paths

    # 生成二维码
    qr_code_filename = generate_qr_code(str(grower.id), QR_CODE_DIRECTORY)
    qr_code_access_path = f"upload/qrcode/{qr_code_filename}".replace("/", ",,")
    grower.qr_code = qr_code_access_path

    session.commit()
    session.refresh(grower)

    return grower


def create_individual_grower(session: SessionDep, data: dict, temp_id: str):
    grower_data = Grower(**data)
    grower = Grower(**grower_data.dict())
    session.add(grower)
    session.commit()
    session.refresh(grower)

    # 获取文件名
    id_card_photo_filename = redis_client.get(
        f"pending_form_files:{temp_id}:id_card_photo"
    )
    land_ownership_certificate_filename = redis_client.get(
        f"pending_form_files:{temp_id}:land_ownership_certificate"
    )
    crop_type_pic_filenames = redis_client.lrange(
        f"pending_form_files:{temp_id}:crop_type_pic", 0, -1
    )

    # 更新文件路径
    if id_card_photo_filename:
        grower.id_card_photo = os.path.join(
            UPLOAD_DIRECTORY,
            "idcard",
            str(grower.id),
            id_card_photo_filename.decode(),
        )

    if land_ownership_certificate_filename:
        grower.land_ownership_certificate = os.path.join(
            UPLOAD_DIRECTORY,
            "land_ownership",
            str(grower.id),
            land_ownership_certificate_filename.decode(),
        )

    crop_type_pic_paths = []
    if crop_type_pic_filenames:
        for filename in crop_type_pic_filenames:
            path = os.path.join(
                UPLOAD_DIRECTORY,
                "crop_type_pic",
                str(grower.id),
                filename.decode(),
            )
            crop_type_pic_paths.append(path)
    grower.crop_type_pic = crop_type_pic_paths

    # 生成二维码
    qr_code_filename = generate_qr_code(str(grower.id), QR_CODE_DIRECTORY)
    qr_code_access_path = f"upload/qrcode/{qr_code_filename}".replace("/", ",,")
    grower.qr_code = qr_code_access_path

    session.commit()
    session.refresh(grower)

    return grower


def create_company_middleman(session: SessionDep, data: dict, temp_id: str):
    middleman_data = Middleman(**data)
    middleman = Middleman(**middleman_data.dict())
    session.add(middleman)
    session.commit()
    session.refresh(middleman)

    # 获取文件名
    business_license_photo_filename = redis_client.get(
        f"pending_form_files:{temp_id}:business_license_photo"
    )
    transaction_contract_filenames = redis_client.lrange(
        f"pending_form_files:{temp_id}:transaction_contracts", 0, -1
    )

    # 更新文件路径
    if business_license_photo_filename:
        middleman.business_license_photo = os.path.join(
            UPLOAD_DIRECTORY,
            "business_license",
            str(middleman.id),
            business_license_photo_filename.decode(),
        )

    transaction_contract_paths = []
    if transaction_contract_filenames:
        for filename in transaction_contract_filenames:
            path = os.path.join(
                UPLOAD_DIRECTORY,
                "transaction_contract",
                str(middleman.id),
                filename.decode(),
            )
            transaction_contract_paths.append(path)
    middleman.transaction_contracts = transaction_contract_paths

    # 生成二维码
    qr_code_filename = generate_qr_code(str(middleman.id), QR_CODE_DIRECTORY)
    qr_code_access_path = f"upload/qrcode/{qr_code_filename}".replace("/", ",,")
    middleman.qr_code = qr_code_access_path

    session.commit()
    session.refresh(middleman)

    return middleman


def create_individual_middleman(session: SessionDep, data: dict, temp_id: str):
    middleman_data = Middleman(**data)
    middleman = Middleman(**middleman_data.dict())
    session.add(middleman)
    session.commit()
    session.refresh(middleman)

    # 获取文件名
    id_card_photo_filename = redis_client.get(
        f"pending_form_files:{temp_id}:id_card_photo"
    )
    transaction_contract_filenames = redis_client.lrange(
        f"pending_form_files:{temp_id}:transaction_contracts", 0, -1
    )

    # 更新文件路径
    if id_card_photo_filename:
        middleman.id_card_photo = os.path.join(
            UPLOAD_DIRECTORY,
            "id_card",
            str(middleman.id),
            id_card_photo_filename.decode(),
        )

    transaction_contract_paths = []
    if transaction_contract_filenames:
        for filename in transaction_contract_filenames:
            path = os.path.join(
                UPLOAD_DIRECTORY,
                "transaction_contract",
                str(middleman.id),
                filename.decode(),
            )
            transaction_contract_paths.append(path)
    middleman.transaction_contracts = transaction_contract_paths

    # 生成二维码
    qr_code_filename = generate_qr_code(str(middleman.id), QR_CODE_DIRECTORY)
    qr_code_access_path = f"upload/qrcode/{qr_code_filename}".replace("/", ",,")
    middleman.qr_code = qr_code_access_path

    session.commit()
    session.refresh(middleman)

    return middleman
