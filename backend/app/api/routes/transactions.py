import json
from sqlalchemy.orm import joinedload
from typing import Any, List
from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import SessionDep
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
from app.utils import generate_qr_code

router = APIRouter()


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
    middleman_in: MiddlemanCreate,
) -> Any:
    middleman = Middleman.model_validate(middleman_in)
    session.add(middleman)
    session.commit()
    session.refresh(middleman)
    return ResponseBase(message="Middleman created successfully",
                        data=middleman)


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


@router.get("/qr_code/{qr_code}", response_model=ResponseBase[QRCodeInfo])
def get_qr_code_info(
    session: SessionDep,
    qr_code: str,
) -> Any:
    statement = select(Transaction).where(Transaction.qr_code == qr_code)
    transaction = session.exec(statement).first()
    if not transaction:
        return ResponseBase(message="QR code not found", code=404)
    product = transaction.product
    plot = product.plot
    grower = plot.grower
    related_transactions = []
    current_transaction = transaction
    while current_transaction:
        related_transactions.append(current_transaction)
        current_transaction = current_transaction.parent_transaction
    qr_code_info = QRCodeInfo(
        grower=GrowerRead.model_validate(grower),
        plot=PlotRead.model_validate(plot),
        product=ProductRead.model_validate(product),
        transactions=[
            TransactionRead.model_validate(t) for t in related_transactions
        ],
    )
    return ResponseBase(message="QR code info retrieved successfully",
                        data=qr_code_info)
