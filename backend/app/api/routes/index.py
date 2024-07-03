from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter()


class CardItem(BaseModel):
    title: str
    icon: str
    color: str
    value: str
    url: str = None


class ResponseModel(BaseModel):
    message: str
    code: int
    data: List[CardItem]


@router.get("/cards", response_model=ResponseModel)
async def get_cards():
    cards = [
        CardItem(
            title="种植主",
            icon="brand",
            color="aquablue",
            value="关于种植主的简要说明xxxxx",
        ),
        CardItem(
            title="中间商",
            icon="identity",
            color="blue",
            value="关于中间商的简要说明xxxx",
        ),
        CardItem(
            title="消费者",
            icon="qr-code",
            color="indigo",
            value="关于消费者的简要说明xxxx",
            url="/workPages/photo",
        ),
    ]

    return ResponseModel(message="Cards retrieved successfully", code=200, data=cards)
