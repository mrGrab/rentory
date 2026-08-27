from sqlmodel import Field, SQLModel


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None


class TokenPayload(SQLModel):
    sub: str | None = None
    exp: int | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)
