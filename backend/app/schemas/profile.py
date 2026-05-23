from pydantic import BaseModel

class ProfileUpdate(BaseModel):
    full_name: str | None = None
    currency: str | None = None
    timezone: str | None = None
    profile_image: str | None = None
