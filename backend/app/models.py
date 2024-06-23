from sqlmodel import Field, Relationship, SQLModel, JSON, Column
from datetime import datetime
from typing import Optional, List, TypeVar, Generic
from enum import Enum


T = TypeVar("T")


class ResponseBase(SQLModel, Generic[T]):
    message: str
    code: int
    data: T


# Shared properties
# TODO replace email str with EmailStr when sqlmodel supports it
class UserBase(SQLModel):
    email: str = Field(unique=True, index=True)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = None


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str


# TODO replace email str with EmailStr when sqlmodel supports it
class UserCreateOpen(SQLModel):
    email: str
    password: str
    full_name: str | None = None


# Properties to receive via API on update, all are optional
# TODO replace email str with EmailStr when sqlmodel supports it
class UserUpdate(UserBase):
    email: str | None = None  # type: ignore
    password: str | None = None


# TODO replace email str with EmailStr when sqlmodel supports it
class UserUpdateMe(SQLModel):
    full_name: str | None = None
    email: str | None = None


class UpdatePassword(SQLModel):
    current_password: str
    new_password: str


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str
    items: list["Item"] = Relationship(back_populates="owner")


# Properties to return via API, id is always required
class UserOut(UserBase):
    id: int


class UsersOut(SQLModel):
    data: list[UserOut]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str
    description: str | None = None


# Properties to receive on item creation
class ItemCreate(ItemBase):
    title: str


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = None  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    owner_id: int | None = Field(default=None, foreign_key="user.id", nullable=False)
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemOut(ItemBase):
    id: int
    owner_id: int


class ItemsOut(SQLModel):
    data: list[ItemOut]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: int | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str


class GrowerBase(SQLModel):
    phone_number: str
    email: Optional[str] = None
    location_coordinates: Optional[str] = None
    crop_type: str
    crop_yield: Optional[float] = None


class CorporateGrowerBase(GrowerBase):
    company_name: str
    company_registration_number: str


class IndividualGrowerBase(GrowerBase):
    id_card_number: str
    id_card_photo: str
    land_ownership_certificate: Optional[str] = None
    crop_type_pic: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))


class Grower(GrowerBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str  # 用于区分企业和农户个人
    qr_code: str
    name: Optional[str] = None
    phone_number: Optional[str] = None
    company_name: Optional[str] = None
    business_license_photo: Optional[str] = None
    company_registration_number: Optional[str] = None
    id_card_number: Optional[str] = Field(default=None, nullable=True, unique=True)
    id_card_photo: Optional[str] = None
    land_ownership_certificate: Optional[str] = None
    crop_type_pic: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))

    sold_to_middlemen: List["Middleman"] = Relationship(
        back_populates="purchase_from_grower"
    )


class CorporateGrowerCreate(CorporateGrowerBase):
    company_registration_number: str
    company_logo: Optional[str] = None


class IndividualGrowerCreate(IndividualGrowerBase):
    id_card_number: str
    id_card_photo: str
    land_ownership_certificate: Optional[str] = None
    crop_type_pic: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))


class GrowerRead(GrowerBase):
    id: int
    type: str
    qr_code: str
    company_registration_number: Optional[str] = None
    company_logo: Optional[str] = None
    id_card_number: Optional[str] = None
    id_card_photo: Optional[str] = None
    land_ownership_certificate: Optional[str] = None
    crop_type_pic: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))


class CorporateGrowerRead(CorporateGrowerBase):
    id: int
    qr_code: str


class IndividualGrowerRead(IndividualGrowerBase):
    id: int
    qr_code: str


class GrowerOut(SQLModel):
    id: int = Field(...)
    type: str = Field(...)  # "individual" 或 "corporate"
    crop_type: str = Field(...)
    crop_yield: Optional[float] = None
    location_coordinates: Optional[str] = None
    qr_code: str = Field(...)
    name: Optional[str] = None
    company_name: Optional[str] = None
    id_card_number: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    crop_type_pic: Optional[List[str]] = None


class GrowersOut(SQLModel):
    data: List[GrowerOut] = Field(...)
    count: int = Field(...)


### 2. Middleman Models


class MiddlemanType(str, Enum):
    INDIVIDUAL = "individual"
    CORPORATE = "corporate"


class MiddlemanBase(SQLModel):
    phone_number: str
    type: str
    purchase_type: str
    transaction_volume: Optional[str] = None
    location_coordinates: Optional[str] = None


