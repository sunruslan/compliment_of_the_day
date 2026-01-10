"""
Database module - DEPRECATED.

This module is kept for backward compatibility.
Please use 'from db import DatabaseManager' instead.
"""

# Import from new location for backward compatibility
from db import DatabaseManager, Base, Compliment, UserSettings

__all__ = ["DatabaseManager", "Base", "Compliment", "UserSettings"]
