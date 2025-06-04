from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os


env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path=env_path)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")


if SQLALCHEMY_DATABASE_URL is None:
    raise ValueError("DATABASE_URL is not set in .env")


# 의존성 주입용 세션
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# DB 엔진 및 세션 설정
engine = create_engine(SQLALCHEMY_DATABASE_URL, future=True)
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine, 
    future=True
)

Base = declarative_base()

# DB 연결 테스트
def check_db_connection():
    try:
        with engine.connect() as conn:

            tables = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            table_list = [table[0] for table in tables]
            if table_list:
                print("\nDATABASE_URL =", SQLALCHEMY_DATABASE_URL)
                print("Found tables:")
                for name in table_list:
                    print(f" - {name}")
            else:
                print("No tables found in the database")
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise

if __name__ == "__main__":
    check_db_connection()
    # print("BASE DIR:", os.path.dirname(os.path.dirname(__file__)))
    print("\nDATABASE_URL =", SQLALCHEMY_DATABASE_URL)
