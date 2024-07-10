import json
from sqlalchemy.orm import joinedload
from typing import Any, List, Dict
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from sqlmodel import select, func
from urllib.parse import urljoin
from fastapi.requests import Request
from app.api.deps import SessionDep
from app.core.config import settings
from app.models import (
    Grower,
    GrowerCreate,
    GrowerRead,
    Middleman,
    MiddlemanCreate,
    MiddlemanRead,
    Plot,
    PlotCreate,
    PlotRead,
    Product,
    ProductCreate,
    ProductRead,
    QRCodeInfo,
    ResponseBase,
    Transaction,
    TransactionCreate,
    TransactionRead,
)
from app.utils import generate_qr_code, decode_qr_code
from app.crud import get_product_by_name, get_product_by_grower_and_name, get_grower_by_id

router = APIRouter()
BASE_URL = f"https://{settings.DOMAIN}"


@router.post("/growers/", response_model=ResponseBase[GrowerRead])
def create_grower(
    session: SessionDep,
    grower_in: GrowerCreate,
) -> Any:
    try:
        grower_data = grower_in.model_dump(exclude={"plots", "products"})
        grower = Grower(**grower_data)
        session.add(grower)
        session.flush()
        if grower_in.plots:
            for plot_data in grower_in.plots:
                plot = Plot(**plot_data.model_dump(), grower_id=grower.id)
                session.add(plot)
                session.flush()
        if grower_in.products:
            for product_data in grower_in.products:
                product = Product(
                    **product_data.model_dump(),
                    grower_id=grower.id,
                    plot_id=plot.id if "plot" in locals() else None,
                    remaining_yield=product_data.total_yield,
                )
                session.add(product)
        session.commit()
        qr_data = json.dumps({"id": grower.id})
        # qr_data = f"Grower ID: {grower.id}, Name: {grower.name or grower.company_name}"
        qr_code_filename = generate_qr_code(qr_data,
                                            prefix="grower",
                                            directory="uploads/grower_qrcodes")
        grower.qr_code = qr_code_filename[1]
        session.commit()
        session.refresh(grower)
        return ResponseBase(message="Grower created successfully", data=grower)
    except Exception as e:
        session.rollback()
        return ResponseBase(message=f"Database error: {str(e)}", code=400)


