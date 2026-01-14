from pydantic import BaseModel, EmailStr


class EmailSchema(BaseModel):
    email: EmailStr


class ForgetPasswordSchema(BaseModel):
    email: EmailStr


class ResetPasswordSchema(BaseModel):
    email: EmailStr
    otp: str
    new_password: str
    confirm_password: str
