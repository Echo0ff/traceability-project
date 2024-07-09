from typing import Any, Optional

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import (
    Consumer,
    ConsumerCreate,
    Grower,
    GrowerCreate,
    GrowerRead,
    Item,
    ItemCreate,
    Middleman,
    MiddlemanCreate,
    MiddlemanUpdate,
    Plot,
    PlotCreate,
    PlotRead,
    Product,
    ProductCreate,
    ProductRead,
    QRCodeInfo,
    Transaction,
    TransactionCreate,
    TransactionRead,
    User,
    UserCreate,
    UserUpdate,
)
from app.utils import generate_qr_code


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create,
        update={"hashed_password": get_password_hash(user_create.password)})
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User,
                user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, phone: str) -> User | None:
    statement = select(User).where(User.phone == phone)
    session_user = session.exec(statement).first()
    return session_user


def get_user_by_phone(*, session: Session, phone: str) -> User | None:
    statement = select(User).where(User.phone == phone)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, phone: str,
                 password: str) -> User | None:
    db_user = get_user_by_phone(session=session, phone=phone)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


# def authenticate(session: Session, *, phone: str,
#                  password: str) -> Optional[User]:
#     user = session.exec(select(User).where(User.phone == phone)).first()
#     if not user:
#         return None
#     if not verify_password(password, user.hashed_password):
#         return None
#     return user


def create_item(*, session: Session, item_in: ItemCreate,
                owner_id: int) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


### Grower CRUD Operations


async def create_grower(
    db: Session,
    grower: GrowerCreate,
    grower_type: str,
):
    db_grower = Grower(type=grower_type, **grower.dict())
    db.add(db_grower)
    db.commit()
    db.refresh(db_grower)
    return db_grower


# def create_grower(*, session: Session, grower_create: GrowerCreate) -> Grower:
#     db_obj = Grower.model_validate(grower_create)
#     session.add(db_obj)
#     session.commit()
#     session.refresh(db_obj)
#     return db_obj

# def update_grower(
#     *, session: Session, db_grower: Grower, grower_in: GrowerUpdate
# ) -> Any:
#     grower_data = grower_in.model_dump(exclude_unset=True)
#     db_grower.sqlmodel_update(grower_data)
#     session.add(db_grower)
#     session.commit()
#     session.refresh(db_grower)
#     return db_grower


def get_grower_by_id(*, session: Session, grower_id: int) -> Grower | None:
    statement = select(Grower).where(Grower.id == grower_id)
    session_grower = session.exec(statement).first()
    return session_grower


### Middleman CRUD Operations


def create_middleman(*, session: Session,
                     middleman_create: MiddlemanCreate) -> Middleman:
    db_obj = Middleman.model_validate(middleman_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_middleman(*, session: Session, db_middleman: Middleman,
                     middleman_in: MiddlemanUpdate) -> Any:
    middleman_data = middleman_in.model_dump(exclude_unset=True)
    db_middleman.sqlmodel_update(middleman_data)
    session.add(db_middleman)
    session.commit()
    session.refresh(db_middleman)
    return db_middleman


def get_middleman_by_id(*, session: Session,
                        middleman_id: int) -> Middleman | None:
    statement = select(Middleman).where(Middleman.id == middleman_id)
    session_middleman = session.exec(statement).first()
    return session_middleman


### Consumer CRUD Operations


def create_consumer(*, session: Session,
                    consumer_create: ConsumerCreate) -> Consumer:
    db_obj = Consumer.model_validate(consumer_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_consumer_by_id(*, session: Session,
                       consumer_id: int) -> Consumer | None:
    statement = select(Consumer).where(Consumer.id == consumer_id)
    session_consumer = session.exec(statement).first()
    return session_consumer


# Grower CRUD operations
def create_grower(*, session: Session, grower_in: GrowerCreate) -> Grower:
    db_grower = Grower.model_validate(grower_in)
    session.add(db_grower)
    session.commit()
    session.refresh(db_grower)
    return db_grower


def get_grower(*, session: Session, grower_id: int) -> Optional[Grower]:
    return session.get(Grower, grower_id)


def get_grower_by_name(*, session: Session, name: str) -> Optional[Grower]:
    statement = select(Grower).where(Grower.name == name)
    return session.exec(statement).first()


def update_grower(*, session: Session, db_grower: Grower,
                  grower_in: GrowerCreate) -> Grower:
    grower_data = grower_in.model_dump(exclude_unset=True)
    db_grower.sqlmodel_update(grower_data)
    session.add(db_grower)
    session.commit()
    session.refresh(db_grower)
    return db_grower


# Plot CRUD operations
def create_plot(*, session: Session, plot_in: PlotCreate) -> Plot:
    db_plot = Plot.model_validate(plot_in)
    session.add(db_plot)
    session.commit()
    session.refresh(db_plot)
    return db_plot


def get_plot(*, session: Session, plot_id: int) -> Optional[Plot]:
    return session.get(Plot, plot_id)


# Product CRUD operations
def create_product(*, session: Session, product_in: ProductCreate) -> Product:
    db_product = Product.model_validate(
        product_in, update={"remaining_yield": product_in.total_yield})
    session.add(db_product)
    session.commit()
    session.refresh(db_product)
    return db_product


def get_product(*, session: Session, product_id: int) -> Optional[Product]:
    return session.get(Product, product_id)


def update_product_yield(*, session: Session, db_product: Product,
                         quantity: float) -> Product:
    db_product.remaining_yield -= quantity
    session.add(db_product)
    session.commit()
    session.refresh(db_product)
    return db_product


# Middleman CRUD operations
def create_middleman(*, session: Session,
                     middleman_in: MiddlemanCreate) -> Middleman:
    db_middleman = Middleman.model_validate(middleman_in)
    session.add(db_middleman)
    session.commit()
    session.refresh(db_middleman)
    return db_middleman


def get_middleman(*, session: Session,
                  middleman_id: int) -> Optional[Middleman]:
    return session.get(Middleman, middleman_id)


# Transaction CRUD operations
def create_transaction(*, session: Session,
                       transaction_in: TransactionCreate) -> Transaction:
    db_transaction = Transaction.model_validate(transaction_in)

    # Generate QR code (you'll need to implement this function)
    qr_code = generate_qr_code(db_transaction)
    db_transaction.qr_code = qr_code

    session.add(db_transaction)

    # Update product remaining yield
    product = get_product(session=session,
                          product_id=transaction_in.product_id)
    if product:
        update_product_yield(session=session,
                             db_product=product,
                             quantity=transaction_in.quantity)

    session.commit()
    session.refresh(db_transaction)
    return db_transaction


def get_transaction(*, session: Session,
                    transaction_id: int) -> Optional[Transaction]:
    return session.get(Transaction, transaction_id)


def get_transaction_by_qr_code(*, session: Session,
                               qr_code: str) -> Optional[Transaction]:
    statement = select(Transaction).where(Transaction.qr_code == qr_code)
    return session.exec(statement).first()


# QR Code Info
def get_qr_code_info(*, session: Session,
                     qr_code: str) -> Optional[QRCodeInfo]:
    transaction = get_transaction_by_qr_code(session=session, qr_code=qr_code)
    if not transaction:
        return None

    product = transaction.product
    plot = product.plot
    grower = plot.grower

    # Get all related transactions
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
