from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Numeric, String, Integer, DateTime

class Base(DeclarativeBase):
    pass

class Account(Base):
    __tablename__ = "accounts"
    
    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal('0.00'), nullable=False)

class Operation(Base):
    __tablename__ = "operations"
    
    operation_id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    customer_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    store_id: Mapped[str] = mapped_column(String, nullable=False)
    check_number: Mapped[str] = mapped_column(String, index=True, nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    points_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False) # 'applied' или 'rejected'
    reject_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)