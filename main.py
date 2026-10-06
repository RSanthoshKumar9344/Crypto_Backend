from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import os
from typing import Annotated, Any, AsyncIterator, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

COINGECKO_API_BASE = "https://api.coingecko.com/api/v3"


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class Coin(APIModel):
    id: str
    symbol: str
    name: str
    image_url: str
    current_price: Optional[float]
    price_change_percentage_24h: Optional[float]
    market_cap: Optional[float]
    market_cap_rank: Optional[int]
    total_volume: Optional[float]
    circulating_supply: Optional[float]
    total_supply: Optional[float]

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: "".join(
            part.capitalize() if index else part
            for index, part in enumerate(field_name.split("_"))
        ),
    )


class CoinDetails(APIModel):
    coin: Coin
    high24h: Optional[float]
    low24h: Optional[float]
    ath: Optional[float]
    atl: Optional[float]
    priceChange24h: Optional[float]
    description: str


class ChartPoint(APIModel):
    timestamp: datetime
    price: float


class MarketStats(APIModel):
    totalMarketCap: float
    total24hVolume: float
    btcDominance: float
    activeCryptocurrencies: int
    marketCapChange24h: float


MOCK_COINS: list[dict[str, Any]] = [
    {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "image": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png",
        "current_price": 67421.20,
        "price_change_percentage_24h": 2.43,
        "market_cap": 1320000000000.0,
        "market_cap_rank": 1,
        "total_volume": 42800000000.0,
        "circulating_supply": 19700000.0,
        "total_supply": 21000000.0,
        "high_24h": 68735.60,
        "low_24h": 64958.40,
        "ath": 97760.74,
        "atl": 5393.70,
        "price_change_24h": 1638.33,
        "description": "Bitcoin (BTC) is a decentralized cryptocurrency.",
    },
    {
        "id": "ethereum",
        "symbol": "eth",
        "name": "Ethereum",
        "image": "https://assets.coingecko.com/coins/images/279/large/ethereum.png",
        "current_price": 3520.15,
        "price_change_percentage_24h": 1.82,
        "market_cap": 422000000000.0,
        "market_cap_rank": 2,
        "total_volume": 18200000000.0,
        "circulating_supply": 120000000.0,
        "total_supply": None,
        "high_24h": 3600.0,
        "low_24h": 3430.0,
        "ath": 4878.26,
        "atl": 0.432979,
        "price_change_24h": 62.9,
        "description": "Ethereum is a decentralized blockchain platform.",
    },
    {
        "id": "tether",
        "symbol": "usdt",
        "name": "Tether",
        "image": "https://assets.coingecko.com/coins/images/325/large/Tether.png",
        "current_price": 1.0,
        "price_change_percentage_24h": 0.01,
        "market_cap": 120000000000.0,
        "market_cap_rank": 3,
        "total_volume": 65000000000.0,
        "circulating_supply": 120000000000.0,
        "total_supply": 120000000000.0,
        "high_24h": 1.01,
        "low_24h": 0.99,
        "ath": 1.32,
        "atl": 0.572521,
        "price_change_24h": 0.0001,
        "description": "Tether is a stablecoin pegged to the US dollar.",
    },
]
MOCK_MARKET_STATS = {
    "totalMarketCap": 2480000000000.0,
    "total24hVolume": 89500000000.0,
    "btcDominance": 53.2,
    "activeCryptocurrencies": 14250,
    "marketCapChange24h": 2.15,
}
PERIOD_DAYS = {"1D": 1, "7D": 7, "30D": 30, "1Y": 365}


def get_coin(client_data: dict[str, Any]) -> Coin:
    return Coin(
        id=client_data["id"],
        symbol=client_data["symbol"].upper(),
        name=client_data["name"],
        image_url=client_data["image"],
        current_price=client_data.get("current_price"),
        price_change_percentage_24h=client_data.get(
            "price_change_percentage_24h"
        ),
        market_cap=client_data.get("market_cap"),
        market_cap_rank=client_data.get("market_cap_rank"),
        total_volume=client_data.get("total_volume"),
        circulating_supply=client_data.get("circulating_supply"),
        total_supply=client_data.get("total_supply"),
    )


def usd_value(market_data: dict[str, Any], field: str) -> Any:
    value = market_data.get(field)
    return value.get("usd") if isinstance(value, dict) else value


