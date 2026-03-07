# bot/models/__init__.py
from bot.models.database import (
    Base, User, LicenseKey, KeyGenerationLog, Watchlist,
    WatchedMovie, UserPreference, ReleaseAlert,
    SupportTicket, SupportMessage,
    SubscriptionTier, KeyStatus, Priority, TicketStatus,
)
from bot.models.engine import get_session, init_db, close_db, redis_client, AsyncSessionFactory
from bot.models.user import UserRepo
from bot.models.license_key import LicenseKeyRepo
from bot.models.watchlist import WatchlistRepo
from bot.models.watched import WatchedRepo
from bot.models.preference import PreferenceRepo
from bot.models.alert import AlertRepo
from bot.models.ticket import TicketRepo

__all__ = [
    "Base", "User", "LicenseKey", "KeyGenerationLog", "Watchlist",
    "WatchedMovie", "UserPreference", "ReleaseAlert",
    "SupportTicket", "SupportMessage",
    "SubscriptionTier", "KeyStatus", "Priority", "TicketStatus",
    "get_session", "init_db", "close_db", "redis_client", "AsyncSessionFactory",
    "UserRepo", "LicenseKeyRepo", "WatchlistRepo", "WatchedRepo",
    "PreferenceRepo", "AlertRepo", "TicketRepo",
]