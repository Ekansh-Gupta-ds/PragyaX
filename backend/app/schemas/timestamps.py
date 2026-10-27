"""Keep existing timestamp strings while accepting database datetime values."""
from datetime import datetime
from typing import Annotated
from pydantic import BeforeValidator


def serialize_timestamp(value):
    return value.isoformat() if isinstance(value, datetime) else value


TimestampString = Annotated[str, BeforeValidator(serialize_timestamp)]
