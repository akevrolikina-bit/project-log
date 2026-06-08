from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InvestEmployeeSelection(Base):
    __tablename__ = "invest_employee_selections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id"), nullable=False
    )
    username: Mapped[str] = mapped_column(String, nullable=False)


class InvestAllocation(Base):
    __tablename__ = "invest_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id"), nullable=False
    )
    username: Mapped[str] = mapped_column(String, nullable=False)
    task_key: Mapped[str] = mapped_column(String, nullable=False)
    invest_project: Mapped[str] = mapped_column(String, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    allocation_type: Mapped[str] = mapped_column(String, nullable=False)


class BuhCompanyMapping(Base):
    __tablename__ = "buh_company_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id"), nullable=False
    )
    task_key: Mapped[str] = mapped_column(String, nullable=False)
    buh_company: Mapped[str] = mapped_column(String, nullable=False)
    invest_project: Mapped[str | None] = mapped_column(String, nullable=True)
