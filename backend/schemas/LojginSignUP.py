from pydantic import BaseModel, Field, field_validator
import re

class RegisterRequest(BaseModel):
    email: str = Field(..., example="user@example.com")
    password: str = Field(..., min_length=8, example="password123")
    password_confirm: str = Field(..., min_length=8, example="password123")
    name: str = Field(..., example="홍길동")

    @field_validator("email")
    @classmethod
    def validate_email(cls, email):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            raise ValueError("올바른 이메일 형식을 입력해주세요.")
        return email

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, confirm, info):
        password = info.data.get("password")
        if password != confirm:
            raise ValueError("비밀번호가 일치하지 않습니다.")
        return confirm

    @field_validator("password")
    @classmethod
    def password_complexity(cls, password):
        if len(password) < 8:
            raise ValueError("비밀번호는 8자리 이상이어야 합니다.")
        if not re.search(r"[A-Za-z]", password):
            raise ValueError("비밀번호에 영문이 1자 이상 포함되어야 합니다.")
        if not re.search(r"[0-9]", password):
            raise ValueError("비밀번호에 숫자가 1자 이상 포함되어야 합니다.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>\[\]\\/~`_\-+=;'']", password):
            raise ValueError("비밀번호에 특수기호가 1자 이상 포함되어야 합니다.")
        return password

class LoginRequest(BaseModel):
    email: str = Field(..., example="user@example.com")
    password: str = Field(..., example="password123")

    @field_validator("email")
    @classmethod
    def validate_email(cls, email):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            raise ValueError("올바른 이메일 형식을 입력해주세요.")
        return email