@router.get("/growers/", response_model=ResponseBase[List[GrowerRead]])
def list_growers(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    statement = select(Grower).offset(skip).limit(limit)
    growers = session.exec(statement).all()
    return ResponseBase(message="Growers retrieved successfully", data=growers)


@router.get("/growers/{grower_id}", response_model=ResponseBase[GrowerRead])
def read_grower(
    session: SessionDep,
    grower_id: int,
) -> Any:
    # 使用 joinedload 预加载 plots 和 products
    query = select(Grower).options(
        joinedload(Grower.plots),
        joinedload(Grower.products)).where(Grower.id == grower_id)

    grower = session.exec(query).first()

    if not grower:
        return ResponseBase(message="Grower not found", code=404)

    # 使用 model_validate 方法创建 GrowerRead 对象
    grower_read = GrowerRead.model_validate(grower)

    return ResponseBase(message="Grower retrieved successfully",
                        data=grower_read)


@router.post("/plots/", response_model=ResponseBase[PlotRead])
def create_plot(
    session: SessionDep,
    plot_in: PlotCreate,
) -> Any:
    plot = Plot.model_validate(plot_in)
    session.add(plot)
    session.commit()
    session.refresh(plot)
    return ResponseBase(message="Plot created successfully", data=plot)


@router.get("/plots/{plot_id}", response_model=ResponseBase[PlotRead])
def read_plot(
    session: SessionDep,
    plot_id: int,
) -> Any:
    plot = session.get(Plot, plot_id)
    if not plot:
        return ResponseBase(message="Plot not found", code=404)
    return ResponseBase(message="Plot retrieved successfully", data=plot)


@router.post("/products/", response_model=ResponseBase[ProductRead])
def create_product(
    session: SessionDep,
    product_in: ProductCreate,
) -> Any:
    product = Product.model_validate(
        product_in, update={"remaining_yield": product_in.total_yield})
    session.add(product)
    session.commit()
    session.refresh(product)
    return ResponseBase(message="Product created successfully", data=product)


@router.get("/products/{product_id}", response_model=ResponseBase[ProductRead])
def read_product(
    session: SessionDep,
    product_id: int,
) -> Any:
    product = session.get(Product, product_id)
    if not product:
        return ResponseBase(message="Product not found", code=404)
    return ResponseBase(message="Product retrieved successfully", data=product)


@router.post("/middlemen/", response_model=ResponseBase[MiddlemanRead])
def create_middleman(
    session: SessionDep,
    middleman: MiddlemanCreate,
) -> Any:
    try:
        with session.begin():
            # 数据验证
            if middleman.purchased_quantity <= 0:
                raise ValueError("Purchased quantity must be positive")

            db_middleman = Middleman(**middleman.model_dump(
                exclude={"split_quantities", "transaction_contract_images"}))

            db_middleman.split_quantities = middleman.split_quantities or [
                middleman.purchased_quantity
            ]
            db_middleman.split_qr_codes = []
            db_middleman.transaction_contract_images = middleman.transaction_contract_images or []

            # 确保拆分数量的总和等于购买数量
            if sum(db_middleman.split_quantities
                   ) != db_middleman.purchased_quantity:
                raise ValueError(
                    "Sum of split quantities must equal purchased quantity")

            # 处理购买来源
            if db_middleman.purchase_from_type == "grower":
                handle_purchase_from_grower(session, db_middleman)
            elif db_middleman.purchase_from_type == "middleman":
                handle_purchase_from_middleman(session, db_middleman)
            else:
                raise ValueError("Invalid purchase_from_type")

            db_middleman.remaining_quantity = db_middleman.purchased_quantity
            session.add(db_middleman)
            session.flush()

            # 生成QR码
            qr_codes = generate_split_qr_codes(db_middleman)
            main_qr_code = generate_main_qr_code(db_middleman)

            db_middleman.qr_code = main_qr_code

        session.refresh(db_middleman)

        response_data = db_middleman.dict()
        response_data["qr_codes"] = qr_codes
        response_data["main_qr_code"] = main_qr_code

        return ResponseBase(
            message="Middleman transaction created successfully",
            data=response_data)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"An error occurred: {str(e)}")


def handle_purchase_from_grower(session: SessionDep, db_middleman: Middleman):
    grower = session.get(Grower, db_middleman.purchase_from_id)
    if not grower:
        raise ValueError("Grower not found")

    product = session.exec(
        select(Product).where(
            Product.grower_id == grower.id,
            Product.name == db_middleman.purchased_product)).first()
    if not product:
        raise ValueError("Product not found for this grower")

    if product.remaining_yield < db_middleman.purchased_quantity:
        raise ValueError("Insufficient remaining yield from grower")

    product.remaining_yield -= db_middleman.purchased_quantity


def handle_purchase_from_middleman(session: SessionDep,
                                   db_middleman: Middleman):
    seller_middleman = session.get(Middleman, db_middleman.purchase_from_id)
    if not seller_middleman:
        raise ValueError("Seller middleman not found")

    total_remaining = sum(seller_middleman.split_quantities)
    if total_remaining < db_middleman.purchased_quantity:
        raise ValueError("Insufficient quantity from seller middleman")

    remaining_to_deduct = db_middleman.purchased_quantity
    seller_middleman.split_quantities = [
        max(0, qty - (remaining_to_deduct if remaining_to_deduct > 0 else 0))
        for qty in seller_middleman.split_quantities
    ]
    seller_middleman.split_qr_codes = seller_middleman.split_qr_codes[:len(
        seller_middleman.split_quantities)]


def generate_split_qr_codes(db_middleman: Middleman) -> List[str]:
    qr_codes = []
    for i, quantity in enumerate(db_middleman.split_quantities):
        qr_data = {"middleman_id": db_middleman.id, "split_index": i}
        qr_url = urljoin(BASE_URL, "/api/middleman/split-info")

        qr_code_filename = generate_qr_code(
            json.dumps({
                "url": qr_url,
                "data": qr_data
            }),
            prefix=f"middleman_{db_middleman.id}_split_{i}",
            directory="uploads/middleman_qrcodes")
        db_middleman.split_qr_codes.append(qr_code_filename[1])
        qr_codes.append(qr_code_filename[1])
    return qr_codes


