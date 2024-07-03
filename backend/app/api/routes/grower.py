import os
import json
import uuid
from typing import Any, Optional, List

from fastapi import APIRouter, HTTPException, Form, UploadFile, File, BackgroundTasks
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.redis_conf import redis_client
from app.models import (
    Grower,
    CompanyGrowerCreate,
    IndividualGrowerCreate,
    GrowerOut,
    GrowersOut,
    ResponseBase,
)

from app.core.config import UPLOAD_DIRECTORY, QR_CODE_DIRECTORY
from app.utils import (
    save_file,
    generate_qr_code,
    model_to_dict,
    generate_verification_code,
    send_verification_code,
    store_verification_code,
)


router = APIRouter()


@router.post("/company", response_model=ResponseBase, summary="创建企业种植主")
async def create_company_grower(
    background_tasks: BackgroundTasks,
    session: SessionDep,
    grower_data: CompanyGrowerCreate,
) -> Any:
    """
    Create a company grower
    """
    # 生成验证码
    code = generate_verification_code()
    # 存储验证码
    store_verification_code(grower_data.phone_number, code)
    # 异步发送验证码
    background_tasks.add_task(send_verification_code, grower_data.phone_number, code)

    # 生成临时ID
    temp_id = str(uuid.uuid4())

    # 准备存储到Redis的数据
    redis_data = {
        "form_type": "company_grower",
        "grower_data": grower_data.model_dump(),
        "files": {
            "business_license_photos": grower_data.business_license_photos,
            "land_ownership_certificate": grower_data.land_ownership_certificate,
            "crop_type_pic": grower_data.crop_type_pic,
            "id_card_photo": grower_data.id_card_photo,
        },
    }

    # 将所有数据作为一个JSON字符串存储到Redis
    redis_client.setex(f"pending_form:{temp_id}", 1800, json.dumps(redis_data))

    return ResponseBase(
        message="Company grower created successfully. Please verify.",
        code=200,
        data={"temp_id": temp_id},
    )


@router.post("/individual", response_model=ResponseBase, summary="创建个人种植主")
async def create_individual_grower(
    background_tasks: BackgroundTasks,
    session: SessionDep,
    grower_data: IndividualGrowerCreate,
) -> Any:
    """
    Create an individual grower
    """
    # 生成验证码
    code = generate_verification_code()
    # 存储验证码
    store_verification_code(grower_data.phone_number, code)
    # 异步发送验证码
    background_tasks.add_task(send_verification_code, grower_data.phone_number, code)

    # 生成临时ID
    temp_id = str(uuid.uuid4())

    # 准备存储到Redis的数据
    redis_data = {
        "form_type": "individual_grower",
        "grower_data": grower_data.model_dump(),
        "files": {
            "id_card_photo": grower_data.id_card_photo,
            "land_ownership_certificate": grower_data.land_ownership_certificate,
            "crop_type_pic": grower_data.crop_type_pic,
        },
    }

    # 将所有数据作为一个JSON字符串存储到Redis
    redis_client.setex(f"pending_form:{temp_id}", 1800, json.dumps(redis_data))

    return ResponseBase(
        message="Individual grower created successfully. Please verify.",
        code=200,
        data={"temp_id": temp_id},
    )


# @router.post("/company", response_model=ResponseBase, summary="创建企业种植主")
# def create_company_grower(
#     background_tasks: BackgroundTasks,
#     session: SessionDep,
#     grower_data: CompanyGrowerCreate,
# ) -> Any:
#     """
#     Create a company grower
#     """
#     # 生成验证码
#     code = generate_verification_code()
#     # 存储验证码
#     store_verification_code(phone_number, code)
#     # 异步发送验证码
#     background_tasks.add_task(send_verification_code, phone_number, code)

#     grower_data = Grower(
#         company_name=company_name,
#         phone_number=phone_number,
#         location_coordinates=location_coordinates,
#         crop_type=crop_type,
#         crop_yield=crop_yield,
#         company_registration_number=company_registration_number,
#         type="company",
#     )

#     # 生成临时ID
#     temp_id = str(uuid.uuid4())

#     # 存储表单类型
#     form_type = "company_grower"
#     redis_client.setex(f"pending_form:{temp_id}:type", 1800, form_type)

#     # 将种植主数据暂时存储在Redis中
#     redis_client.setex(
#         f"pending_form:{temp_id}", 1800, json.dumps(grower_data.model_dump())
#     )

#     # 存储文件路径到Redis（不保存文件）
#     redis_client.set(
#         f"pending_form_files:{temp_id}:business_license_photos",
#         business_license_photos.filename,
#     )
#     if land_ownership_certificate:
#         redis_client.set(
#             f"pending_form_files:{temp_id}:land_ownership_certificate",
#             land_ownership_certificate.filename,
#         )
#     if crop_type_pic:
#         for pic in crop_type_pic:
#             redis_client.rpush(
#                 f"pending_form_files:{temp_id}:crop_type_pic",
#                 pic.filename,
#             )

