from fastapi import FastAPI, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.database import Base, engine, SessionLocal
from app.utils import get_hashed_password, verify_password, create_access_token, create_refresh_token, table_selector, get_all_tables_and_columns, get_table, generate_code_using_llm, verify_code_syntax
from app.utils import *
from fastapi import HTTPException, status
from io import StringIO
from app.models import User, TokenTable
from app.schemas import changepassword, QuestionModel
from langchain.agents import initialize_agent, Tool
from langchain_openai import ChatOpenAI
from langchain.agents.agent_types import AgentType
from langchain_community.utilities import SQLDatabase
from langchain_experimental.utilities import PythonREPL
from langchain_community.agent_toolkits import create_sql_agent
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from app import models

from dotenv import load_dotenv                                     
import csv
tables = get_all_tables_and_columns()
schema1 = tables.get("sys")
# Load environment variables
load_dotenv()

# Constants
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
ALGORITHM = "HS256"
JWT_SECRET_KEY = "4e019228a35ce36f8994e7fee43e38b335d2a1061845052d46fe06c10cf0b49a"
JWT_REFRESH_SECRET_KEY = "4c80c50fd2cff5bf2783ed006069fa323ed1c9fcc6378ee75368abf6e2d12e12"
OUTPUT_DIR = 'static/plots'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize FastAPI
app = FastAPI()
templates = Jinja2Templates(directory="template")
app.mount("/static", StaticFiles(directory="static"), name="static")

tables = get_all_tables_and_columns()
schema1 = tables.get("sys")

# Database session dependency
def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

# Home route
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

# Register page and endpoint
@app.get('/register')
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_user(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    if session.query(User).filter_by(email=email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    encrypted_password = get_hashed_password(password)
    new_user = User(name=name, email=email, password=encrypted_password)
    session.add(new_user)
    session.commit()
    return RedirectResponse(url="/login", status_code=303)

# Login page and endpoint
@app.get('/login')
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post('/login')
def login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session)
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect email or password")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    token_db = TokenTable(user_id=user.id, access_token=access_token, refresh_token=refresh_token, status=True)
    db.add(token_db)
    db.commit()
    return RedirectResponse(url="/upload-csv", status_code=303)

@app.get('/getusers')
def get_users(session: Session = Depends(get_session)):
    return session.query(User).all()

# Change password endpoint
@app.post('/change-password')
def change_password(request: changepassword, db: Session = Depends(get_session)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.old_password, user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or old password")

    user.password = get_hashed_password(request.new_password)
    db.commit()
    return {"message": "Password changed successfully"}

# Upload CSV page and endpoint
@app.get('/upload-csv')
async def upload_csv_page(request: Request):
    return templates.TemplateResponse("upload-csv.html", {"request": request})

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_session)):
    try:
        content = await file.read()
        df = pd.read_csv(StringIO(content.decode('utf-8')))
        
        for _, row in df.iterrows():
            new_record = models.CSVData(
                field1=row['Id'],  
                field2=row['SepalLengthCm'], 
                field3=row['SepalWidthCm'],  
                field4=row['PetalLengthCm'],
                field5=row['PetalWidthCm'],
                field6=row['Species']
            )
            db.add(new_record)
        db.commit()

        # Redirect to the question page after successful CSV upload
        return RedirectResponse(url="/question", status_code=303)
    except Exception as e:
        print(f"Error during CSV upload: {e}")
        raise HTTPException(status_code=500, detail="CSV upload failed")

@app.get("/connect-db")
async def get_connectdb_page(request: Request):
    return templates.TemplateResponse("connect-db.html", {"request": request})

@app.post("/connect-db")
async def connect_db(
    db_username: str = Form(...),
    db_password: str = Form(...),
    db_host: str = Form(...),
    db_port: str = Form(...),
    db_name: str = Form(...),
    db_table: str = Form(...),
):
    try:
        db_url = f"mysql+mysqlconnector://{db_username}:{db_password}@{db_host}:{db_port}/{db_name}"
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {db_table} LIMIT 1"))
            if result.fetchone() is not None:
                # Redirect to the question page after successful database connection
                return RedirectResponse(url="/question", status_code=303)
            else:
                return {"message": "Table is empty or does not exist"}
    except SQLAlchemyError as e:
        print(f"Database operation failed: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

# Question handling and plotting
@app.get("/question")
async def get_question_form(request: Request):
    return templates.TemplateResponse("question.html", {"request": request})

@app.post("/question")
async def graph_check(request: Request, question: str = Form(...)):
    try:
        q = question
        tables = table_selector(schema1, q)
        executable = graph_requirement_check(tables, q)
        print("executable code or not:", executable)
        
        if executable.lower() == "yes":
            table = get_table(tables, q)
            table = table.replace("\\", "").replace("'", "").strip()
            print("This is the given table:", table)
            
            with engine.connect() as conn:
                result = conn.execute(text(f'SELECT * FROM {str(table)}'))
                rows = result.fetchall()
                columns = result.keys()
                df = pd.DataFrame.from_records(rows, columns=columns)
                
                schema = df.dtypes.to_dict()
                
                def execute_code_with_error_handling(code, graph_type="bar", x_col=None, y_col=None):
                    local_dict = {'df': df, 'sns': sns, 'plt': plt, 'pd': pd}
                    
                    try:
                        exec(code, {}, local_dict)
                        
                        fig = local_dict.get('fig', plt.gcf())
                        fig_path = os.path.join(OUTPUT_DIR, 'plot.png')
                        fig.savefig(fig_path)
                        return fig_path
                        
                    except Exception as e:
                        print(f"Error encountered: {e}. Generating a basic fallback plot.")
                        plt.figure()
                        if graph_type == "bar":
                            sns.barplot(x=x_col, y=y_col, data=df, palette='viridis')
                        elif graph_type == "scatter":
                            sns.scatterplot(x=x_col, y=y_col, data=df, palette='coolwarm')
                        elif graph_type == "line":
                            sns.lineplot(x=x_col, y=y_col, data=df, palette='Blues')
                        elif graph_type == "hist":
                            sns.histplot(df[x_col], kde=True)
                        elif graph_type == "box":
                            sns.boxplot(x=x_col, y=y_col, data=df, palette='Set2')
                        else:
                            sns.barplot(x=x_col, y=y_col, data=df, palette='viridis')
                        plt.xlabel(x_col)
                        plt.ylabel(y_col)
                        plt.title(f"Fallback {graph_type.capitalize()} Plot")
                        fig_path = os.path.join(OUTPUT_DIR, 'plot.png')
                        plt.savefig(fig_path)
                        return fig_path

                code = generate_code_using_llm(df, question)
                print(f"This is the generated code: {code}")
                
                if verify_code_syntax(code):
                    fig_path = execute_code_with_error_handling(code, graph_type="bar", x_col="x", y_col="y")
                else:
                    fig_path = execute_code_with_error_handling(code, graph_type="bar", x_col="x", y_col="y")

                return templates.TemplateResponse("question.html", {"request": request, "plot_url": fig_path})
                
    except Exception as e:
        print(f"Error handling question: {e}")
        raise HTTPException(status_code=500, detail="Error handling question")