def generate_main_qr_code(db_middleman: Middleman) -> str:
    qr_data = {"middleman_id": db_middleman.id}
    qr_url = urljoin(BASE_URL, "/api/middleman/info")

    main_qr_code_filename = generate_qr_code(
        json.dumps({
            "url": qr_url,
            "data": qr_data
        }),
        prefix=f"middleman_{db_middleman.id}_main",
        directory="uploads/middleman_qrcodes")
    return main_qr_code_filename[1]


class MiddlemanInfoRequest(BaseModel):
    middleman_id: int


class MiddlemanSplitInfoRequest(BaseModel):
    middleman_id: int
    split_index: int


class MiddlemanInfo(BaseModel):
    middleman_id: int
    quantity: int
    product: str
    source: str
    purchase_from_id: int
    purchase_from_type: str


class MiddlemanInfoOut(BaseModel):
    data: MiddlemanInfo
    count: int


class MiddlemanSplitInfo(BaseModel):
    middleman_id: int
    split_index: int
    quantity: int
    product: str
    source: str
    purchase_from_id: int
    purchase_from_type: str


class MiddlemanSplitInfoOut(BaseModel):
    data: MiddlemanSplitInfo
    count: int


@router.post("/api/middleman/info", response_model=MiddlemanInfoOut)
def get_middleman_info(request: MiddlemanInfoRequest,
                       session: SessionDep) -> Any:
    count_stmt = select(func.count()).select_from(Middleman).where(
        Middleman.id == request.middleman_id)
    count = session.exec(count_stmt).one()

    stmt = select(Middleman).where(Middleman.id == request.middleman_id)
    middleman = session.exec(stmt).first()

    if not middleman:
        raise HTTPException(status_code=404, detail="Middleman not found")

    data = MiddlemanInfo(middleman_id=middleman.id,
                         quantity=middleman.purchased_quantity,
                         product=middleman.purchased_product,
                         source="middleman",
                         purchase_from_id=middleman.purchase_from_id,
                         purchase_from_type=middleman.purchase_from_type)

    return MiddlemanInfoOut(data=data, count=count)


@router.post("/api/middleman/split-info", response_model=MiddlemanSplitInfoOut)
def get_middleman_split_info(request: MiddlemanSplitInfoRequest,
                             session: SessionDep) -> Any:
    count_stmt = select(func.count()).select_from(Middleman).where(
        Middleman.id == request.middleman_id)
    count = session.exec(count_stmt).one()

    stmt = select(Middleman).where(Middleman.id == request.middleman_id)
    middleman = session.exec(stmt).first()

    if not middleman:
        raise HTTPException(status_code=404, detail="Middleman not found")
    if request.split_index >= len(middleman.split_quantities):
        raise HTTPException(status_code=404, detail="Split index out of range")

    data = MiddlemanSplitInfo(
        middleman_id=middleman.id,
        split_index=request.split_index,
        quantity=middleman.split_quantities[request.split_index],
        product=middleman.purchased_product,
        source="middleman",
        purchase_from_id=middleman.purchase_from_id,
        purchase_from_type=middleman.purchase_from_type)

    return MiddlemanSplitInfoOut(data=data, count=count)


# def generate_split_qr_codes(db_middleman: Middleman) -> List[str]:
#     qr_codes = []
#     for i, quantity in enumerate(db_middleman.split_quantities):
#         qr_data = json.dumps({
#             "middleman_id":
#             db_middleman.id,
#             "split_index":
#             i,
#             "quantity":
#             quantity,
#             "product":
#             db_middleman.purchased_product,
#             "source":
#             "middleman",
#             "purchase_from_id":
#             db_middleman.purchase_from_id,
#             "purchase_from_type":
#             db_middleman.purchase_from_type
#         })
#         qr_code_filename = generate_qr_code(
#             qr_data,
#             prefix=f"middleman_{db_middleman.id}_split_{i}",
#             directory="uploads/middleman_qrcodes")
#         db_middleman.split_qr_codes.append(qr_code_filename[1])
#         qr_codes.append(qr_code_filename[1])
#     return qr_codes

