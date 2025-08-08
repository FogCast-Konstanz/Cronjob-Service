"""
Utility functions for safe settings access with type safety.
"""
from typing import Any, TypeVar, Union
from cron.settings import settings

T = TypeVar('T')

def get_setting(key: str, default: T = None) -> Union[T, Any]:
    """
    Safely get a setting value with fallback.
    
    Args:
        key: The setting key (supports dot notation for nested keys)
        default: Default value if key is not found
        
    Returns:
        The setting value or default
        
    Examples:
        get_setting('log_dir', './logs')
        get_setting('influx.url', 'http://localhost:8086')
        get_setting('discord.webhook_url', '')
    """
    try:
        keys = key.split('.')
        value = settings
        
        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            else:
                return default
                
        return value
    except (AttributeError, KeyError):
        return default

def has_setting(key: str) -> bool:
    """
    Check if a setting exists.
    
    Args:
        key: The setting key (supports dot notation)
        
    Returns:
        True if the setting exists, False otherwise
    """
    try:
        keys = key.split('.')
        value = settings
        
        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            else:
                return False
                
        return True
    except (AttributeError, KeyError):
        return False

# Convenience functions for commonly used settings
def get_log_dir() -> str:
    """Get the log directory path."""
    return get_setting('log_dir', './logs')

def get_data_dir() -> str:
    """Get the data directory path."""
    return get_setting('data_dir', './csv-data')

def get_influx_config() -> dict:
    """Get InfluxDB configuration."""
    return {
        'url': get_setting('influx.url', 'http://localhost:8086'),
        'token': get_setting('influx.token', ''),
        'org': get_setting('influx.org', ''),
        'bucket': get_setting('influx.bucket', '')
    }

def get_discord_webhook_url() -> str:
    """Get Discord webhook URL."""
    return get_setting('discord.webhook_url', '')

def get_coordinates() -> tuple:
    """Get latitude and longitude as tuple."""
    return (
        get_setting('latitude', 0.0),
        get_setting('longitude', 0.0)
    )
