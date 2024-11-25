from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from app.database import Base
import datetime

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)  

class TokenTable(Base):
    __tablename__ = "token"
    user_id = Column(Integer)
    access_token = Column(String(450), primary_key = True)
    refresh_token = Column(String(450), nullable=False)
    status = Column(Boolean)
    created_date = Column(DateTime, default=datetime.datetime.now)


class CSVData(Base):
    __tablename__ = "csv_data"
    id = Column(Integer, primary_key=True, index=True)
    field1 = Column(Integer) 
    field2 = Column(Integer)
    field3 = Column(Integer)
    field4 = Column(Integer)
    field5 = Column(Integer)
    field6 = Column(String)

class DBConnection(Base):
    __tablename__ = "db_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    db_type = Column(String)
    host = Column(String)
    port = Column(Integer)
    database = Column(String)
    username = Column(String)
    password = Column(String)

