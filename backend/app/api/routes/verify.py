import json
import logging
import os
import shutil
from typing import List
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.core.config import QR_CODE_DIRECTORY, UPLOAD_DIRECTORY, settings
from app.core.redis_conf import redis_client
from app.models import Grower, GrowerCreate, Middleman, ResponseBase
from app.utils import generate_qr_code, verify_code

router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VerificationData(BaseModel):
    temp_id: str
    verification_code: str


router = APIRouter()


@router.post("/", response_model=ResponseBase)
async def verify_form(
    background_tasks: BackgroundTasks,
    session: SessionDep,
    verification_data: VerificationData,
):
    # localhost/uploads/temp/WechatIMG323.jpg
    #
    # 获取待验证的数据
    pending_data = redis_client.get(f"pending_form:{verification_data.temp_id}")
    if not pending_data:
        raise HTTPException(status_code=400, detail="Invalid or expired temporary ID")

    redis_data = json.loads(pending_data)
    form_type = redis_data.get("form_type")
    grower_data = redis_data.get("grower_data")
    files = redis_data.get("files", {})

    if not form_type or not grower_data:
        raise HTTPException(status_code=400, detail="Invalid data format")

    # 验证码检查
    if not verify_code(
        grower_data["phone_number"], verification_data.verification_code
    ):
        return ResponseBase(code=400, message="Invalid verification code")

    # 根据表单类型执行不同的操作
    if form_type == "company_grower":
        logger.info(
            f"grower_data: {grower_data}, files:{files}, temp_id: {verification_data.temp_id}"
        )
        result = await create_company_grower(
            session, grower_data, files, verification_data.temp_id
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid form type")

    # 清理Redis中的临时数据
    redis_client.delete(f"pending_form:{verification_data.temp_id}")

    return ResponseBase(
        message=f"{form_type} created successfully", code=200, data=result
    )


async def create_company_grower(
    session: SessionDep, data: dict, files: dict, temp_id: str
):
    grower_data = GrowerCreate(**data)

    # 生成临时的 QR 码值
    temp_qr_code = ""

    grower = Grower(**grower_data.dict(), type="company", qr_code=temp_qr_code)
    session.add(grower)
    session.flush()  # 这会给 grower 分配一个 ID，但不会提交事务

    # 处理文件
    business_license_photos = await save_files(
        files.get("business_license_photos", []), "business_license", grower.id
    )
    land_ownership_certificates = await save_files(
        files.get("land_ownership_certificate", []), "land_ownership", grower.id
    )
    crop_type_pics = await save_files(
        files.get("crop_type_pic", []), "crop_type_pic", grower.id
    )
    id_card_photo = await save_files(
        files.get("id_card_photo", []), "idcard", grower.id
    )
    prefix = f"https://{settings.DOMAIN}/{UPLOAD_DIRECTORY}"
    if business_license_photos:
        grower.business_license_photos = [
            prefix + photo for photo in business_license_photos
        ]
    if land_ownership_certificates:
        grower.land_ownership_certificate = [
            prefix + cert for cert in land_ownership_certificates
        ]
    if crop_type_pics:
        grower.crop_type_pic = [prefix + pic for pic in crop_type_pics]
    if id_card_photo:
        grower.id_card_photo = [prefix + id_card for id_card in id_card_photo]

    # 生成二维码
    qr_code_filename = generate_qr_code(
        grower.id, f"/grower/{str(grower.id)}", QR_CODE_DIRECTORY
    )

    qr_code_access_path = os.path.join(UPLOAD_DIRECTORY, "qrcode", qr_code_filename)
    grower.qr_code = qr_code_access_path

    session.commit()
    session.refresh(grower)

    return grower


async def save_files(file_urls: List[str], folder: str, grower_id: int) -> List[str]:
    saved_paths = []
    for file_url in file_urls:
        # 解析 URL，获取文件名
        parsed_url = urlparse(file_url)
        filename = os.path.basename(parsed_url.path)

        # 构造本地源文件路径
        source_path = os.path.join("uploads", *parsed_url.path.split("/")[2:])

        if not os.path.exists(source_path):
            logger.error(f"File not found: {source_path}")
            continue

        # 构造目标文件路径
        destination_path = os.path.join(
            UPLOAD_DIRECTORY, folder, str(grower_id), filename
        )
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

        try:
            # 如果目标文件已存在，先删除
            if os.path.exists(destination_path):
                os.remove(destination_path)

            # 移动文件
            shutil.copy(source_path, destination_path)

            # 保存新的文件路径（这里保存的是相对路径，方便后续生成URL）
            relative_path = os.path.join(folder, str(grower_id), filename)
            saved_paths.append(relative_path)
        except shutil.Error as e:
            logger.error(f"Error moving file {source_path}: {str(e)}")
            # 如果移动失败，尝试复制
            try:
                shutil.copy2(source_path, destination_path)
                relative_path = os.path.join(folder, str(grower_id), filename)
                saved_paths.append(relative_path)
            except shutil.Error as e:
                logger.error(f"Error copying file {source_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error processing file {source_path}: {str(e)}")

    return saved_paths


# @router.post("/", response_model=ResponseBase)
# async def verify_form(
#     background_tasks: BackgroundTasks,
#     session: SessionDep,
#     temp_id: str = Form(...),
#     verification_code: str = Form(...),
# ):
#     # 获取表单类型
#     form_type = redis_client.get(f"pending_form:{temp_id}:type")
#     if not form_type:
#         raise HTTPException(status_code=400, detail="Invalid or expired temporary ID")

#     if isinstance(form_type, bytes):
#         form_type = form_type.decode()

#     # 获取待验证的数据
#     pending_data = redis_client.get(f"pending_form:{temp_id}")
#     if not pending_data:
#         raise HTTPException(status_code=400, detail="Invalid or expired temporary ID")
#     if isinstance(pending_data, bytes):
#         pending_data = pending_data.decode()

#     data = json.loads(pending_data)

#     # 验证码检查
#     if not verify_code(data["phone_number"], verification_code):
#         raise HTTPException(status_code=400, detail="Invalid verification code")

#     # 根据表单类型执行不同的操作
#     if form_type == "company_middleman":
#         result = create_company_middleman(session, data, temp_id)
#     elif form_type == "individual_grower":
#         result = create_individual_grower(session, data, temp_id)
#     elif form_type == "company_grower":
#         result = create_company_grower(session, data, temp_id)
#     elif form_type == "individual_middleman":
#         result = create_individual_middleman(session, data, temp_id)
#     else:
#         raise HTTPException(status_code=400, detail="Invalid form type")

#     # 清理Redis中的临时数据
#     redis_client.delete(f"pending_form:{temp_id}")
#     redis_client.delete(f"pending_form:{temp_id}:type")
#     redis_client.delete(f"pending_form_files:{temp_id}:business_license_photos")
#     redis_client.delete(f"pending_form_files:{temp_id}:transaction_contracts")

#     return ResponseBase(
#         message=f"{form_type} created successfully", code=200, data=result
#     )


# def create_company_grower(session: SessionDep, data: dict, temp_id: str):
#     grower_data = Grower(**data)

#     # 生成临时的 QR 码值
#     temp_qr_code = ""

#     grower = Grower(**grower_data.dict(), qr_code=temp_qr_code)
#     session.add(grower)
#     session.flush()  # 这会给 grower 分配一个 ID，但不会提交事务

#     # 获取文件名
#     business_license_photos_filename = redis_client.get(
#         f"pending_form_files:{temp_id}:business_license_photos"
#     )
#     print(f"business_license_photos_filename:{business_license_photos_filename}")

#     land_ownership_certificate_filename = redis_client.get(
#         f"pending_form_files:{temp_id}:land_ownership_certificate"
#     )
#     print(land_ownership_certificate_filename)
#     crop_type_pic_filenames = redis_client.lrange(
#         f"pending_form_files:{temp_id}:crop_type_pic", 0, -1
#     )
#     print(crop_type_pic_filenames)

#     # 更新文件路径
#     if business_license_photos_filename:
#         grower.business_license_photos = os.path.join(
#             UPLOAD_DIRECTORY,
#             "business_license",
#             str(grower.id),
#             business_license_photos_filename,
#         )

#     if land_ownership_certificate_filename:
#         grower.land_ownership_certificate = os.path.join(
#             UPLOAD_DIRECTORY,
#             "land_ownership",
#             str(grower.id),
#             land_ownership_certificate_filename,
#         )

#     crop_type_pic_paths = []
#     if crop_type_pic_filenames:
#         for filename in crop_type_pic_filenames:
#             path = os.path.join(
#                 UPLOAD_DIRECTORY,
#                 "crop_type_pic",
#                 str(grower.id),
#                 filename,
#             )
#             crop_type_pic_paths.append(path)
#     grower.crop_type_pic = crop_type_pic_paths

#     # 生成二维码
#     qr_code_filename = generate_qr_code(str(grower.id), QR_CODE_DIRECTORY)
#     qr_code_access_path = f"upload/qrcode/{qr_code_filename}".replace("/", ",,")
#     grower.qr_code = qr_code_access_path

#     session.commit()
#     session.refresh(grower)

#     return grower


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
    business_license_photos_filename = redis_client.get(
        f"pending_form_files:{temp_id}:business_license_photos"
    )
    transaction_contract_filenames = redis_client.lrange(
        f"pending_form_files:{temp_id}:transaction_contracts", 0, -1
    )

    # 更新文件路径
    if business_license_photos_filename:
        middleman.business_license_photos = os.path.join(
            UPLOAD_DIRECTORY,
            "business_license",
            str(middleman.id),
            business_license_photos_filename.decode(),
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
            id_card_photo_filename,
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