#     return ResponseBase(
#         message="Company grower created successfully. Please verify.",
#         code=200,
#         data={"temp_id": temp_id},
#     )


# @router.post("/individual", response_model=ResponseBase, summary="创建个人种植主")
# def create_individual_grower(
#     background_tasks: BackgroundTasks,
#     session: SessionDep,
#     name: str = Form(..., description="姓名"),
#     phone_number: str = Form(..., description="联系电话"),
#     location_coordinates: Optional[str] = Form(None, description="地块坐标"),
#     crop_type: str = Form(..., description="种植品种"),
#     crop_yield: Optional[float] = Form(None, description="种植产量"),
#     id_card_number: str = Form(..., description="身份证号", nullable=False),
#     id_card_photo: UploadFile = File(..., description="身份证照片"),
#     land_ownership_certificate: Optional[UploadFile] = File(
#         None, description="土地所有权证书"
#     ),
#     crop_type_pic: Optional[List[UploadFile]] = File(None, description="种植品种图片"),
# ) -> Any:
#     """
#     Create an individual grower
#     """
#     # 生成验证码
#     code = generate_verification_code()
#     # 存储验证码
#     store_verification_code(phone_number, code)
#     # 异步发送验证码
#     background_tasks.add_task(send_verification_code, phone_number, code)

#     grower_data = Grower(
#         name=name,
#         phone_number=phone_number,
#         location_coordinates=location_coordinates,
#         crop_type=crop_type,
#         crop_yield=crop_yield,
#         id_card_number=id_card_number,
#         type="individual",
#     )

#     # 生成临时ID
#     temp_id = str(uuid.uuid4())

#     # 存储表单类型
#     form_type = "individual_grower"
#     redis_client.setex(f"pending_form:{temp_id}:type", 1800, form_type)

#     # 将种植主数据暂时存储在Redis中
#     redis_client.setex(
#         f"pending_form:{temp_id}", 1800, json.dumps(grower_data.model_dump())
#     )

#     # 存储文件路径到Redis（不保存文件）
#     redis_client.set(
#         f"pending_form_files:{temp_id}:id_card_photo",
#         id_card_photo.filename,
#     )
#     if land_ownership_certificate:
#         redis_client.set(
#             f"pending_form_files:{temp_id}:land_ownership_certificate",
#             land_ownership_certificate.filename,
#         )
#     if crop_type_pic:
#         for pic in crop_type_pic:
#             redis_client.rpush(
#                 f"pending_form_files:{temp_id}:crop_type_pic",
#                 pic.filename,
#             )

#     return ResponseBase(
#         message="Individual grower created successfully. Please verify.",
#         code=200,
#         data={"temp_id": temp_id},
#     )


# @router.post("/individual", response_model=ResponseBase, summary="创建个人种植主")
# def create_individual_grower(
#     session: SessionDep,
#     name: str = Form(..., description="姓名"),
#     phone_number: str = Form(..., description="联系电话"),
#     location_coordinates: Optional[str] = Form(None, description="地块坐标"),
#     crop_type: str = Form(..., description="种植品种"),
#     crop_yield: Optional[float] = Form(None, description="种植产量"),
#     id_card_number: str = Form(..., description="身份证号", nullable=False),
#     id_card_photo: UploadFile = File(..., description="身份证照片"),
#     land_ownership_certificate: Optional[UploadFile] = File(
#         None, description="土地所有权证书"
#     ),
#     crop_type_pic: Optional[List[UploadFile]] = File(None, description="种植品种图片"),
# ) -> Any:
#     """
#     Create an individual grower
#     """
#     # First, create the grower record with placeholder values for file paths
#     grower_data = {
#         "name": name,
#         "phone_number": phone_number,
#         "location_coordinates": location_coordinates,
#         "crop_type": crop_type,
#         "crop_yield": crop_yield,
#         "id_card_number": id_card_number,
#         "id_card_photo": "placeholder",
#         "land_ownership_certificate": "placeholder",
#         "crop_type_pic": [],
#         "type": "individual",
#         "qr_code": "placeholder",
#     }

#     grower = Grower(**grower_data)
#     session.add(grower)
#     session.commit()
#     session.refresh(grower)

#     # Now use the actual grower.id to save files
#     id_card_photo_path = save_file(
#         id_card_photo, UPLOAD_DIRECTORY, "idcard", str(grower.id)
#     )
#     land_ownership_certificate_path = save_file(
#         land_ownership_certificate, UPLOAD_DIRECTORY, "land_ownership", str(grower.id)
#     )

#     # Save multiple crop_type_pic files
#     crop_type_pic_paths = []
#     if crop_type_pic:
#         for pic in crop_type_pic:
#             pic_path = save_file(pic, UPLOAD_DIRECTORY, "crop_type_pic", str(grower.id))
#             crop_type_pic_paths.append(pic_path)