# def generate_main_qr_code(db_middleman: Middleman) -> str:
#     main_qr_data = json.dumps({
#         "middleman_id":
#         db_middleman.id,
#         "quantity":
#         db_middleman.purchased_quantity,
#         "product":
#         db_middleman.purchased_product,
#         "source":
#         "middleman",
#         "purchase_from_id":
#         db_middleman.purchase_from_id,
#         "purchase_from_type":
#         db_middleman.purchase_from_type
#     })
#     main_qr_code_filename = generate_qr_code(
#         main_qr_data,
#         prefix=f"middleman_{db_middleman.id}_main",
#         directory="uploads/middleman_qrcodes")
#     return main_qr_code_filename[1]

# @router.post("/middlemen/", response_model=ResponseBase[MiddlemanRead])
# def create_middleman(
#     session: SessionDep,
#     middleman: MiddlemanCreate,
# ) -> Any:
#     try:
#         with session.begin():
#             db_middleman = Middleman(**middleman.model_dump(
#                 exclude={"split_quantities", "transaction_contract_images"}))

#             db_middleman.split_quantities = middleman.split_quantities or [
#                 middleman.purchased_quantity
#             ]
#             db_middleman.split_qr_codes = []
#             db_middleman.transaction_contract_images = middleman.transaction_contract_images or []

#             # 确保拆分数量的总和等于购买数量
#             if sum(db_middleman.split_quantities
#                    ) != db_middleman.purchased_quantity:
#                 raise ValueError(
#                     "Sum of split quantities must equal purchased quantity")

#             if db_middleman.purchase_from_type == "grower":
#                 grower = session.get(Grower, db_middleman.purchase_from_id)
#                 if not grower:
#                     raise ValueError("Grower not found")

#                 product = session.exec(
#                     select(Product).where(
#                         Product.grower_id == grower.id, Product.name ==
#                         db_middleman.purchased_product)).first()
#                 if not product:
#                     raise ValueError("Product not found for this grower")

#                 if product.remaining_yield < db_middleman.purchased_quantity:
#                     raise ValueError(
#                         "Insufficient remaining yield from grower")

#                 product.remaining_yield -= db_middleman.purchased_quantity

#             elif db_middleman.purchase_from_type == "middleman":
#                 seller_middleman = session.get(Middleman,
#                                                db_middleman.purchase_from_id)
#                 if not seller_middleman:
#                     raise ValueError("Seller middleman not found")

#                 total_remaining = sum(seller_middleman.split_quantities)
#                 if total_remaining < db_middleman.purchased_quantity:
#                     raise ValueError(
#                         "Insufficient quantity from seller middleman")

#                 remaining_to_deduct = db_middleman.purchased_quantity
#                 for i, qty in enumerate(seller_middleman.split_quantities):
#                     if qty >= remaining_to_deduct:
#                         seller_middleman.split_quantities[
#                             i] -= remaining_to_deduct
#                         break
#                     else:
#                         remaining_to_deduct -= qty
#                         seller_middleman.split_quantities[i] = 0

#                 seller_middleman.split_quantities = [
#                     qty for qty in seller_middleman.split_quantities if qty > 0
#                 ]
#                 seller_middleman.split_qr_codes = seller_middleman.split_qr_codes[:len(
#                     seller_middleman.split_quantities)]

#             db_middleman.remaining_quantity = db_middleman.purchased_quantity
#             session.add(db_middleman)
#             session.flush()

#             qr_codes = []
#             for i, quantity in enumerate(db_middleman.split_quantities):
#                 qr_data = json.dumps({
#                     "middleman_id":
#                     db_middleman.id,
#                     "split_index":
#                     i,
#                     "quantity":
#                     quantity,
#                     "product":
#                     db_middleman.purchased_product,
#                     "source":
#                     "middleman",
#                     "purchase_type":
#                     db_middleman.purchase_type,
#                     "purchase_from_id":
#                     db_middleman.purchase_from_id,
#                     "purchase_from_middleman_id":
#                     db_middleman.purchase_from_middleman_id
#                 })
#                 qr_code_filename = generate_qr_code(
#                     qr_data,
#                     prefix=f"middleman_{db_middleman.id}_split_{i}",
#                     directory="uploads/middleman_qrcodes")
#                 db_middleman.split_qr_codes.append(qr_code_filename[1])
#                 qr_codes.append(qr_code_filename[1])

