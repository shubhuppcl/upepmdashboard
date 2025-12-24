import os
import json
import warnings
import certifi
import requests
from bs4 import BeautifulSoup
from requests.exceptions import SSLError
from urllib3.exceptions import InsecureRequestWarning

PAGE_URL = "https://www.upsldc.org/realtimedatap"
JSON_URL = "https://www.upsldc.org/assets/dataset/real-time-summary.json"
HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "User-Agent": "Mozilla/5.0",
    "Referer": PAGE_URL,
    "X-Requested-With": "XMLHttpRequest",
}
TARGET_IDS = [
    "SCHEDULE_MW", "DRAWL_MW", "OD_UD", "DEMAND_MW", 
    "TOTAL_SSGS_MW", "UP_THERMAL_GENERATION_MW", "IPP_THERMAL_GENERATION_MW", 
    "UP_HYDRO_GENERATION_MW", "COGEN_CPP_GENERATION_MW", "RE_SOLAR_GENERATION_MW", 
    "FREQUENC_HZ", "DEVIATION_RATE_PAISE_PER_UNIT"
]

def fetch_json(session, verify):
    try:
        r = session.get(JSON_URL, timeout=15, headers=HEADERS, verify=verify)
        r.raise_for_status()
    except SSLError as e:
        # fallback: one insecure attempt (for testing only)
        # print("SSL verification failed, doing one insecure fallback (not recommended).")
        warnings.simplefilter("ignore", InsecureRequestWarning)
        r = session.get(JSON_URL, timeout=15, headers=HEADERS, verify=False)
        r.raise_for_status()
    data = r.json()
    return data

def get_ups_data():
    """Fetches real-time summary data from UPSLDC."""
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    sess = requests.Session()
    sess.headers.update(HEADERS)
    verify = certifi.where()
    
    try:
        data = fetch_json(sess, verify)
        # data is expected to be a list with one object
        obj = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
        
        result = {}
        for k in TARGET_IDS:
            result[k] = obj.get(k)
        return result
    except Exception as e:
        # print("Failed to fetch JSON:", e)
        return None