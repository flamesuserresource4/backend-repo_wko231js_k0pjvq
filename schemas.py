from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr

# NOTE: Each class corresponds to one MongoDB collection named by lowercase class name

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    role: str = Field("user", description="Role name: user | admin")
    avatar_url: Optional[str] = Field(None, description="Profile image URL")
    settings: Dict[str, Any] = Field(default_factory=dict, description="User settings map")
    is_active: bool = Field(True, description="Active account")

class Role(BaseModel):
    name: str = Field(..., description="Role identifier")
    permissions: List[str] = Field(default_factory=list, description="Allowed actions")

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    category: str = Field("digital", description="Product category")
    in_stock: bool = True

class Affiliate(BaseModel):
    network: str = Field(..., description="Affiliate network name")
    link: str = Field(..., description="Tracking link")
    clicks: int = 0
    conversions: int = 0

class Strategy(BaseModel):
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)

class Trade(BaseModel):
    symbol: str = Field(..., description="Ticker or pair, e.g., BTCUSDT")
    side: str = Field(..., description="buy or sell")
    qty: float = Field(..., gt=0)
    status: str = Field("pending", description="pending | filled | canceled")
    strategy: Optional[str] = None
    pnl: Optional[float] = None

class Video(BaseModel):
    title: str
    script: Optional[str] = None
    status: str = Field("draft", description="draft | rendering | published")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Job(BaseModel):
    kind: str = Field(..., description="job type, e.g., backtest, render, publish")
    status: str = Field("queued", description="queued | running | completed | failed")
    payload: Dict[str, Any] = Field(default_factory=dict)
    owner_email: Optional[EmailStr] = None

class Audit(BaseModel):
    action: str
    actor: Optional[str] = None
    severity: str = Field("info", description="info | warn | error | critical")
    details: Dict[str, Any] = Field(default_factory=dict)

class ContactMessage(BaseModel):
    name: str
    email: EmailStr
    message: str

class HealthCheck(BaseModel):
    component: str
    status: str = Field(..., description="ok | warn | error")
    info: Dict[str, Any] = Field(default_factory=dict)
