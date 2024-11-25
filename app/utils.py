import os
import ast
from datetime import datetime, timedelta
from typing import Union, Any
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import create_engine, inspect
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from app.database import *
# Load environment variables
load_dotenv()

ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
ALGORITHM = "HS256"
JWT_SECRET_KEY = "4e019228a35ce36f8994e7fee43e38b335d2a1061845052d46fe06c10cf0b49a"
JWT_REFRESH_SECRET_KEY = "4c80c50fd2cff5bf2783ed006069fa323ed1c9fcc6378ee75368abf6e2d12e12"

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
model = ChatOpenAI()

def get_hashed_password(password: str) -> str:
    return password_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_context.verify(plain_password, hashed_password)

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    expires_delta = expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": datetime.utcnow() + expires_delta, "sub": str(subject)}
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    expires_delta = expires_delta or timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": datetime.utcnow() + expires_delta, "sub": str(subject)}
    return jwt.encode(to_encode, JWT_REFRESH_SECRET_KEY, algorithm=ALGORITHM)

def get_all_tables_and_schemas():
    inspector = inspect(engine)
    schemas = inspector.get_schema_names()
    all_tables = {schema: inspector.get_table_names(schema=schema) for schema in schemas}
    return all_tables

def get_all_tables_and_columns():
    inspector = inspect(engine)
    schemas = inspector.get_schema_names()
    all_tables = {}
    for schema in schemas:
        tables = inspector.get_table_names(schema=schema)
        schema_tables = {table: inspector.get_columns(table_name=table, schema=schema) for table in tables}
        all_tables[schema] = schema_tables
    return all_tables

def table_selector(schema, question):
    prompt = """
    You are the best database manager. You need to understand the user question and provide the table and schema needed to get the data.
    
    Here is the database schema: {schema}
    
    Here is the user question: {question}
    
    Note: Provide the relevant table and schema. If a join or additional tables are needed, include those as well.
    """
    prompt_template = ChatPromptTemplate.from_template(prompt)
    parser = StrOutputParser()
    chain = prompt_template | model | parser
    return chain.invoke({"schema": schema, "question": question})

def graph_requirement_check(final_schema, question):
    prompt = """
    You are the best data analyst. You need to understand the final schema and the user question and determine if a graph is needed to represent the data.
    
    Here is the final schema: {final_schema}
    
    Here is the user question: {question}
    
    Note: Answer only with 'yes' or 'no'. Consider that graphs will be created using Plotly, Seaborn, and Matplotlib.
    """
    prompt_template = ChatPromptTemplate.from_template(prompt)
    parser = StrOutputParser()
    chain = prompt_template | model | parser
    return chain.invoke({"final_schema": final_schema, "question": question})

def get_table(final_schema, question):
    prompt = """
    You are the best data engineer. Provide the table name based on the user question from the final schema so the user can perform further operations.
    
    Here is the final schema: {final_schema}
    
    Here is the user question: {question}
    
    Note: Provide only the table name in a string. Do not include extra words, symbols, or special characters.
    """
    prompt_template = ChatPromptTemplate.from_template(prompt)
    parser = StrOutputParser()
    chain = prompt_template | model | parser
    return chain.invoke({"final_schema": final_schema, "question": question})

def generate_code_using_llm(schema, user_query, attempt_number=1):
    schema_description = ", ".join([f"{col} ({dtype})" for col, dtype in schema.items()])
    prompt = (
        f"Attempt #{attempt_number}: Given the following DataFrame schema: {schema_description}, "
        f"generate Python code using Seaborn to {user_query}. "
        "Do not create any sample DataFrame; use only the given DataFrame. "
        "Ensure the code creates a visually appealing plot with labels, titles, and appropriate colors. "
        "Avoid using 'plt.show()' and 'ax.legend_.remove()'. The plot should be stored in a variable named 'fig'."
    )
    response = model.generate([prompt])
    return response.generations[0][0].text

def verify_code_syntax(code):
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)