#     # Update the grower record with actual file paths
#     grower.id_card_photo = id_card_photo_path
#     grower.land_ownership_certificate = land_ownership_certificate_path
#     grower.crop_type_pic = crop_type_pic_paths

#     # Generate QR code
#     qr_code_content = f"upload/qrcode/{grower.id}".replace("/", ",,")
#     qr_code_filename = generate_qr_code(str(grower.id), QR_CODE_DIRECTORY)

#     # 构造 QR 码的访问路径
#     qr_code_access_path = f"upload/qrcode/{qr_code_filename}".replace("/", ",,")

#     # 更新种植主的二维码字段
#     grower.qr_code = qr_code_access_path

#     session.commit()
#     session.refresh(grower)

#     return ResponseBase(message="Grower created successfully.", code=200, data=grower)


# @router.post("/company", response_model=ResponseBase, summary="创建企业种植主")
# def create_company_grower(
#     session: SessionDep,
#     company_name: str = Form(..., description="企业名称"),
#     phone_number: str = Form(..., description="联系电话"),
#     location_coordinates: Optional[str] = Form(None, description="地块坐标"),
#     crop_type: str = Form(..., description="种植品种"),
#     crop_yield: Optional[float] = Form(None, description="种植产量"),
#     company_registration_number: str = Form(
#         ..., description="营业执照编号", nullable=False
#     ),
#     business_license_photos: UploadFile = File(..., description="营业执照照片"),
#     land_ownership_certificate: Optional[UploadFile] = File(
#         None, description="土地所有权证书"
#     ),
#     crop_type_pic: Optional[List[UploadFile]] = File(None, description="种植品种图片"),
# ) -> Any:
#     """
#     Create a company grower
#     """
#     # First, create the grower record with placeholder values for file paths
#     grower_data = {
#         "company_name": company_name,
#         "phone_number": phone_number,
#         "location_coordinates": location_coordinates,
#         "crop_type": crop_type,
#         "crop_yield": crop_yield,
#         "company_registration_number": company_registration_number,
#         "business_license_photos": "placeholder",
#         "land_ownership_certificate": "placeholder",
#         "crop_type_pic": [],
#         "type": "company",
#         "qr_code": "placeholder",
#     }

#     grower = Grower(**grower_data)
#     session.add(grower)
#     session.commit()
#     session.refresh(grower)

#     # Now use the actual grower.id to save files
#     business_license_photos_path = save_file(
#         business_license_photos, UPLOAD_DIRECTORY, "business_license", str(grower.id)
#     )
#     land_ownership_certificate_path = save_file(
#         land_ownership_certificate, UPLOAD_DIRECTORY, "land_ownership", str(grower.id)
#     )

#     # Save multiple crop_type_pic files
#     crop_type_pic_paths = []
#     if crop_type_pic:
#         for pic in crop_type_pic:
#             pic_path = save_file(pic, UPLOAD_DIRECTORY, "crop_type_pic", str(grower.id))
#             crop_type_pic_paths.append(pic_path)

#     # Update the grower record with actual file paths
#     grower.business_license_photos = business_license_photos_path
#     grower.land_ownership_certificate = land_ownership_certificate_path
#     grower.crop_type_pic = crop_type_pic_paths

#     # Generate QR code
#     qr_code_content = f"upload/qrcode/{grower.id}".replace("/", ",,")
#     qr_code_filename = generate_qr_code(str(grower.id), QR_CODE_DIRECTORY)

#     # 构造 QR 码的访问路径
#     qr_code_access_path = f"upload/qrcode/{qr_code_filename}".replace("/", ",,")

#     # 更新种植主的二维码字段
#     grower.qr_code = qr_code_access_path

#     session.commit()
#     session.refresh(grower)

#     return ResponseBase(
#         message="Company grower created successfully.", code=200, data=grower
#     )


@router.get("/", response_model=ResponseBase[GrowersOut])
def read_growers(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve all growers.
    """
    statement = select(func.count()).select_from(Grower)
    count = session.exec(statement).one()
    statement = select(Grower).offset(skip).limit(limit)
    growers = session.exec(statement).all()

    return ResponseBase(
        message="Growers retrieved successfully",
        code=200,
        data=GrowersOut(data=growers, count=count),
    )


@router.get("/{id}", response_model=ResponseBase[GrowerOut])
def read_grower(session: SessionDep, id: int) -> Any:
    """
    Get grower by ID.
    """
    grower = session.get(Grower, id)
    if not grower:
        return ResponseBase(message="Grower not found", code=404)

    grower_out = model_to_dict(grower, GrowerOut)

    return ResponseBase(
        message="Grower retrieved successfully",
        code=200,
        data=grower_out,
    )
