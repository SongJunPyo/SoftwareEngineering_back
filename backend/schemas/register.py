from pydantic import BaseModel, EmailStr, Field

class AccountCreate(BaseModel):
    email: EmailStr = Field(..., example="account@example.com")
    password: str = Field(..., min_length=8, example="securepassword123")
    name: str = Field(..., example="홍길동")
    phone_number: str = Field(..., example="010-1234-5678")
    address: str = Field(..., example="서울시 강남구")
    account_type: int = Field(3, example=3)  # 기본값은 사용자 3