#             main_qr_data = json.dumps({
#                 "middleman_id":
#                 db_middleman.id,
#                 "quantity":
#                 db_middleman.purchased_quantity,
#                 "product":
#                 db_middleman.purchased_product,
#                 "source":
#                 "middleman",
#                 "purchase_type":
#                 db_middleman.purchase_type,
#                 "purchase_from_id":
#                 db_middleman.purchase_from_id,
#                 "purchase_from_middleman_id":
#                 db_middleman.purchase_from_middleman_id
#             })
#             main_qr_code_filename = generate_qr_code(
#                 main_qr_data,
#                 prefix=f"middleman_{db_middleman.id}_main",
#                 directory="uploads/middleman_qrcodes")
#             db_middleman.qr_code = main_qr_code_filename[1]
#             main_qr_code = main_qr_code_filename[1]

#         session.refresh(db_middleman)

#         response_data = db_middleman.dict()
#         response_data["qr_codes"] = qr_codes
#         response_data["main_qr_code"] = main_qr_code

#         return ResponseBase(
#             message="Middleman transaction created successfully",
#             data=response_data)
#     except ValueError as ve:
#         return ResponseBase(message=str(ve), code=400)
#     except Exception as e:
#         return ResponseBase(message=f"An error occurred: {str(e)}", code=500)

# @router.post("/middlemen/", response_model=ResponseBase[MiddlemanRead])
# def create_middleman(
#     session: SessionDep,
#     middleman: MiddlemanCreate,
# ) -> Any:
#     db_middleman = Middleman(**middleman.model_dump(
#         exclude={"split_quantities"}))

#     db_middleman.split_quantities = middleman.split_quantities or [
#         middleman.purchased_quantity
#     ]
#     db_middleman.split_qr_codes = []

#     if db_middleman.purchase_source == "grower":
#         # 首先，根据产品名称找到对应的种植者
#         product = get_product_by_name(
#             session=session, product_name=db_middleman.purchased_product)
#         if not product:
#             return ResponseBase(message="Product not found", code=404)

#         grower = get_grower_by_id(session=session, grower_id=product.grower_id)
#         if not grower:
#             return ResponseBase(message="Grower not found", code=404)

#         if product.remaining_yield < db_middleman.purchased_quantity:
#             return ResponseBase(
#                 message="Insufficient remaining yield from grower", code=400)

#         product.remaining_yield -= db_middleman.purchased_quantity

#     session.add(db_middleman)
#     session.commit()
#     session.refresh(db_middleman)

#     qr_codes = []
#     for i, quantity in enumerate(db_middleman.split_quantities):
#         qr_data = json.dumps({
#             "middleman_id": db_middleman.id,
#             "split_index": i,
#             "quantity": quantity,
#             "product": db_middleman.purchased_product,
#             "source": "middleman",
#             "purchase_type": db_middleman.purchase_type,
#             "purchase_from_id": db_middleman.purchase_from_id
#         })
#         qr_code_filename = generate_qr_code(
#             qr_data,
#             prefix=f"middleman_{db_middleman.id}_split_{i}",
#             directory="uploads/middleman_qrcodes")
#         db_middleman.split_qr_codes.append(qr_code_filename[1])
#         qr_codes.append(qr_code_filename[1])

#     # 创建主 QR 码，无论购买类型如何
#     main_qr_data = json.dumps({
#         "middleman_id": db_middleman.id,
#         "quantity": db_middleman.purchased_quantity,
#         "product": db_middleman.purchased_product,
#         "source": "middleman",
#         "purchase_type": db_middleman.purchase_type,
#         "purchase_from_id": db_middleman.purchase_from_id
#     })
#     main_qr_code_filename = generate_qr_code(
#         main_qr_data,
#         prefix=f"middleman_{db_middleman.id}_main",
#         directory="uploads/middleman_qrcodes")
#     db_middleman.qr_code = main_qr_code_filename[1]
#     main_qr_code = f"/uploads/middleman_qrcodes/{main_qr_code_filename[1]}"

#     session.commit()
#     session.refresh(db_middleman)

#     response_data = db_middleman.dict()
#     response_data["qr_codes"] = qr_codes
#     response_data["main_qr_code"] = main_qr_code

