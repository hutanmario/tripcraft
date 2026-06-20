from sqlalchemy import Column, Integer, String, Float, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.database import Base


# Tabela many-to-many între QuestionOption și Tag, cu greutate per asociere
option_tags = Table(
    "option_tags",
    Base.metadata,
    Column("option_id", Integer, ForeignKey("question_options.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
    Column("weight", Float, default=1.0),
)


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    question_text = Column(String, nullable=False)
    type = Column(String, default="single")      # ← adaugă
    source = Column(String, default="gap")    

    tag = relationship("Tag")
    options = relationship(
        "QuestionOption",
        back_populates="question",
        cascade="all, delete-orphan",
    )


class QuestionOption(Base):
    __tablename__ = "question_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    option_text = Column(String, nullable=False)
    value = Column(String, nullable=True) 

    question = relationship("Question", back_populates="options")
    tags = relationship("Tag", secondary=option_tags)