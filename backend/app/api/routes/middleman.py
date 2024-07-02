import os
import uuid
import json
from typing import Any, Optional, List
from pydantic import TypeAdapter
import logging

from fastapi import APIRouter, HTTPException, Form, UploadFile, File, BackgroundTasks
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Middleman,
    MiddlemanOut,
    MiddlemansOut,
    MiddlemanCreate,
    ResponseBase,
)

from app.core.config import UPLOAD_DIRECTORY, QR_CODE_DIRECTORY
from app.core.redis_conf import redis_client
from app.utils import (
    save_file,
    generate_qr_code,
    generate_verification_code,
    send_verification_code,
    store_verification_code,
    verify_code,
)


router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@router.post("/company", response_model=ResponseBase, summary="创建企业中间商")
def create_company_middleman(
    background_tasks: BackgroundTasks,
    Session: SessionDep,
    company_name: str = Form(..., description="企业名称"),
    phone_number: str = Form(..., description="联系电话"),
    location_coordinates: Optional[str] = Form(None, description="地理坐标"),
    purchase_type: str = Form(..., description="购买品种"),
    transaction_volume: Optional[str] = Form(None, description="交易量"),
    purchase_from_grower_id: Optional[int] = Form(None, description="种植主ID"),
    purchase_from_middleman_id: Optional[int] = Form(None, description="上游中间商ID"),
    business_license_number: str = Form(
        ..., description="营业执照编号", nullable=False
    ),
    business_license_photo: UploadFile = File(..., description="营业执照照片"),
    transaction_contracts: Optional[List[UploadFile]] = File(
        None, description="交易合同"
    ),
) -> Any:
    """
    Create a company middleman
    """
    # 生成验证码
    code = generate_verification_code()
    logger.info(f"Generated verification code: {code}")
    # 存储验证码
    store_verification_code(phone_number, code)
    # 异步发送验证码
    background_tasks.add_task(send_verification_code, phone_number, code)

    middleman_data = MiddlemanCreate(
        name=company_name,
        phone_number=phone_number,
        location_coordinates=location_coordinates,
        purchase_type=purchase_type,
        transaction_volume=transaction_volume,
        purchase_from_id=purchase_from_grower_id,
        purchase_from_middleman_id=purchase_from_middleman_id,
        company_name=company_name,
        business_license_number=business_license_number,
        type="corporate",
    )

    # 生成临时ID
    temp_id = str(uuid.uuid4())

    # 存储表单类型
    form_type = "company_middleman"
    redis_client.setex(f"pending_form:{temp_id}:type", 1800, form_type)

    # 将中间商数据暂时存储在Redis中
    redis_client.setex(
        f"pending_middleman:{temp_id}", 1800, json.dumps(middleman_data.model_dump())
    )

    # 存储文件路径到Redis（不保存文件）
    redis_client.set(
        f"pending_middleman_files:{temp_id}:business_license_photo",
        business_license_photo.filename,
    )
    if transaction_contracts:
        for contract in transaction_contracts:
            redis_client.rpush(
                f"pending_middleman_files:{temp_id}:transaction_contracts",
                contract.filename,
            )

    return ResponseBase(
        message="Company middleman created successfully. Please verify.",
        code=200,
        data={"temp_id": temp_id},
    )


# @router.post("/verify", response_model=ResponseBase)
# async def verify_middleman(
#     background_tasks: BackgroundTasks,
#     session: SessionDep,
#     temp_id: str = Form(...),
#     verification_code: str = Form(...),
# ):
#     # 从Redis获取待验证的中间商数据
#     pending_data = redis_client.get(f"pending_middleman:{temp_id}")
#     if not pending_data:
#         raise HTTPException(status_code=400, detail="Invalid or expired temporary ID")

#     middleman_data = MiddlemanCreate.parse_raw(pending_data)

#     # 验证码检查
#     if not verify_code(middleman_data.phone_number, verification_code):
#         raise HTTPException(status_code=400, detail="Invalid verification code")

#     # 验证通过,创建中间商
#     middleman = Middleman(**middleman_data.dict())
#     session.add(middleman)
#     session.commit()
#     session.refresh(middleman)

#     # 获取文件名
#     business_license_photo_filename = redis_client.get(
#         f"pending_middleman_files:{temp_id}:business_license_photo"
#     )
#     transaction_contract_filenames = redis_client.lrange(
#         f"pending_middleman_files:{temp_id}:transaction_contracts", 0, -1
#     )