#     return ResponseBase(message="Middleman created successfully",
#                         data=response_data)

# @router.post("/middlemen/transaction/",
#              response_model=ResponseBase[MiddlemanRead])
# def create_middleman_transaction(
#     session: SessionDep,
#     seller_id: int,
#     buyer_id: int,
#     quantity: float,
#     split_index: int,
# ) -> Any:
#     seller = session.get(Middleman, seller_id)
#     buyer = session.get(Middleman, buyer_id)
#     if not seller or not buyer:
#         return ResponseBase(message="Seller or buyer not found", code=404)
#     if split_index >= len(seller.split_quantities
#                           ) or seller.split_quantities[split_index] < quantity:
#         return ResponseBase(
#             message="Invalid split index or insufficient quantity", code=400)

#     seller.split_quantities[split_index] -= quantity
#     buyer_split_index = len(buyer.split_quantities)
#     buyer.split_quantities.append(quantity)

#     qr_data = json.dumps({
#         "middleman_id": buyer.id,
#         "split_index": buyer_split_index,
#         "quantity": quantity,
#         # "product": seller.purchase_type,
#         "source": "middleman",
#         "original_middleman_id": seller.id,
#         "original_split_index": split_index
#     })
#     qr_code_filename = generate_qr_code(
#         qr_data,
#         prefix=f"middleman_{buyer.id}_split_{buyer_split_index}",
#         directory="uploads/middleman_qrcodes")
#     buyer.split_qr_codes.append(qr_code_filename[1])

#     session.commit()
#     session.refresh(buyer)
#     return ResponseBase(message="Middleman transaction created successfully",
#                         data=buyer)

# @router.post("/middlemen/repackage/",
#              response_model=ResponseBase[MiddlemanRead])
# def repackage_middleman_product(
#     session: SessionDep,
#     middleman_id: int,
#     new_split_quantities: List[float],
# ) -> Any:
#     middleman = session.get(Middleman, middleman_id)
#     if not middleman:
#         return ResponseBase(message="Middleman not found", code=404)

#     total_quantity = sum(middleman.split_quantities)
#     if sum(new_split_quantities) != total_quantity:
#         return ResponseBase(
#             message="New split quantities do not match total quantity",
#             code=400)

#     new_split_qr_codes = []
#     for i, quantity in enumerate(new_split_quantities):
#         qr_data = json.dumps({
#             "middleman_id": middleman.id,
#             "split_index": i,
#             "quantity": quantity,
#             # "product": middleman.purchase_type,
#             "source": "middleman",
#             "original_split": middleman.split_quantities,
#             "original_qr_codes": middleman.split_qr_codes
#         })
#         qr_code_filename = generate_qr_code(
#             qr_data,
#             prefix=f"middleman_{middleman.id}_resplit_{i}",
#             directory="uploads/middleman_qrcodes")
#         new_split_qr_codes.append(qr_code_filename[1])

#     middleman.original_split = middleman.split_quantities
#     middleman.original_qr_codes = middleman.split_qr_codes
#     middleman.split_quantities = new_split_quantities
#     middleman.split_qr_codes = new_split_qr_codes

#     session.commit()
#     session.refresh(middleman)
#     return ResponseBase(message="Middleman product repackaged successfully",
#                         data=middleman)


@router.get("/middlemen/", response_model=ResponseBase[List[MiddlemanRead]])
def list_middlemen(session: SessionDep,
                   skip: int = 0,
                   limit: int = 100) -> Any:
    statement = select(Middleman).offset(skip).limit(limit)
    middlemen = session.exec(statement).all()
    return ResponseBase(message="Middlemen retrieved successfully",
                        data=middlemen)


@router.get("/middlemen/{middleman_id}",
            response_model=ResponseBase[MiddlemanRead])
def read_middleman(
    session: SessionDep,
    middleman_id: int,
) -> Any:
    middleman = session.get(Middleman, middleman_id)
    if not middleman:
        return ResponseBase(message="Middleman not found", code=404)
    return ResponseBase(message="Middleman retrieved successfully",
                        data=middleman)