class Middleman(MiddlemanBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    qr_code: str
    purchase_from_id: Optional[int] = Field(default=None, foreign_key="grower.id")
    purchase_from_middleman_id: Optional[int] = Field(
        default=None, foreign_key="middleman.id"
    )
    name: Optional[str] = None
    company_name: Optional[str] = None
    business_license_number: Optional[str] = None
    business_license_photo: Optional[str] = None
    id_card_number: Optional[str] = None
    id_card_photo: Optional[str] = None
    transaction_contracts: List[str] = Field(default=[], sa_column=Column(JSON))

    purchase_from_grower: Optional["Grower"] = Relationship(
        back_populates="sold_to_middlemen",
        sa_relationship_kwargs={"foreign_keys": "Middleman.purchase_from_id"},
    )
    purchase_from_middleman: Optional["Middleman"] = Relationship(
        back_populates="sold_to_middlemen",
        sa_relationship_kwargs={
            "foreign_keys": "Middleman.purchase_from_middleman_id",
            "remote_side": "Middleman.id",
        },
    )
    sold_to_middlemen: List["Middleman"] = Relationship(
        back_populates="purchase_from_middleman"
    )
    consumers: List["Consumer"] = Relationship(back_populates="middleman")


class MiddlemanCreate(MiddlemanBase):
    purchase_from_id: Optional[int] = None
    purchase_from_middleman_id: Optional[int] = None
    company_name: Optional[str] = None
    business_license_number: Optional[str] = None
    business_license_photo: Optional[str] = None
    id_card_number: Optional[str] = None
    id_card_photo: Optional[str] = None
    transaction_contracts: List[str] = Field(default=[])
    qr_code: str = Field(default="")


class MiddlemanUpdate(SQLModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    purchase_type: Optional[str] = None
    transaction_volume: Optional[str] = None
    location_coordinates: Optional[str] = None
    purchase_from_id: Optional[int] = None
    purchase_from_middleman_id: Optional[int] = None
    company_name: Optional[str] = None
    business_license_number: Optional[str] = None
    business_license_photo: Optional[str] = None
    id_card_number: Optional[str] = None
    id_card_photo: Optional[str] = None
    transaction_contracts: Optional[List[str]] = None


class MiddlemanRead(MiddlemanBase):
    id: int
    qr_code: str
    purchase_from_id: Optional[int] = None
    purchase_from_middleman_id: Optional[int] = None
    company_name: Optional[str] = None
    business_license_number: Optional[str] = None
    business_license_photo: Optional[str] = None
    id_card_number: Optional[str] = None
    id_card_photo: Optional[str] = None
    transaction_contracts: List[str] = Field(default=[])


class MiddlemanOut(SQLModel):
    id: int
    type: str
    purchase_type: str
    transaction_volume: Optional[str] = None
    location_coordinates: Optional[str] = None
    qr_code: str
    purchase_from_id: Optional[int] = None
    purchase_from_middleman_id: Optional[int] = None
    name: Optional[str] = None
    company_name: Optional[str] = None
    transaction_contracts: List[str] = Field(default=[])


class MiddlemansOut(SQLModel):
    data: List[MiddlemanOut]
    count: int


class ConsumerBase(SQLModel):
    purchase_details: str
    qr_code: str


class Consumer(ConsumerBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    traceability_info: Optional[str] = None
    middleman_id: Optional[int] = Field(default=None, foreign_key="middleman.id")

    middleman: Optional[Middleman] = Relationship(back_populates="consumers")


class ConsumerCreate(ConsumerBase):
    middleman_id: Optional[int] = None


class ConsumerRead(ConsumerBase):
    id: int
    traceability_info: Optional[str] = None
    middleman_id: Optional[int] = None


class ConsumerUpdate(SQLModel):
    purchase_details: Optional[str] = None
    traceability_info: Optional[str] = None
    middleman_id: Optional[int] = None


class ConsumerOut(ConsumerBase):
    id: int
    traceability_info: Optional[str] = None
    middleman_id: Optional[int] = None


class ConsumersOut(SQLModel):
    data: List[ConsumerOut]
    count: int


### 4. QR Code and Authentication Models


class QRCodeBase(SQLModel):
    data: str
    created_at: datetime


class QRCode(QRCodeBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    qr_code: str


class QRCodeCreate(QRCodeBase):
    pass


class QRCodeRead(QRCodeBase):
    id: int
    qr_code: str


class AuthenticationBase(SQLModel):
    phone_number: str
    verification_code: str
    verified_at: Optional[datetime] = None


class Authentication(AuthenticationBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class AuthenticationCreate(AuthenticationBase):
    pass


class AuthenticationUpdate(AuthenticationBase):
    verification_code: Optional[str] = None
    verified_at: Optional[datetime] = None
