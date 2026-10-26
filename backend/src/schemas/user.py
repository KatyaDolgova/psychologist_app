from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.models import AdminRole, TransactionStatus, UserRole
from src.models.enums import (
    ClientSessionFormat,
    DateFormat,
    MethodFormat,
    PricingFormat,
    TimeFormat,
    UserGender,
    UserTimezone,
)
from src.utils.validators import normalize_and_validate_phone

PHONE_EXAMPLES = ["+79994445678"]
MAX_AGE_YEARS = 120


def validate_optional_phone(v: str | None) -> str | None:
    """Пустой номер (None, "" или пробелы) означает, что телефона нет."""
    if v is None or not v.strip():
        return None
    return normalize_and_validate_phone(v)


def validate_birth_date(v: datetime | None) -> datetime | None:
    """Дата рождения не может быть в будущем или раньше, чем MAX_AGE_YEARS лет назад."""
    if v is None:
        return None
    birth_date = v.date()
    today = date.today()
    if birth_date > today:
        raise ValueError("Дата рождения не может быть в будущем")
    if birth_date < date(today.year - MAX_AGE_YEARS, 1, 1):
        raise ValueError(
            f"Дата рождения не может быть раньше {MAX_AGE_YEARS} лет назад"
        )
    return v


class UserProfileResponse(BaseModel):
    id: int
    name: str | None = None
    email: EmailStr
    phone: str | None = Field(None, examples=PHONE_EXAMPLES)
    notifications: bool
    subscription: int | None = None  # UNIX-TIME дата,
    timezone: UserTimezone | None = None
    avatar: str | None = None
    birth_date: date | None = None
    gender: UserGender = UserGender.NOT_STATED
    new: bool = True


class UserSurvey(BaseModel):
    name: str
    birth_date: datetime
    gender: UserGender
    emotions: list[str] | None = None
    relations: list[str] | None = None
    work: list[str] | None = None
    life: list[str] | None = None
    personal: list[str] | None = None
    format: list[ClientSessionFormat] | None = None
    timezone: UserTimezone | None = None
    long: TimeFormat | None = None
    pricing: PricingFormat | None = None
    time: DateFormat | None = None
    method: MethodFormat | None = None

    model_config = ConfigDict(use_enum_values=True)

    @field_validator("birth_date")
    @classmethod
    def check_birth_date(cls, v):
        return validate_birth_date(v)


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    phone: str | None = Field(None, examples=PHONE_EXAMPLES)
    email: EmailStr | None = None
    birth_date: datetime | None = None
    gender: UserGender | None = None
    timezone: UserTimezone | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        return validate_optional_phone(v)

    @field_validator("birth_date")
    @classmethod
    def check_birth_date(cls, v):
        return validate_birth_date(v)


class AdminProfile(BaseModel):
    role: AdminRole


class UserForAdmin(BaseModel):
    id: int
    email: EmailStr
    name: str | None = None
    phone: str | None = Field(None, examples=PHONE_EXAMPLES)
    roles: list[UserRole]


class TransactionSchema(BaseModel):
    id: int
    date: datetime
    method: str
    status: TransactionStatus


class SessionSchema(BaseModel):
    id: int
    date: datetime
    psychologist_id: int
    how_long: int


class UserDetailForAdmin(BaseModel):
    id: int
    email: EmailStr
    name: str | None = None
    phone: str | None = Field(None, examples=PHONE_EXAMPLES)
    roles: list[UserRole]
    age: int | None = None
    transactions: list[TransactionSchema] = []
    sessions: list[SessionSchema] = []


class UserUpdateRequestForAdmin(BaseModel):
    name: str | None = None
    phone: str | None = Field(None, examples=PHONE_EXAMPLES)
    email: EmailStr | None = None
    birth_date: datetime | None = None
    gender: UserGender | None = None
    roles: list[UserRole] | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        return validate_optional_phone(v)

    @field_validator("birth_date")
    @classmethod
    def check_birth_date(cls, v):
        return validate_birth_date(v)
