from typing import Any, Optional, Union

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import (
    Item,
    ItemCreate,
    User,
    UserCreate,
    UserUpdate,
    Grower,
    CorporateGrowerCreate,
    IndividualGrowerCreate,
    Middleman,
    MiddlemanCreate,
    MiddlemanUpdate,
    Consumer,
    ConsumerCreate,
    QRCode,
    QRCodeCreate,
    Authentication,
    AuthenticationCreate,
    AuthenticationUpdate,
)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
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


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: int) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


### Grower CRUD Operations


async def create_grower(
    db: Session,
    grower: Union[CorporateGrowerCreate, IndividualGrowerCreate],
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


def create_middleman(
    *, session: Session, middleman_create: MiddlemanCreate
) -> Middleman:
    db_obj = Middleman.model_validate(middleman_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_middleman(
    *, session: Session, db_middleman: Middleman, middleman_in: MiddlemanUpdate
) -> Any:
    middleman_data = middleman_in.model_dump(exclude_unset=True)
    db_middleman.sqlmodel_update(middleman_data)
    session.add(db_middleman)
    session.commit()
    session.refresh(db_middleman)
    return db_middleman


def get_middleman_by_id(*, session: Session, middleman_id: int) -> Middleman | None:
    statement = select(Middleman).where(Middleman.id == middleman_id)
    session_middleman = session.exec(statement).first()
    return session_middleman


### Consumer CRUD Operations


def create_consumer(*, session: Session, consumer_create: ConsumerCreate) -> Consumer:
    db_obj = Consumer.model_validate(consumer_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_consumer_by_id(*, session: Session, consumer_id: int) -> Consumer | None:
    statement = select(Consumer).where(Consumer.id == consumer_id)
    session_consumer = session.exec(statement).first()
    return session_consumer


### QR Code CRUD Operations


def create_qr_code(*, session: Session, qr_code_create: QRCodeCreate) -> QRCode:
    db_obj = QRCode.model_validate(qr_code_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_qr_code_by_data(*, session: Session, data: str) -> QRCode | None:
    statement = select(QRCode).where(QRCode.data == data)
    session_qr_code = session.exec(statement).first()
    return session_qr_code


### Authentication CRUD Operations


def create_authentication(
    *, session: Session, auth_create: AuthenticationCreate
) -> Authentication:
    db_obj = Authentication.model_validate(auth_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_authentication(
    *, session: Session, db_auth: Authentication, auth_in: AuthenticationUpdate
) -> Any:
    auth_data = auth_in.model_dump(exclude_unset=True)
    db_auth.sqlmodel_update(auth_data)
    session.add(db_auth)
    session.commit()
    session.refresh(db_auth)
    return db_auth


def get_authentication_by_phone_number(
    *, session: Session, phone_number: str
) -> Authentication | None:
    statement = select(Authentication).where(
        Authentication.phone_number == phone_number
    )
    session_auth = session.exec(statement).first()
    return session_auth


def authenticate(
    *, session: Session, phone_number: str, verification_code: str
) -> Authentication | None:
    db_auth = get_authentication_by_phone_number(
        session=session, phone_number=phone_number
    )
    if not db_auth:
        return None
    if db_auth.verification_code != verification_code:
        return None
    return db_auth
