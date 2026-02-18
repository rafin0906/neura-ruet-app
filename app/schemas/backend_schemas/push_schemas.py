from pydantic import BaseModel, Field


class DeviceTokenRegister(BaseModel):
    token: str = Field(..., min_length=10)


class DeviceTokenRegisterResponse(BaseModel):
    ok: bool = True