@router.post("/transactions/", response_model=ResponseBase[TransactionRead])
def create_transaction(
    session: SessionDep,
    transaction_in: TransactionCreate,
) -> Any:
    product = session.get(Product, transaction_in.product_id)
    if not product:
        return ResponseBase(message="Product not found", code=404)
    if product.remaining_yield < transaction_in.quantity:
        return ResponseBase(message="Insufficient remaining yield", code=400)
    transaction = Transaction.model_validate(transaction_in)
    qr_data = f"Transaction ID: {transaction.id}, Product: {product.name}, Quantity: {transaction.quantity}"
    qr_code_filename = generate_qr_code(
        qr_data, prefix="transaction", directory="uploads/transaction_qrcodes")
    transaction.qr_code = qr_code_filename
    session.add(transaction)
    product.remaining_yield -= transaction_in.quantity
    session.commit()
    session.refresh(transaction)
    return ResponseBase(message="Transaction created successfully",
                        data=transaction)


@router.get("/transactions/{transaction_id}",
            response_model=ResponseBase[TransactionRead])
def read_transaction(
    session: SessionDep,
    transaction_id: int,
) -> Any:
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        return ResponseBase(message="Transaction not found", code=404)
    return ResponseBase(message="Transaction retrieved successfully",
                        data=transaction)


@router.get("/qr_code/{qr_code}", response_model=ResponseBase[Dict])
def get_qr_code_info(
    session: SessionDep,
    qr_code: str,
) -> Any:
    qr_code_data = json.loads(decode_qr_code(qr_code))
    source_type = qr_code_data.get("source")

    if source_type == "grower":
        # 现有的种植者逻辑
        ...
    elif source_type == "middleman":
        middleman = session.get(Middleman, qr_code_data["middleman_id"])
        if not middleman:
            return ResponseBase(message="Middleman not found", code=404)

        trace_data = trace_middleman_chain(session, qr_code_data)

        return ResponseBase(message="QR code info retrieved successfully",
                            data={
                                "source_type": "middleman",
                                "middleman_info": {
                                    "id": middleman.id,
                                    "name": middleman.name,
                                    "product": qr_code_data["product"],
                                    "quantity": qr_code_data["quantity"]
                                },
                                "trace_data": trace_data
                            })
    else:
        return ResponseBase(message="Invalid QR code data", code=400)


def trace_middleman_chain(session: SessionDep,
                          qr_code_data: Dict) -> List[Dict]:
    trace = []
    current_data = qr_code_data

    while "original_middleman_id" in current_data:
        original_middleman = session.get(Middleman,
                                         current_data["original_middleman_id"])
        if not original_middleman:
            break

        trace.append({
            "id":
            original_middleman.id,
            "name":
            original_middleman.name,
            "quantity":
            original_middleman.split_quantities[
                current_data["original_split_index"]],
            "product":
            original_middleman.purchase_type
        })

        if original_middleman.purchase_from_id:
            grower = session.get(Grower, original_middleman.purchase_from_id)
            if grower:
                trace.append({
                    "source_type": "grower",
                    "id": grower.id,
                    "name": grower.name,
                    "product": original_middleman.purchase_type,
                    "quantity":
                    original_middleman.split_quantities[0]  # 假设从种植者处购买的是第一个批次
                })
            break
        else:
            current_data = json.loads(
                decode_qr_code(original_middleman.split_qr_codes[0]))

    return trace


# @router.get("/qr_code/{qr_code}", response_model=ResponseBase[QRCodeInfo])
# def get_qr_code_info(
#     session: SessionDep,
#     qr_code: str,
# ) -> Any:
#     statement = select(Transaction).where(Transaction.qr_code == qr_code)
#     transaction = session.exec(statement).first()
#     if not transaction:
#         return ResponseBase(message="QR code not found", code=404)
#     product = transaction.product
#     plot = product.plot
#     grower = plot.grower
#     related_transactions = []
#     current_transaction = transaction
#     while current_transaction:
#         related_transactions.append(current_transaction)
#         current_transaction = current_transaction.parent_transaction
#     qr_code_info = QRCodeInfo(
#         grower=GrowerRead.model_validate(grower),
#         plot=PlotRead.model_validate(plot),
#         product=ProductRead.model_validate(product),
#         transactions=[
#             TransactionRead.model_validate(t) for t in related_transactions
#         ],
#     )
#     return ResponseBase(message="QR code info retrieved successfully",
#                         data=qr_code_info)