async def fetch_json(
    request: Request, endpoint: str, params: dict[str, Any] | None = None
) -> tuple[Any, bool]:
    client: httpx.AsyncClient = request.app.state.http_client
    try:
        response = await client.get(endpoint, params=params)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502, detail="CoinGecko API is unavailable"
        ) from exc

    if response.status_code == 429:
        return None, True
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Coin not found")
    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=f"CoinGecko API returned HTTP {response.status_code}",
        )
    try:
        return response.json(), False
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail="CoinGecko API returned invalid JSON"
        ) from exc


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    headers = {"accept": "application/json"}
    api_key = os.getenv("COINGECKO_API_KEY")
    if api_key:
        headers["x-cg-demo-api-key"] = api_key
    async with httpx.AsyncClient(
        base_url=COINGECKO_API_BASE,
        headers=headers,
        timeout=httpx.Timeout(10.0, connect=5.0),
    ) as client:
        app.state.http_client = client
        yield


app = FastAPI(
    title="Cryptocurrency Market Research API",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/coins", response_model=list[Coin], response_model_by_alias=True)
async def list_coins(request: Request) -> list[Coin]:
    data, rate_limited = await fetch_json(
        request,
        "/coins/markets",
        {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        },
    )
    if rate_limited:
        return [get_coin(coin) for coin in MOCK_COINS]
    return [get_coin(coin) for coin in data]


@app.get(
    "/api/v1/coins/{coin_id}",
    response_model=CoinDetails,
    response_model_by_alias=True,
)
async def coin_details(
    request: Request,
    coin_id: Annotated[str, Path(min_length=1, max_length=100)],
) -> CoinDetails:
    data, rate_limited = await fetch_json(
        request,
        f"/coins/{coin_id}",
        {
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "false",
            "developer_data": "false",
            "sparkline": "false",
        },
    )
    if rate_limited:
        data = next((coin for coin in MOCK_COINS if coin["id"] == coin_id), None)
        if data is None:
            raise HTTPException(
                status_code=404,
                detail=f"No fallback data available for coin '{coin_id}'",
            )
        market_data = data
        description = data["description"]
    else:
        market_data = data.get("market_data", {})
        description = (data.get("description") or {}).get("en", "")

    return CoinDetails(
        coin=get_coin(
            {
                "id": data["id"],
                "symbol": data["symbol"],
                "name": data["name"],
                "image": data.get("image")
                if rate_limited
                else (data.get("image") or {}).get("large"),
                "current_price": usd_value(market_data, "current_price"),
                "price_change_percentage_24h": market_data.get(
                    "price_change_percentage_24h"
                ),
                "market_cap": usd_value(market_data, "market_cap"),
                "market_cap_rank": data.get("market_cap_rank"),
                "total_volume": usd_value(market_data, "total_volume"),
                "circulating_supply": market_data.get("circulating_supply"),
                "total_supply": market_data.get("total_supply"),
            }
        ),
        high24h=usd_value(market_data, "high_24h"),
        low24h=usd_value(market_data, "low_24h"),
        ath=usd_value(market_data, "ath"),
        atl=usd_value(market_data, "atl"),
        priceChange24h=usd_value(market_data, "price_change_24h"),
        description=description,
    )


@app.get(
    "/api/v1/coins/{coin_id}/chart",
    response_model=list[ChartPoint],
    response_model_by_alias=True,
)
async def coin_chart(
    request: Request,
    coin_id: Annotated[str, Path(min_length=1, max_length=100)],
    period: Literal["1D", "7D", "30D", "1Y"] = Query("1D"),
) -> list[ChartPoint]:
    days = PERIOD_DAYS[period]
    data, rate_limited = await fetch_json(
        request,
        f"/coins/{coin_id}/market_chart",
        {"vs_currency": "usd", "days": days},
    )
    if rate_limited:
        coin = next((item for item in MOCK_COINS if item["id"] == coin_id), None)
        if coin is None:
            raise HTTPException(
                status_code=404,
                detail=f"No fallback data available for coin '{coin_id}'",
            )
        now = datetime.now(timezone.utc)
        return [
            ChartPoint(
                timestamp=now - timedelta(days=days),
                price=coin["current_price"] * 0.97,
            ),
            ChartPoint(timestamp=now, price=coin["current_price"]),
        ]

    return [
        ChartPoint(
            timestamp=datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc),
            price=price,
        )
        for timestamp, price in data.get("prices", [])
    ]


@app.get(
    "/api/v1/market/stats",
    response_model=MarketStats,
    response_model_by_alias=True,
)
async def market_stats(request: Request) -> MarketStats:
    data, rate_limited = await fetch_json(request, "/global")
    if rate_limited:
        return MarketStats(**MOCK_MARKET_STATS)

    global_data = data["data"]
    return MarketStats(
        totalMarketCap=global_data["total_market_cap"]["usd"],
        total24hVolume=global_data["total_volume"]["usd"],
        btcDominance=global_data["market_cap_percentage"]["btc"],
        activeCryptocurrencies=global_data["active_cryptocurrencies"],
        marketCapChange24h=global_data["market_cap_change_percentage_24h_usd"],
    )
