from typing import Any

from fastapi import APIRouter, HTTPException
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


@router.post("/growers/", response_model=ResponseBase)
def create_grower(
    session: SessionDep,
    grower_in: GrowerCreate,
) -> Any:
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
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400,
                            detail=f"Database error: {str(e)}")
    qr_data = f"Grower ID: {grower.id}, Name: {grower.name or grower.company_name}"
    qr_code_filename = generate_qr_code(qr_data,
                                        prefix="grower",
                                        directory="uploads/grower_qrcodes")
    grower.qr_code = qr_code_filename[1]
    session.commit()
    session.refresh(grower)
    return ResponseBase(message="Grower created successfully", data=grower)


@router.get("/growers/{grower_id}", response_model=GrowerRead)
def read_grower(
    session: SessionDep,
    grower_id: int,
) -> Any:
    grower = session.get(Grower, grower_id)
    if not grower:
        raise HTTPException(status_code=404, detail="Grower not found")
    return grower


@router.post("/plots/", response_model=PlotRead)
def create_plot(
    session: SessionDep,
    plot_in: PlotCreate,
) -> Any:
    plot = Plot.model_validate(plot_in)
    session.add(plot)
    session.commit()
    session.refresh(plot)
    return plot


@router.get("/plots/{plot_id}", response_model=PlotRead)
def read_plot(
    session: SessionDep,
    plot_id: int,
) -> Any:
    plot = session.get(Plot, plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail="Plot not found")
    return plot


@router.post("/products/", response_model=ProductRead)
def create_product(
    session: SessionDep,
    product_in: ProductCreate,
) -> Any:
    product = Product.model_validate(
        product_in, update={"remaining_yield": product_in.total_yield})
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.get("/products/{product_id}", response_model=ProductRead)
def read_product(
    session: SessionDep,
    product_id: int,
) -> Any:
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/middlemen/", response_model=MiddlemanRead)
def create_middleman(
    session: SessionDep,
    middleman_in: MiddlemanCreate,
) -> Any:
    middleman = Middleman.model_validate(middleman_in)
    session.add(middleman)
    session.commit()
    session.refresh(middleman)
    return middleman


@router.get("/middlemen/{middleman_id}", response_model=MiddlemanRead)
def read_middleman(
    session: SessionDep,
    middleman_id: int,
) -> Any:
    middleman = session.get(Middleman, middleman_id)
    if not middleman:
        raise HTTPException(status_code=404, detail="Middleman not found")
    return middleman


@router.post("/transactions/", response_model=TransactionRead)
def create_transaction(
    session: SessionDep,
    transaction_in: TransactionCreate,
) -> Any:
    product = session.get(Product, transaction_in.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.remaining_yield < transaction_in.quantity:
        raise HTTPException(status_code=400,
                            detail="Insufficient remaining yield")
    transaction = Transaction.model_validate(transaction_in)
    qr_data = f"Transaction ID: {transaction.id}, Product: {product.name}, Quantity: {transaction.quantity}"
    qr_code_filename = generate_qr_code(
        qr_data, prefix="transaction", directory="uploads/transaction_qrcodes")
    transaction.qr_code = qr_code_filename
    session.add(transaction)
    product.remaining_yield -= transaction_in.quantity
    session.commit()
    session.refresh(transaction)
    return transaction


@router.get("/transactions/{transaction_id}", response_model=TransactionRead)
def read_transaction(
    session: SessionDep,
    transaction_id: int,
) -> Any:
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.get("/qr_code/{qr_code}", response_model=QRCodeInfo)
def get_qr_code_info(
    session: SessionDep,
    qr_code: str,
) -> Any:
    statement = select(Transaction).where(Transaction.qr_code == qr_code)
    transaction = session.exec(statement).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="QR code not found")
    product = transaction.product
    plot = product.plot
    grower = plot.grower
    related_transactions = []
    current_transaction = transaction
    while current_transaction:
        related_transactions.append(current_transaction)
        current_transaction = current_transaction.parent_transaction
    return QRCodeInfo(
        grower=GrowerRead.model_validate(grower),
        plot=PlotRead.model_validate(plot),
        product=ProductRead.model_validate(product),
        transactions=[
            TransactionRead.model_validate(t) for t in related_transactions
        ],
    )
