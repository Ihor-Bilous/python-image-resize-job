from pydantic import BaseModel, EmailStr, Field


class JobFormSchema(BaseModel):
    email: EmailStr
    width: int = Field(default=640, ge=64, le=1600)
