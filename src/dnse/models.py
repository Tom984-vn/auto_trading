from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

# Authentication Models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str = Field(description="JWT token for standard API calls")
    user_id: Optional[str] = None
    account_no: Optional[str] = None

class VerifyOTPRequest(BaseModel):
    otp: str

class VerifyOTPResponse(BaseModel):
    trading_token: str = Field(alias="tradingToken", description="Token required for order placement")

# Order Execution Models
class PlaceOrderRequest(BaseModel):
    accountNo: str
    symbol: str
    side: str = Field(description="NB (Mua) or NS (Bán)")
    orderType: str = Field(default="LO", description="LO, MP, MTL")
    price: float
    quantity: int
    loanPackageId: int = 1531
    marketId: str = Field(default="UNDERLYING", description="UNDERLYING for stock market")

class PlaceOrderResponse(BaseModel):
    orderId: str
    status: str
    message: Optional[str] = None

# Conditional Order Models (DNSE Server-Side)
class TargetOrder(BaseModel):
    quantity: int
    side: str = Field(description="NB or NS")
    price: float
    orderType: str = Field(default="LO")
    loanPackageId: int = 1531

class ConditionalOrderProps(BaseModel):
    stopPrice: float
    marketId: str = "UNDERLYING"

class TimeInForce(BaseModel):
    kind: str = "GTD"
    expireTime: Optional[str] = None

class ConditionalOrderRequest(BaseModel):
    accountNo: str
    symbol: str
    category: str = "STOP"
    condition: str = Field(description="e.g. price <= 26500")
    props: ConditionalOrderProps
    targetOrder: TargetOrder
    timeInForce: Optional[TimeInForce] = None

class ConditionalOrderResponse(BaseModel):
    id: str
    symbol: str
    status: str
    condition: str

# WebSocket Market Data Model
class MarketTick(BaseModel):
    symbol: str
    price: float
    volume: int
    side: Optional[str] = None
    timestamp: str
