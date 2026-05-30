from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CheckResult(Base):
    __tablename__ = "check_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id"), nullable=False
    )
    username: Mapped[str] = mapped_column(String, nullable=False)
    check_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(Text, default="{}")

    upload = relationship("Upload", back_populates="check_results")
