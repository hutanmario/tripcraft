from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id       = Column(Integer, primary_key=True, index=True)
    name     = Column(String, nullable=False, unique=True)
    slug     = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("tags.id"), nullable=True)

    is_leaf           = Column(Boolean, default=True, nullable=False)
    question_template = Column(Text, nullable=True)
    description       = Column(Text, nullable=True)
    image_url         = Column(String, nullable=True)
    icon              = Column(String, nullable=True)

    parent = relationship("Tag", remote_side=[id], backref="children")


class TagConflict(Base):
    __tablename__ = "tag_conflicts"
    __table_args__ = (
        UniqueConstraint("tag_a_id", "tag_b_id", name="uq_tag_conflicts_pair"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tag_a_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    tag_b_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    question = Column(Text, nullable=False)
    options = Column(JSONB, nullable=False)

    tag_a = relationship("Tag", foreign_keys=[tag_a_id], backref="conflicts_as_a")
    tag_b = relationship("Tag", foreign_keys=[tag_b_id], backref="conflicts_as_b")
