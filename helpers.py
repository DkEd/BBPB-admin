import streamlit as st
import redis
import json
import os
from datetime import datetime

def get_redis():
    """Connects to the shared Redis database using the Render Environment Variable."""
    # This looks for the 'REDIS_URL' you paste into the Render Dashboard
    return redis.from_url(os.environ.get("REDIS_URL"), decode_responses=True)

def format_time_string(t_str):
    """Ensures times are always HH:MM:SS for the leaderboard."""
    try:
        t_str = str(t_str).strip()
        parts = t_str.split(':')
        if len(parts) == 2: # Converts MM:SS -> 00:MM:SS
            return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        elif len(parts) == 3: # Converts H:M:S -> 00:00:00
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        return t_str
    except:
        return t_str

def time_to_seconds(t_str):
    """Converts time strings to total seconds for sorting and point math."""
    try:
        parts = list(map(int, str(t_str).split(':')))
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return 999999
    except:
        return 999999

def get_category(dob_str, race_date_str, mode="10Y"):
    """Calculates age category (Senior, V40, V50 etc.) based on race date."""
    try:
        dob = datetime.strptime(str(dob_str), '%Y-%m-%d')
        race_date = datetime.strptime(str(race_date_str), '%Y-%m-%d')
        # Exact age at time of race
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        
        step = 5 if mode == "5Y" else 10
        threshold = 35 if mode == "5Y" else 40
        
        if age < threshold:
            return "Senior"
        return f"V{(age // step) * step}"
    except:
        return "Unknown"
