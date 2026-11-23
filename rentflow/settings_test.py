
from .settings import *

# Automated tests use an isolated in-memory SQLite database.
# The normal development database remains MySQL.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
