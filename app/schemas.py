from pydantic import BaseModel
import datetime

class UserCreate(BaseModel):
    name : str
    email : str
    password : str

class requestdetails(BaseModel):
    email:str
    password:str

class TokenSchema(BaseModel):
    access_token:str
    refresh_token:str

class changepassword(BaseModel):
    email:str
    old_password:str
    new_password:str

class TokenCreate(BaseModel):
    user_id:str
    access_token:str
    refresh_token:str
    status:bool
    created_date:datetime.datetime

class DBConnectionRequest(BaseModel):
    db_type: str
    host: str
    port: int
    database: str
    username: str
    password: str

class QuestionModel(BaseModel):
    question: str