#     # 更新文件路径
#     if business_license_photo_filename:
#         middleman.business_license_photo = os.path.join(
#             UPLOAD_DIRECTORY,
#             "business_license",
#             str(middleman.id),
#             business_license_photo_filename.decode(),
#         )

#     transaction_contract_paths = []
#     if transaction_contract_filenames:
#         for filename in transaction_contract_filenames:
#             path = os.path.join(
#                 UPLOAD_DIRECTORY,
#                 "transaction_contract",
#                 str(middleman.id),
#                 filename.decode(),
#             )
#             transaction_contract_paths.append(path)
#     middleman.transaction_contracts = transaction_contract_paths

#     # 生成二维码
#     qr_code_filename = generate_qr_code(str(middleman.id), QR_CODE_DIRECTORY)
#     qr_code_access_path = f"upload/qrcode/{qr_code_filename}".replace("/", ",,")
#     middleman.qr_code = qr_code_access_path

#     session.commit()
#     session.refresh(middleman)

#     # 删除临时数据
#     redis_client.delete(f"pending_middleman:{temp_id}")
#     redis_client.delete(f"pending_middleman_files:{temp_id}:business_license_photo")
#     redis_client.delete(f"pending_middleman_files:{temp_id}:transaction_contracts")

#     return ResponseBase(
#         message="Company middleman verified and created successfully",
#         code=200,
#         data=middleman,
#     )


@router.post("/individual", response_model=ResponseBase, summary="创建个人中间商")
def create_individual_middleman(
    session: SessionDep,
    name: str = Form(..., description="姓名"),
    phone_number: str = Form(..., description="联系电话"),
    location_coordinates: Optional[str] = Form(None, description="地理坐标"),
    purchase_type: str = Form(..., description="购买品种"),
    transaction_volume: Optional[float] = Form(None, description="交易量"),
    purchase_from_id: Optional[int] = Form(None, description="种植主ID"),
    sale_to_id: Optional[int] = Form(None, description="交易商ID"),
    id_card_number: str = Form(..., description="身份证号", nullable=False),
    id_card_photo: UploadFile = File(..., description="身份证照片"),
    transaction_contracts: Optional[List[UploadFile]] = File(
        None, description="交易合同"
    ),
) -> Any:
    """
    Create an individual middleman
    """
    middleman_data = MiddlemanCreate(
        name=name,
        phone_number=phone_number,
        location_coordinates=location_coordinates,
        purchase_type=purchase_type,
        transaction_volume=transaction_volume,
        purchase_from_id=purchase_from_id,
        sale_to_id=sale_to_id,
        id_card_number=id_card_number,
        type="individual",
    )

    middleman = Middleman(**middleman_data.model_dump())
    session.add(middleman)
    session.commit()
    session.refresh(middleman)

    id_card_photo_path = save_file(
        id_card_photo, UPLOAD_DIRECTORY, "idcard", str(middleman.id)
    )

    transaction_contract_paths = []
    if transaction_contracts:
        for contract in transaction_contracts:
            contract_path = save_file(
                contract, UPLOAD_DIRECTORY, "transaction_contract", str(middleman.id)
            )
            transaction_contract_paths.append(contract_path)

    middleman.id_card_photo = id_card_photo_path
    middleman.transaction_contracts = transaction_contract_paths

    qr_code_filename = generate_qr_code(str(middleman.id), QR_CODE_DIRECTORY)
    qr_code_access_path = f"upload/qrcode/{qr_code_filename}".replace("/", ",,")
    middleman.qr_code = qr_code_access_path

    session.commit()
    session.refresh(middleman)

    return ResponseBase(
        message="Individual middleman created successfully.", code=200, data=middleman
    )


@router.get("/", response_model=ResponseBase[MiddlemansOut])
def read_middlemen(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve all middlemen.
    """
    statement = select(func.count()).select_from(Middleman)
    count = session.exec(statement).one()
    statement = select(Middleman).offset(skip).limit(limit)
    middlemen = session.exec(statement).all()

    return ResponseBase(
        message="Middlemen retrieved successfully",
        code=200,
        data=MiddlemansOut(data=middlemen, count=count),
    )


@router.get("/{id}", response_model=ResponseBase[MiddlemanOut])
def read_middleman(session: SessionDep, id: int) -> Any:
    """
    Get middleman by ID.
    """
    middleman = session.get(Middleman, id)
    if not middleman:
        return ResponseBase(message="Middleman not found", code=404)

    # 使用 TypeAdapter 替代 from_orm
    middleman_out = TypeAdapter(MiddlemanOut).validate_python(middleman)

    return ResponseBase(
        message="Middleman retrieved successfully",
        code=200,
        data=middleman_out,
    )
