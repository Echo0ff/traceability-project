from typing import Any, Optional, List
from pydantic import TypeAdapter

from fastapi import APIRouter, HTTPException, Form, UploadFile, File
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
from app.utils import save_file, generate_qr_code


router = APIRouter()


@router.post("/company", response_model=ResponseBase, summary="创建企业中间商")
def create_company_middleman(
    session: SessionDep,
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

    middleman = Middleman(**middleman_data.dict())
    session.add(middleman)
    session.commit()
    session.refresh(middleman)

    business_license_photo_path = save_file(
        business_license_photo, UPLOAD_DIRECTORY, "business_license", str(middleman.id)
    )

    transaction_contract_paths = []
    if transaction_contracts:
        for contract in transaction_contracts:
            contract_path = save_file(
                contract, UPLOAD_DIRECTORY, "transaction_contract", str(middleman.id)
            )
            transaction_contract_paths.append(contract_path)

    middleman.business_license_photo = business_license_photo_path
    middleman.transaction_contracts = transaction_contract_paths

    qr_code_filename = generate_qr_code(str(middleman.id), QR_CODE_DIRECTORY)
    qr_code_access_path = f"upload/qrcode/{qr_code_filename}".replace("/", ",,")
    middleman.qr_code = qr_code_access_path

    session.commit()
    session.refresh(middleman)

    return ResponseBase(
        message="Company middleman created successfully.", code=200, data=middleman
    )


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
