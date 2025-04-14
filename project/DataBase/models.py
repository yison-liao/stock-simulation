from datetime import datetime
from typing import Optional

from DbInit import DatabaseInit
from sqlalchemy import INTEGER, DateTime, Float, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

engine = DatabaseInit().pg_engine


class Base(DeclarativeBase):
    pass


class StockPerformance(Base):
    __tablename__ = "StockPerformance"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(30))
    year: Mapped[Optional[str]] = mapped_column(String(30))
    ROE: Mapped[float] = mapped_column(Float)
    EPS: Mapped[float] = mapped_column(Float)
    revenue_growth: Mapped[float] = mapped_column(Float)
    date: Mapped[datetime] = mapped_column(DateTime)
    open_price: Mapped[float] = mapped_column(Float)
    close_price: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(INTEGER)

    def __repr__(self) -> str:
        return (
            f"User(id={self.id!r}, stock_code={self.stock_code!r}, year={self.year!r})"
        )


Base.metadata.create_all(engine)
