# =====================================================
# PRESCRIPTION DELIVERY SYSTEM - MULTI-TENANT LOGIN
# =====================================================

import streamlit as st
import requests
import json
import time
from datetime import datetime
import os

# =====================================================
# USER CREDENTIALS & ROLES
# =====================================================

USERS = {
    "provider": {
        "password": "rx2024",
        "role": "provider",
        "name": "Dr. James Wilson"
    },
    "john_doe":     {"password": "pass123", "role": "patient", "name": "John Doe"},
    "sarah_smith":  {"password": "pass123", "role": "patient", "name": "Sarah Smith"},
    "michael_chen": {"password": "pass123", "role": "patient", "name": "Michael Chen"},
    "emily_davis":  {"password": "pass123", "role": "patient", "name": "Emily Davis"},
    "robert_jones": {"password": "pass123", "role": "patient", "name": "Robert Jones"},
    "pharmacy1": {
        "password": "pharma1",
        "role": "pharmacy",
        "name": "CityMed Pharmacy – Downtown",
        "pharmacy_id": 1
    },
    "pharmacy2": {
        "password": "pharma2",
        "role": "pharmacy",
        "name": "QuickRx Pharmacy – Midtown",
        "pharmacy_id": 2
    },
    "mike_j":   {"password": "drive1", "role": "driver", "name": "Mike Johnson",  "driver_id": "DR001"},
    "linda_c":  {"password": "drive1", "role": "driver", "name": "Linda Chen",    "driver_id": "DR002"},
    "david_k":  {"password": "drive1", "role": "driver", "name": "David Kim",     "driver_id": "DR003"},
    "admin": {"password": "admin1", "role": "admin", "name": "System Admin"},
}

PATIENT_NAMES = ["John Doe", "Sarah Smith", "Michael Chen", "Emily Davis", "Robert Jones"]

# =====================================================
# GOOGLE MAPS API INTEGRATION
# =====================================================

class GoogleMapsAPI:

    def __init__(self, api_key):
        self.api_key = api_key

    def find_nearby_pharmacies(self, address):
        try:
            geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={self.api_key}"
            geo_response = requests.get(geocode_url)
            geo_data = geo_response.json()

            if geo_data['status'] != 'OK':
                status_code = geo_data.get('status', 'UNKNOWN')
                error_msg   = geo_data.get('error_message', 'No details provided by Google.')
                if status_code == 'REQUEST_DENIED':
                    st.error(f"❌ Google Maps REQUEST_DENIED — {error_msg}")
                    st.warning("Common fixes: (1) Enable Geocoding API in GCP Console, (2) Remove HTTP-referrer restrictions from your API key (server calls need IP or no restriction), (3) Ensure billing is active on your GCP project.")
                else:
                    st.error(f"❌ Geocoding failed — status: {status_code} — {error_msg}")
                return None

            location = geo_data['results'][0]['geometry']['location']
            lat, lng = location['lat'], location['lng']

            places_url = (
                f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                f"?location={lat},{lng}&rankby=distance&type=pharmacy&key={self.api_key}"
            )
            places_response = requests.get(places_url)
            places_data = places_response.json()

            if places_data['status'] != 'OK':
                st.error("❌ Could not find nearby pharmacies.")
                return None

            pharmacies = []
            for place in places_data['results'][:5]:
                pharmacy_lat = place['geometry']['location']['lat']
                pharmacy_lng = place['geometry']['location']['lng']

                dist_url = (
                    f"https://maps.googleapis.com/maps/api/distancematrix/json"
                    f"?origins={lat},{lng}&destinations={pharmacy_lat},{pharmacy_lng}"
                    f"&mode=driving&key={self.api_key}"
                )
                dist_response = requests.get(dist_url)
                dist_data = dist_response.json()

                distance_miles = "N/A"
                duration_text = "N/A"
                if dist_data['status'] == 'OK':
                    element = dist_data['rows'][0]['elements'][0]
                    if element['status'] == 'OK':
                        distance_meters = element['distance']['value']
                        distance_miles = round(distance_meters / 1609.34, 1)
                        duration_text = element['duration']['text']

                pharmacies.append({
                    'id': place['place_id'],
                    'name': place['name'],
                    'address': place.get('vicinity', 'Address not available'),
                    'rating': place.get('rating', 4.0),
                    'open_now': place.get('opening_hours', {}).get('open_now', True),
                    'distance_miles': distance_miles,
                    'drive_time': duration_text,
                    'lat': pharmacy_lat,
                    'lng': pharmacy_lng
                })

            pharmacies.sort(key=lambda x: x['distance_miles'] if isinstance(x['distance_miles'], (int, float)) else 999)
            return pharmacies[:3]

        except Exception as e:
            st.error(f"❌ Error finding pharmacies: {str(e)}")
            return None

    def calculate_route(self, origin, destinations):
        try:
            results = []
            for dest in destinations:
                url = (
                    f"https://maps.googleapis.com/maps/api/distancematrix/json"
                    f"?origins={origin}&destinations={dest}&mode=driving&key={self.api_key}"
                )
                response = requests.get(url)
                data = response.json()
                if data['status'] == 'OK':
                    element = data['rows'][0]['elements'][0]
                    if element['status'] == 'OK':
                        results.append({
                            'distance': element['distance']['text'],
                            'duration': element['duration']['text'],
                            'duration_value': element['duration']['value']
                        })
                    else:
                        results.append({'distance': 'N/A', 'duration': 'N/A', 'duration_value': 9999})
                else:
                    results.append({'distance': 'N/A', 'duration': 'N/A', 'duration_value': 9999})
            return results
        except Exception as e:
            st.error(f"❌ Route calculation error: {str(e)}")
            return None


# =====================================================
# GROQ AI INTEGRATION
# =====================================================

class GroqAI:

    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def _call_api(self, messages, temperature=0.3):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }
        response = requests.post(self.base_url, headers=headers, json=payload)
        response.raise_for_status()
        return json.loads(response.json()['choices'][0]['message']['content'])

    def recommend_pharmacy(self, prescription, pharmacies):
        prompt = f"""You are a pharmacy recommendation system. Analyze these pharmacies and recommend the best one.

Prescription: {prescription['medication']} for {prescription['patient_name']}
Delivery address: {prescription.get('location', 'Unknown')}

Pharmacies:
{json.dumps(pharmacies, indent=2)}

Return JSON: {{
  "recommended_id": "<pharmacy place_id>",
  "score": <0-100>,
  "reasoning": ["reason1", "reason2", "reason3"],
  "ranked_options": [
    {{"id": "<id>", "name": "<name>", "score": <0-100>, "summary": "<one line>"}}
  ]
}}"""
        return self._call_api([{"role": "user", "content": prompt}])

    def recommend_driver(self, drivers, pharmacy_location, patient_location, delivery_priority):
        prompt = f"""You are a driver assignment system. Pick the best available driver.

Pharmacy location: {pharmacy_location}
Patient location: {patient_location}
Priority: {delivery_priority}

Drivers:
{json.dumps(drivers, indent=2)}

Return JSON: {{
  "recommended_driver_id": "<driver_id>",
  "score": <0-100>,
  "estimated_pickup_minutes": <int>,
  "estimated_delivery_minutes": <int>,
  "reasoning": ["reason1", "reason2"],
  "ranked_options": [
    {{"driver_id": "<id>", "name": "<name>", "score": <0-100>, "summary": "<one line>"}}
  ]
}}"""
        return self._call_api([{"role": "user", "content": prompt}])


# =====================================================
# SESSION STATE & HELPERS
# =====================================================

def init_session_state():
    if 'prescriptions' not in st.session_state:
        st.session_state.prescriptions = []
    if 'activity_log' not in st.session_state:
        st.session_state.activity_log = []
    if 'drivers' not in st.session_state:
        st.session_state.drivers = [
            {
                'id': 'DR001', 'name': 'Mike Johnson',
                'location': 'Downtown Cincinnati', 'lat': 39.1031, 'lng': -84.5120,
                'status': 'available', 'rating': 4.8,
                'deliveries_today': 8, 'avg_delivery_time': 22
            },
            {
                'id': 'DR002', 'name': 'Linda Chen',
                'location': 'Over-the-Rhine', 'lat': 39.1100, 'lng': -84.5150,
                'status': 'available', 'rating': 4.9,
                'deliveries_today': 6, 'avg_delivery_time': 20
            },
            {
                'id': 'DR003', 'name': 'David Kim',
                'location': 'Mount Adams', 'lat': 39.1050, 'lng': -84.5000,
                'status': 'available', 'rating': 4.7,
                'deliveries_today': 10, 'avg_delivery_time': 24
            },
        ]
    if 'groq_api_key' not in st.session_state:
        st.session_state.groq_api_key = os.environ.get('GROQ_API_KEY', '')
    if 'google_maps_api_key' not in st.session_state:
        st.session_state.google_maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'user_display_name' not in st.session_state:
        st.session_state.user_display_name = None
    if 'pharmacy_name_to_account' not in st.session_state:
        st.session_state.pharmacy_name_to_account = {}
    if 'expander_states' not in st.session_state:
        st.session_state.expander_states = {}
    # Initialize expander state keys for all existing prescriptions
    for _rx in st.session_state.get('prescriptions', []):
        _rid = _rx['id']
        for _key in [
            f"prov_exp_{_rid}",
            f"ph_exp_assigned_{_rid}",
            f"ph_exp_filling_{_rid}",
            f"ph_exp_ready_{_rid}",
            f"drv_exp_{_rid}",
        ]:
            if _key not in st.session_state:
                st.session_state[_key] = False


def add_activity(message):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.activity_log.append(f"[{ts}] {message}")


def update_prescription_status(rx_id, new_status, **kwargs):
    for rx in st.session_state.prescriptions:
        if rx['id'] == rx_id:
            rx['status'] = new_status
            for k, v in kwargs.items():
                rx[k] = v
            add_activity(f"Rx {rx_id} → {new_status}")
            break


def get_pharmacy_account(pharmacy_name):
    mapping = st.session_state.pharmacy_name_to_account
    if pharmacy_name not in mapping:
        if len(mapping) == 0:
            mapping[pharmacy_name] = 1
        elif len(mapping) == 1:
            mapping[pharmacy_name] = 2
        else:
            mapping[pharmacy_name] = 2
    return mapping[pharmacy_name]


# =====================================================
# DESIGN SYSTEM
# =====================================================

ROLE_COLORS = {
    "provider": {"primary": "#6366F1", "light": "#EEF2FF", "gradient": "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)"},
    "patient":  {"primary": "#0EA5E9", "light": "#F0F9FF", "gradient": "linear-gradient(135deg, #0EA5E9 0%, #38BDF8 100%)"},
    "pharmacy": {"primary": "#10B981", "light": "#ECFDF5", "gradient": "linear-gradient(135deg, #10B981 0%, #34D399 100%)"},
    "driver":   {"primary": "#F59E0B", "light": "#FFFBEB", "gradient": "linear-gradient(135deg, #F59E0B 0%, #FBBF24 100%)"},
    "admin":    {"primary": "#EF4444", "light": "#FEF2F2", "gradient": "linear-gradient(135deg, #EF4444 0%, #F87171 100%)"},
}

def apply_custom_css():
    st.html("""
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>

    /* ── Global ── */
    html, body {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background: #F8FAFC !important;
    }
    div, span, p, h1, h2, h3, h4, h5, h6, label, button, input, select, textarea {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1200px;
        background: #F8FAFC;
    }
    [data-testid="stAppViewContainer"] { background: #F8FAFC !important; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0D1B2A 0%, #112240 45%, #0D1B2A 100%) !important;
        border-right: 1px solid rgba(99,102,241,0.25) !important;
        box-shadow: 4px 0 24px rgba(0,0,0,0.35) !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.25rem !important;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span:not([data-baseweb]),
    [data-testid="stSidebar"] label {
        color: #B8C6D9 !important;
    }
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3,
    [data-testid="stSidebar"] .stMarkdown strong {
        color: #E2E8F0 !important;
        letter-spacing: 0.01em !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: rgba(99,102,241,0.2) !important;
        margin: 0.75rem 0 !important;
    }

    /* Sidebar radio nav items */
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        display: flex !important;
        align-items: center !important;
        padding: 0.5rem 0.75rem !important;
        border-radius: 10px !important;
        margin-bottom: 2px !important;
        transition: background 0.2s ease, color 0.2s ease !important;
        cursor: pointer !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        color: #94A3B8 !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background: rgba(99,102,241,0.12) !important;
        color: #E2E8F0 !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] [aria-checked="true"] + div,
    [data-testid="stSidebar"] [data-testid="stRadio"] input:checked ~ div {
        color: #818CF8 !important;
        font-weight: 600 !important;
    }

    /* Sidebar selectbox */
    [data-testid="stSidebar"] .stSelectbox > div > div {
        background: rgba(30,41,59,0.7) !important;
        border: 1px solid rgba(99,102,241,0.3) !important;
        border-radius: 10px !important;
        color: #CBD5E1 !important;
    }
    [data-testid="stSidebar"] .stSelectbox > div > div:hover {
        border-color: rgba(99,102,241,0.6) !important;
    }

    /* Sidebar text inputs */
    [data-testid="stSidebar"] .stTextInput > div > div > input {
        background: rgba(30,41,59,0.7) !important;
        border: 1px solid rgba(99,102,241,0.3) !important;
        border-radius: 10px !important;
        color: #E2E8F0 !important;
    }
    [data-testid="stSidebar"] .stTextInput > div > div > input:focus {
        border-color: #6366F1 !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
    }

    /* Sidebar section labels */
    [data-testid="stSidebar"] .stMarkdown p {
        color: #94A3B8 !important;
        font-size: 0.85rem !important;
        line-height: 1.5 !important;
    }

    /* Sidebar caption / small text */
    [data-testid="stSidebar"] small,
    [data-testid="stSidebar"] .stCaption {
        color: #64748B !important;
        font-size: 0.78rem !important;
    }

    /* ── Sign-out button (sidebar) ── */
    [data-testid="stSidebar"] .stButton > button {
        background: linear-gradient(135deg, rgba(239,68,68,0.07) 0%, rgba(220,38,38,0.11) 100%) !important;
        color: #FCA5A5 !important;
        border: 1px solid rgba(239,68,68,0.28) !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        letter-spacing: 0.03em !important;
        padding: 0.6rem 1rem !important;
        transition: box-shadow 0.15s ease, background 0.15s ease !important;
        width: 100% !important;
        box-shadow: 0 1px 6px rgba(239,68,68,0.10), inset 0 1px 0 rgba(255,255,255,0.04) !important;
        text-align: center !important;
        position: relative !important;
        overflow: hidden !important;
    }
    [data-testid="stSidebar"] .stButton > button::before {
        content: "" !important;
        position: absolute !important;
        inset: 0 !important;
        background: linear-gradient(135deg, rgba(239,68,68,0.0) 0%, rgba(239,68,68,0.06) 100%) !important;
        opacity: 0 !important;
        transition: opacity 0.25s ease !important;
        border-radius: inherit !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: linear-gradient(135deg, rgba(239,68,68,0.18) 0%, rgba(220,38,38,0.26) 100%) !important;
        border-color: rgba(239,68,68,0.55) !important;
        color: #FECACA !important;
        box-shadow: 0 4px 16px rgba(239,68,68,0.25) !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover::before {
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] .stButton > button:active {
        box-shadow: 0 1px 6px rgba(239,68,68,0.15) !important;
    }

    /* Sidebar accent divider line at top */
    [data-testid="stSidebar"]::before {
        content: "" !important;
        display: block !important;
        height: 3px !important;
        background: linear-gradient(90deg, #6366F1, #0EA5E9, #10B981) !important;
        border-radius: 0 0 3px 3px !important;
        position: sticky !important;
        top: 0 !important;
    }

    /* ── Buttons — NO transform (prevents Streamlit blink) ── */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        padding: 0.5rem 1.25rem !important;
        transition: box-shadow 0.15s ease !important;
        border: none !important;
        background: linear-gradient(135deg, #0EA5E9, #6366F1) !important;
        color: white !important;
        box-shadow: 0 2px 8px rgba(14,165,233,0.25) !important;
        width: 100%;
    }
    .stButton > button:hover {
        box-shadow: 0 4px 16px rgba(14,165,233,0.4) !important;
        transition: box-shadow 0.15s ease !important;
    }

    /* ── Form submit buttons ── */
    .stFormSubmitButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        background: linear-gradient(135deg, #10B981, #0EA5E9) !important;
        color: white !important;
        border: none !important;
        padding: 0.6rem 1.5rem !important;
        transition: box-shadow 0.15s ease, opacity 0.15s ease !important;
        box-shadow: 0 2px 10px rgba(16,185,129,0.3) !important;
        width: 100% !important;
    }
    .stFormSubmitButton > button:hover {
        box-shadow: 0 4px 16px rgba(16,185,129,0.4) !important;
        opacity: 0.90 !important;
    }

    /* ── Inputs — target BaseUI to fix black fields ── */
    [data-baseweb="input"] {
        border-radius: 10px !important;
        border: 1.5px solid #E2E8F0 !important;
        background: white !important;
        overflow: hidden;
    }
    [data-baseweb="input"]:focus-within {
        border-color: #0EA5E9 !important;
        box-shadow: 0 0 0 3px rgba(14,165,233,0.12) !important;
    }
    [data-baseweb="input"] input,
    [data-baseweb="base-input"] input {
        background: white !important;
        color: #0F172A !important;
        font-size: 0.9rem !important;
        caret-color: #0EA5E9 !important;
    }
    [data-baseweb="base-input"] {
        background: white !important;
        color: #0F172A !important;
    }
    [data-baseweb="select"] > div {
        border-radius: 10px !important;
        border: 1.5px solid #E2E8F0 !important;
        background: white !important;
        color: #0F172A !important;
    }
    [data-baseweb="select"] > div:focus-within {
        border-color: #0EA5E9 !important;
        box-shadow: 0 0 0 3px rgba(14,165,233,0.12) !important;
    }
    [data-baseweb="select"] span { color: #0F172A !important; }
    [data-baseweb="popover"] {
        border-radius: 10px !important;
        border: 1px solid #E2E8F0 !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.10) !important;
    }
    [data-baseweb="menu"] { background: white !important; }
    [data-baseweb="menu"] li { color: #0F172A !important; }
    [data-baseweb="menu"] li:hover { background: #F1F5F9 !important; }
    [data-testid="stNumberInput"] input {
        background: white !important;
        color: #0F172A !important;
    }
    .stTextInput label, .stSelectbox label,
    .stNumberInput label, .stTextArea label {
        color: #374151 !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
    }

    /* ── Password toggle icon — prevent black override ── */
    [data-baseweb="input"] svg {
        color: #64748B !important;
        stroke: #64748B !important;
    }
    [data-baseweb="input"] button svg,
    [data-baseweb="input"] [role="button"] svg,
    [data-testid="stTextInput"] [data-baseweb="input"] svg,
    .stTextInput [data-baseweb="input"] svg {
        color: #64748B !important;
        stroke: #64748B !important;
        fill: none !important;
        opacity: 0.7 !important;
    }

    /* ── Metrics ── */
    [data-testid="stMetric"] {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 1rem 1.25rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        transition: box-shadow 0.2s ease;
    }
    [data-testid="stMetric"]:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        color: #64748B !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #F1F5F9;
        border-radius: 12px;
        padding: 4px;
        gap: 2px;
        border: none !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 9px !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        color: #64748B !important;
        padding: 0.5rem 1rem !important;
        transition: background 0.15s ease, color 0.15s ease !important;
    }
    .stTabs [aria-selected="true"] {
        background: white !important;
        color: #0F172A !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 6px rgba(0,0,0,0.1) !important;
    }

    /* ── Expanders ── */
    [data-testid="stExpander"] {
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        margin-bottom: 0.5rem !important;
        overflow: hidden !important;
        background: white !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
        transition: box-shadow 0.2s ease !important;
        will-change: auto !important;
    }
    [data-testid="stExpander"]:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
    }
    [data-testid="stExpander"] summary {
        font-weight: 600 !important;
        color: #1E293B !important;
        padding: 0.75rem 1rem !important;
    }

    /* ── Progress bar ── */
    .stProgress > div > div {
        border-radius: 99px !important;
        background: #E2E8F0 !important;
    }
    .stProgress > div > div > div {
        border-radius: 99px !important;
        background: linear-gradient(90deg, #0EA5E9, #6366F1) !important;
        transition: width 0.5s ease !important;
    }

    /* ── Alerts ── */
    [data-testid="stAlert"] {
        border-radius: 12px !important;
        border: none !important;
        font-weight: 500 !important;
    }

    /* ── Divider ── */
    hr {
        border: none !important;
        border-top: 1px solid #E2E8F0 !important;
        margin: 1.25rem 0 !important;
    }

    /* ── Page header cards ── */
    .page-header {
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        color: white;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .page-header h1 {
        margin: 0;
        font-size: 1.6rem;
        font-weight: 700;
        color: white !important;
    }
    .page-header p {
        margin: 0;
        opacity: 0.85;
        font-size: 0.9rem;
    }

    /* ── Stat badge ── */
    .stat-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 99px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    /* ── Rx card ── */
    .rx-card {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        transition: box-shadow 0.2s ease;
    }
    .rx-card:hover {
        box-shadow: 0 6px 24px rgba(0,0,0,0.08);
    }

    /* ── Status pill ── */
    .status-pill {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 99px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .status-pending        { background: #FEF3C7; color: #92400E; }
    .status-assigned       { background: #FED7AA; color: #9A3412; }
    .status-filling        { background: #DBEAFE; color: #1E40AF; }
    .status-ready          { background: #D1FAE5; color: #065F46; }
    .status-out_for_delivery { background: #E0E7FF; color: #3730A3; }
    .status-delivered      { background: #DCFCE7; color: #14532D; }

    /* ── Milestone step ── */
    .milestone-step {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 12px;
        border-radius: 10px;
        margin-bottom: 6px;
        font-size: 0.875rem;
        font-weight: 500;
    }
    .milestone-done   { background: #D1FAE5; color: #065F46; }
    .milestone-pending { background: #F1F5F9; color: #94A3B8; }

    /* ── Activity feed ── */
    .activity-entry {
        padding: 8px 12px;
        border-radius: 8px;
        background: #F8FAFC;
        border-left: 3px solid #0EA5E9;
        margin-bottom: 6px;
        font-size: 0.8rem;
        font-family: 'Inter', monospace;
        color: #334155;
    }

    /* ── Login page ── */
    .login-hero {
        text-align: center;
        padding: 3rem 0 2rem 0;
    }
    .login-logo {
        font-size: 3.5rem;
        margin-bottom: 0.5rem;
    }
    .login-title {
        font-size: 2.6rem;
        font-weight: 900;
        letter-spacing: -0.03em;
        background: linear-gradient(135deg, #0EA5E9 0%, #6366F1 55%, #8B5CF6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
        line-height: 1.1;
    }
    .login-subtitle {
        color: #64748B;
        font-size: 1rem;
        margin-top: 0.5rem;
        letter-spacing: 0.02em;
        font-weight: 400;
    }
    .login-card {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 20px;
        padding: 2rem 2rem 1.5rem;
        box-shadow: 0 8px 40px rgba(0,0,0,0.08);
    }

    /* ── Pharmacy rec card ── */
    .rec-card {
        background: linear-gradient(135deg, #ECFDF5, #F0FDF4);
        border: 1.5px solid #6EE7B7;
        border-radius: 14px;
        padding: 1rem 1.25rem;
        margin: 0.75rem 0;
    }
    .rec-card-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #065F46;
        margin-bottom: 2px;
    }
    .rec-card-address {
        font-size: 0.85rem;
        color: #047857;
    }

    /* ── AI reasoning list ── */
    .reasoning-item {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        padding: 6px 0;
        font-size: 0.875rem;
        color: #334155;
        border-bottom: 1px solid #F1F5F9;
    }
    .reasoning-item:last-child { border-bottom: none; }

    /* ── Driver card ── */
    .driver-rec-card {
        background: linear-gradient(135deg, #EFF6FF, #EDE9FE);
        border: 1.5px solid #93C5FD;
        border-radius: 14px;
        padding: 1rem 1.25rem;
        margin: 0.75rem 0;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #F1F5F9; border-radius: 99px; }
    ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 99px; }
    ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

    /* ── Sidebar brand / app title ── */
    .sidebar-brand {
        text-align: center;
        padding: 0.5rem 0 1.25rem 0;
    }
    .sidebar-brand-title {
        font-size: 1.3rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, #93C5FD 0%, #818CF8 55%, #A78BFA 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-top: 6px;
        line-height: 1.2;
    }
    .sidebar-brand-subtitle {
        font-size: 0.68rem;
        color: #475569 !important;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        margin-top: 3px;
        font-weight: 500;
    }

    /* ── Spinner ── */
    [data-testid="stSpinner"] > div {
        border-top-color: #0EA5E9 !important;
    }

    </style>
    """)


def page_header(icon, title, subtitle, role="patient"):
    colors = ROLE_COLORS.get(role, ROLE_COLORS["patient"])
    st.markdown(f"""
    <div class="page-header" style="background: {colors['gradient']};">
        <div style="font-size:2rem;">{icon}</div>
        <div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def status_pill(status):
    labels = {
        'pending': '⏳ Pending',
        'assigned': '📋 Assigned',
        'filling': '⚗️ Filling',
        'ready': '✅ Ready',
        'out_for_delivery': '🚚 Out for Delivery',
        'delivered': '🏁 Delivered',
    }
    label = labels.get(status, status)
    return f'<span class="status-pill status-{status}">{label}</span>'


# =====================================================
# LOGIN PAGE
# =====================================================

def login_page():
    st.markdown("""
    <div class="login-hero">
        <svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-bottom:12px;">
            <rect width="72" height="72" rx="20" fill="url(#loginGrad)"/>
            <defs>
                <linearGradient id="loginGrad" x1="0" y1="0" x2="72" y2="72" gradientUnits="userSpaceOnUse">
                    <stop offset="0%" stop-color="#0EA5E9"/>
                    <stop offset="100%" stop-color="#6366F1"/>
                </linearGradient>
            </defs>
            <rect x="32" y="14" width="8" height="44" rx="4" fill="white"/>
            <rect x="14" y="32" width="44" height="8" rx="4" fill="white"/>
            <circle cx="52" cy="20" r="6" fill="#F0F9FF" opacity="0.5"/>
        </svg>
        <h1 class="login-title">RxPrescribe</h1>
        <p class="login-subtitle">Intelligent Prescription Delivery Platform</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.1, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("#### Sign in to your account")
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign In →", use_container_width=True)

        if submitted:
            user = USERS.get(username)
            if user and user["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.user_role = user["role"]
                st.session_state.user_display_name = user["name"]
                st.rerun()
            else:
                st.error("Invalid username or password.")

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🔑 View Demo Credentials"):
            st.markdown("""
<style>
[data-testid="stExpander"] .stDataFrame {
    font-size: 15px !important;
    color: #111111 !important;
}
[data-testid="stExpander"] .stDataFrame td,
[data-testid="stExpander"] .stDataFrame th {
    font-size: 15px !important;
    color: #111111 !important;
    font-weight: 500;
}
[data-testid="stExpander"] .stDataFrame th {
    font-weight: 700 !important;
    background-color: #f0f2f6 !important;
}
</style>
""", unsafe_allow_html=True)
            import pandas as pd
            credentials_data = {
                "Role": [
                    "👨‍⚕️ Provider",
                    "👤 Patient – John Doe",
                    "👤 Patient – Sarah Smith",
                    "👤 Patient – Michael Chen",
                    "👤 Patient – Emily Davis",
                    "👤 Patient – Robert Jones",
                    "🏪 Pharmacy 1",
                    "🏪 Pharmacy 2",
                    "🚗 Driver – Mike Johnson",
                    "🚗 Driver – Linda Chen",
                    "🚗 Driver – David Kim",
                    "📊 Admin",
                ],
                "Username": [
                    "provider", "john_doe", "sarah_smith", "michael_chen",
                    "emily_davis", "robert_jones", "pharmacy1", "pharmacy2",
                    "mike_j", "linda_c", "david_k", "admin",
                ],
                "Password": [
                    "rx2024", "pass123", "pass123", "pass123",
                    "pass123", "pass123", "pharma1", "pharma2",
                    "drive1", "drive1", "drive1", "admin1",
                ],
            }
            st.dataframe(pd.DataFrame(credentials_data), use_container_width=True, hide_index=True)


# =====================================================
# PROVIDER PORTAL
# =====================================================

def page_provider():
    page_header("👨‍⚕️", "Provider Portal", f"Welcome, {st.session_state.user_display_name}", "provider")

    with st.form("rx_form"):
        st.markdown("#### ✍️ Create New E-Prescription")
        col1, col2, col3 = st.columns(3)
        with col1:
            patient_name = st.selectbox("Patient", PATIENT_NAMES)
            medication = st.selectbox("Medication", [
                "Lisinopril 10mg", "Metformin 500mg",
                "Atorvastatin 20mg", "Amlodipine 5mg"
            ])
        with col2:
            quantity = st.number_input("Quantity", min_value=1, max_value=365, value=30)
            refills = st.number_input("Refills", min_value=0, max_value=12, value=2)
        with col3:
            insurance = st.selectbox("Insurance", [
                "Blue Cross Blue Shield", "United Healthcare", "Aetna", "Medicare"
            ])
            st.text_input("Patient Address", value="Set by patient", disabled=True)

        submitted = st.form_submit_button("📤 Send Prescription", use_container_width=True)

    if submitted:
        rx_id = f"RX{len(st.session_state.prescriptions) + 1:03d}"
        st.session_state.prescriptions.append({
            'id': rx_id,
            'patient_name': patient_name,
            'medication': medication,
            'quantity': quantity,
            'refills': refills,
            'insurance': insurance,
            'location': None,
            'status': 'pending',
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'pharmacy_id': None,
            'pharmacy_name': None,
            'pharmacy_address': None,
            'pharmacy_account': None,
            'driver_id': None,
            'driver_name': None,
            'delivery_time': None,
            'instructions': None,
            'estimated_delivery_time': None,
            'delivered_at': None,
            'milestones': {
                'gps_started': False,
                'photo_captured': False,
                'signature_obtained': False,
                'delivered': False
            }
        })
        # Initialize expander state keys for the new prescription
        for _key in [
            f"prov_exp_{rx_id}",
            f"ph_exp_assigned_{rx_id}",
            f"ph_exp_filling_{rx_id}",
            f"ph_exp_ready_{rx_id}",
            f"drv_exp_{rx_id}",
        ]:
            st.session_state[_key] = False
        add_activity(f"Provider created {rx_id} for {patient_name} – {medication}")
        st.success(f"✅ Prescription **{rx_id}** sent to **{patient_name}**")

    st.markdown("---")
    total = len(st.session_state.prescriptions)
    pending = sum(1 for r in st.session_state.prescriptions if r['status'] == 'pending')
    delivered = sum(1 for r in st.session_state.prescriptions if r['status'] == 'delivered')
    c1, c2, c3 = st.columns(3)
    c1.metric("📋 Total Prescriptions", total)
    c2.metric("⏳ Pending", pending)
    c3.metric("✅ Delivered Today", delivered)

    st.markdown("#### 📄 All Prescriptions")
    if not st.session_state.prescriptions:
        st.info("No prescriptions created yet. Use the form above to get started.")
    for rx in reversed(st.session_state.prescriptions[-10:]):
        exp_key = f"prov_exp_{rx['id']}"
        if exp_key not in st.session_state:
            st.session_state[exp_key] = False
        with st.expander(f"{rx['id']}  ·  {rx['patient_name']}  ·  {rx['medication']}", expanded=st.session_state.get(exp_key, False)):
            st.markdown(status_pill(rx['status']), unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Qty:** {rx['quantity']}")
            c2.write(f"**Refills:** {rx['refills']}")
            c3.write(f"**Insurance:** {rx['insurance']}")
            st.caption(f"🕐 Created: {rx['created_at']}")


# =====================================================
# PATIENT PORTAL
# =====================================================

def page_patient():
    patient_name = st.session_state.user_display_name
    page_header("👤", "My Prescriptions", f"Hello, {patient_name}", "patient")

    my_rxs = [r for r in st.session_state.prescriptions if r['patient_name'] == patient_name]

    if not my_rxs:
        st.markdown("""
        <div style="text-align:center; padding: 3rem; background: #F8FAFC; border-radius: 16px; border: 2px dashed #CBD5E1;">
            <div style="font-size:3rem;">💊</div>
            <h3 style="color:#64748B; margin-top:0.5rem;">No prescriptions yet</h3>
            <p style="color:#94A3B8;">Your provider hasn't sent you any prescriptions yet.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    maps_key = st.session_state.google_maps_api_key
    groq_key = st.session_state.groq_api_key

    for rx in my_rxs:
        st.markdown(f"""
        <div class="rx-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                <span style="font-size:1.1rem; font-weight:700; color:#0F172A;">{rx['id']} &nbsp;·&nbsp; {rx['medication']}</span>
                {status_pill(rx['status'])}
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            # ── ADDRESS SETUP ──────────────────────────────────────
            if rx['status'] == 'pending':
                if not rx['location']:
                    st.markdown("**📍 Set your delivery address to continue:**")
                    with st.form(f"addr_{rx['id']}"):
                        c1, c2 = st.columns(2)
                        street = c1.text_input("Street Address")
                        city   = c2.text_input("City")
                        c3, c4 = st.columns(2)
                        state  = c3.text_input("State")
                        zipcode = c4.text_input("ZIP Code")
                        if st.form_submit_button("💾 Save Address"):
                            if all([street, city, state, zipcode]):
                                full_address = f"{street}, {city}, {state} {zipcode}"
                                rx['location'] = full_address
                                rx.pop('pharmacy_recommendations', None)
                                add_activity(f"{patient_name} set address for {rx['id']}")
                                st.rerun()
                            else:
                                st.error("All fields are required.")
                else:
                    col_addr, col_edit = st.columns([3, 1])
                    col_addr.markdown(f"""
                    <div style="background:#F0F9FF; border:1px solid #BAE6FD; border-radius:10px; padding:10px 14px; font-size:0.9rem; color:#0369A1;">
                        📍 <strong>Delivery Address:</strong> {rx['location']}
                    </div>
                    """, unsafe_allow_html=True)
                    if col_edit.button("✏️ Edit", key=f"edit_addr_{rx['id']}"):
                        rx['_editing_address'] = True

                    if rx.get('_editing_address'):
                        with st.form(f"edit_addr_form_{rx['id']}"):
                            parts = rx['location'].split(',')
                            c1, c2 = st.columns(2)
                            street  = c1.text_input("Street", value=parts[0].strip() if len(parts) > 0 else "")
                            city    = c2.text_input("City",   value=parts[1].strip() if len(parts) > 1 else "")
                            c3, c4  = st.columns(2)
                            rest    = parts[2].strip().split() if len(parts) > 2 else ["", ""]
                            state   = c3.text_input("State", value=rest[0] if rest else "")
                            zipcode = c4.text_input("ZIP",   value=rest[1] if len(rest) > 1 else "")
                            sc1, sc2 = st.columns(2)
                            if sc1.form_submit_button("✅ Update"):
                                if all([street, city, state, zipcode]):
                                    rx['location'] = f"{street}, {city}, {state} {zipcode}"
                                    rx.pop('_editing_address', None)
                                    rx.pop('pharmacy_recommendations', None)
                                    st.rerun()
                            if sc2.form_submit_button("✖ Cancel"):
                                rx.pop('_editing_address', None)

                    # ── PHARMACY SEARCH ────────────────────────────
                    if rx['location'] and not rx.get('pharmacy_confirmed'):
                        if not maps_key or not groq_key:
                            st.error("⚠️ API keys are not configured. An admin must add GOOGLE_MAPS_API_KEY and GROQ_API_KEY as environment secrets in the HF Space settings.")
                        else:
                            if st.button(f"🤖 Find Nearby Pharmacies with AI", key=f"find_ph_{rx['id']}"):
                                with st.status("Analyzing pharmacies...", expanded=True) as status:
                                    st.write("🔍 Searching nearby pharmacies...")
                                    maps = GoogleMapsAPI(maps_key)
                                    pharmacies = maps.find_nearby_pharmacies(rx['location'])
                                    if pharmacies:
                                        st.write("🤖 AI analyzing options...")
                                        groq = GroqAI(groq_key)
                                        rec = groq.recommend_pharmacy(rx, pharmacies)
                                        rx['pharmacy_recommendations'] = {
                                            'pharmacies': pharmacies,
                                            'recommendation': rec
                                        }
                                        st.write("✅ Analysis complete!")
                                        status.update(label="", state="complete")

                        if rx.get('pharmacy_recommendations'):
                            data = rx['pharmacy_recommendations']
                            rec  = data['recommendation']
                            phs  = data['pharmacies']
                            rec_id = rec.get('recommended_id')
                            rec_ph = next((p for p in phs if p['id'] == rec_id), phs[0])

                            st.markdown(f"""
                            <div class="rec-card">
                                <div class="rec-card-title">🏆 {rec_ph['name']}</div>
                                <div class="rec-card-address">📍 {rec_ph['address']}</div>
                            </div>
                            """, unsafe_allow_html=True)

                            m1, m2, m3, m4 = st.columns(4)
                            m1.metric("🤖 AI Score", f"{rec.get('score', 'N/A')}/100")
                            m2.metric("📏 Distance", f"{rec_ph['distance_miles']} mi")
                            m3.metric("🚗 Drive Time", rec_ph['drive_time'])
                            m4.metric("⭐ Rating", rec_ph['rating'])

                            with st.expander("💡 Why this pharmacy?"):
                                for r in rec.get('reasoning', []):
                                    st.markdown(f"""<div class="reasoning-item">✦ {r}</div>""", unsafe_allow_html=True)
                            with st.expander("📋 View other options"):
                                for opt in rec.get('ranked_options', []):
                                    st.write(f"**#{rec.get('ranked_options',[]).index(opt)+1} {opt.get('name','')}** — Score: {opt.get('score','N/A')} — {opt.get('summary','')}")

                            st.markdown("#### 📅 Schedule Delivery")
                            with st.form(f"schedule_{rx['id']}"):
                                delivery_time = st.selectbox("Delivery Window", [
                                    "Today 2–4 PM", "Today 4–6 PM",
                                    "Tomorrow 10 AM–12 PM", "Tomorrow 2–4 PM"
                                ])
                                instructions = st.text_input("Special Instructions (optional)")
                                if st.form_submit_button("✅ Confirm & Schedule Delivery"):
                                    account = get_pharmacy_account(rec_ph['name'])
                                    update_prescription_status(
                                        rx['id'], 'assigned',
                                        pharmacy_id=rec_ph['id'],
                                        pharmacy_name=rec_ph['name'],
                                        pharmacy_address=rec_ph['address'],
                                        pharmacy_account=account,
                                        delivery_time=delivery_time,
                                        instructions=instructions,
                                        pharmacy_confirmed=True
                                    )
                                    add_activity(f"{patient_name} scheduled {rx['id']} → {rec_ph['name']}")

            # ── IN-TRANSIT TRACKING ────────────────────────────────
            elif rx['status'] in ['assigned', 'filling', 'ready', 'out_for_delivery']:
                status_map = {
                    'assigned':          ('🟠 Assigned to Pharmacy', 25),
                    'filling':           ('🔵 Being Filled',          50),
                    'ready':             ('🟢 Ready for Pickup',       75),
                    'out_for_delivery':  ('🚚 Out for Delivery',       90),
                }
                label, progress = status_map[rx['status']]
                st.markdown(f"**Status:** {label}")
                st.progress(progress)

                c1, c2 = st.columns(2)
                c1.markdown(f"""
                <div style="background:#F8FAFC; border-radius:10px; padding:12px; margin-top:8px;">
                    <div style="font-size:0.75rem; color:#64748B; font-weight:600; text-transform:uppercase; letter-spacing:0.05em;">Pharmacy</div>
                    <div style="font-weight:600; color:#0F172A; margin-top:2px;">{rx.get('pharmacy_name','—')}</div>
                    <div style="font-size:0.85rem; color:#64748B;">📍 {rx.get('pharmacy_address','—')}</div>
                </div>
                """, unsafe_allow_html=True)
                c2.markdown(f"""
                <div style="background:#F8FAFC; border-radius:10px; padding:12px; margin-top:8px;">
                    <div style="font-size:0.75rem; color:#64748B; font-weight:600; text-transform:uppercase; letter-spacing:0.05em;">Delivery Window</div>
                    <div style="font-weight:600; color:#0F172A; margin-top:2px;">🕐 {rx.get('delivery_time','—')}</div>
                </div>
                """, unsafe_allow_html=True)

                if rx['status'] == 'out_for_delivery':
                    st.markdown(f"""
                    <div style="background:#EDE9FE; border:1px solid #C4B5FD; border-radius:10px; padding:12px; margin-top:8px;">
                        🚗 <strong>Driver:</strong> {rx.get('driver_name','—')} &nbsp;·&nbsp; ⏱ <strong>ETA:</strong> {rx.get('estimated_delivery_time','Calculating...')}
                    </div>
                    """, unsafe_allow_html=True)

                ms = rx.get('milestones', {})
                st.markdown("<br>**Delivery Milestones:**", unsafe_allow_html=True)
                steps = [
                    ("📍 GPS Started",        ms.get('gps_started')),
                    ("📸 Photo Taken",         ms.get('photo_captured')),
                    ("✍️ Signature Obtained",  ms.get('signature_obtained')),
                    ("🏁 Delivered",           ms.get('delivered')),
                ]
                for label_m, done in steps:
                    css = "milestone-done" if done else "milestone-pending"
                    icon = "✅" if done else "○"
                    st.markdown(f'<div class="milestone-step {css}">{icon} &nbsp; {label_m}</div>', unsafe_allow_html=True)

            # ── DELIVERED ─────────────────────────────────────────
            elif rx['status'] == 'delivered':
                st.markdown(f"""
                <div style="background:#DCFCE7; border:1px solid #86EFAC; border-radius:12px; padding:1rem 1.25rem; margin-top:0.5rem;">
                    <div style="font-weight:700; color:#14532D; font-size:1rem;">🎉 Delivered successfully</div>
                    <div style="font-size:0.85rem; color:#166534; margin-top:4px;">
                        🕐 {rx.get('delivered_at','')} &nbsp;·&nbsp;
                        🏪 {rx.get('pharmacy_name','—')} &nbsp;·&nbsp;
                        🚗 {rx.get('driver_name','—')} &nbsp;·&nbsp;
                        🔄 {rx['refills']} refills remaining
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)


# =====================================================
# PHARMACY DASHBOARD
# =====================================================

def page_pharmacy():
    user = USERS[st.session_state.username]
    pharmacy_account = user['pharmacy_id']
    pharmacy_label   = user['name']

    page_header("🏪", pharmacy_label, f"Logged in as {st.session_state.user_display_name}", "pharmacy")

    my_rxs = [r for r in st.session_state.prescriptions if r.get('pharmacy_account') == pharmacy_account]

    assigned = [r for r in my_rxs if r['status'] == 'assigned']
    filling  = [r for r in my_rxs if r['status'] == 'filling']
    ready    = [r for r in my_rxs if r['status'] == 'ready']
    delivered_today = [r for r in my_rxs if r['status'] == 'delivered']

    c1, c2, c3 = st.columns(3)
    c1.metric("📥 New Orders",  len(assigned))
    c2.metric("⚗️ Filling",     len(filling))
    c3.metric("✅ Ready",       len(ready))

    if pharmacy_account == 2 and not my_rxs:
        st.markdown("""
        <div style="text-align:center; padding:2.5rem; background:#F8FAFC; border-radius:16px; border:2px dashed #CBD5E1; margin-top:1rem;">
            <div style="font-size:2.5rem;">🏪</div>
            <h3 style="color:#64748B;">Waiting for orders</h3>
            <p style="color:#94A3B8;">Prescriptions appear here when a patient's AI recommendation selects a second pharmacy location.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    tab1, tab2, tab3, tab4 = st.tabs(["📥 New Orders", "⚗️ Filling", "✅ Ready for Dispatch", "📦 Delivered"])

    with tab1:
        if not assigned:
            st.info("No new orders at this time.")
        for rx in assigned:
            exp_key = f"ph_exp_assigned_{rx['id']}"
            with st.expander(f"{rx['id']}  ·  {rx['patient_name']}  ·  {rx['medication']}", expanded=st.session_state.get(exp_key, False)):
                st.markdown(status_pill(rx['status']), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Qty:** {rx['quantity']}")
                c2.write(f"**Insurance:** {rx['insurance']}")
                c3.write(f"**Window:** {rx.get('delivery_time','—')}")
                if rx.get('instructions'):
                    st.info(f"📝 {rx['instructions']}")
                if st.button(f"✅ Accept Order", key=f"accept_{rx['id']}"):
                    st.session_state[exp_key] = True
                    update_prescription_status(rx['id'], 'filling')
                    time.sleep(0.15)
                    st.rerun()

    with tab2:
        if not filling:
            st.info("No prescriptions currently being filled.")
        for rx in filling:
            exp_key = f"ph_exp_filling_{rx['id']}"
            with st.expander(f"{rx['id']}  ·  {rx['patient_name']}  ·  {rx['medication']}", expanded=st.session_state.get(exp_key, False)):
                st.progress(60, text="⚗️ Filling in progress — 60%")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button(f"🟢 Mark as Ready", key=f"ready_{rx['id']}"):
                    st.session_state[exp_key] = True
                    update_prescription_status(rx['id'], 'ready')
                    time.sleep(0.15)
                    st.rerun()

    with tab3:
        if not ready:
            st.info("No prescriptions ready for dispatch.")

        groq_key = st.session_state.groq_api_key
        maps_key = st.session_state.google_maps_api_key

        for rx in ready:
            exp_key = f"ph_exp_ready_{rx['id']}"
            with st.expander(f"{rx['id']}  ·  {rx['patient_name']}  ·  {rx['medication']}", expanded=st.session_state.get(exp_key, False)):
                st.markdown(f"""
                <div style="background:#F0F9FF; border-radius:10px; padding:10px 14px; font-size:0.9rem; color:#0369A1; margin-bottom:10px;">
                    📍 <strong>Patient:</strong> {rx.get('location','—')}
                </div>
                """, unsafe_allow_html=True)

                if st.button(f"🤖 Find Best Driver with AI", key=f"find_drv_{rx['id']}"):
                    avail = [d for d in st.session_state.drivers if d['status'] == 'available']
                    if not avail:
                        st.warning("No drivers available right now.")
                    elif not groq_key:
                        st.error("Groq API key not configured.")
                    else:
                        with st.spinner("🤖 AI is selecting the best driver..."):
                            if maps_key:
                                maps = GoogleMapsAPI(maps_key)
                                origins = f"{rx.get('pharmacy_address','Cincinnati, OH')}"
                                destinations = [f"{d['lat']},{d['lng']}" for d in avail]
                                routes = maps.calculate_route(origins, destinations)
                                if routes:
                                    for i, d in enumerate(avail):
                                        d['distance_to_pharmacy'] = routes[i]['distance']
                                        d['eta_to_pharmacy'] = routes[i]['duration']

                            groq = GroqAI(groq_key)
                            rec = groq.recommend_driver(
                                avail,
                                rx.get('pharmacy_address', 'Cincinnati, OH'),
                                rx.get('location', 'Unknown'),
                                rx.get('delivery_time', 'standard')
                            )
                            rx['driver_recommendation'] = rec

                if rx.get('driver_recommendation'):
                    rec = rx['driver_recommendation']
                    rec_id = rec.get('recommended_driver_id')
                    rec_drv = next((d for d in st.session_state.drivers if d['id'] == rec_id), None)

                    if rec_drv:
                        st.markdown(f"""
                        <div class="driver-rec-card">
                            <div style="font-weight:700; color:#1E40AF; font-size:1rem;">🏆 Recommended: {rec_drv['name']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("🤖 AI Score", f"{rec.get('score','N/A')}/100")
                        m2.metric("⏱ Pickup ETA", f"{rec.get('estimated_pickup_minutes','?')} min")
                        m3.metric("🚚 Delivery ETA", f"{rec.get('estimated_delivery_minutes','?')} min")
                        m4.metric("⭐ Rating", rec_drv['rating'])

                        st.markdown("**Why this driver:**")
                        for r in rec.get('reasoning', []):
                            st.markdown(f'<div class="reasoning-item">✦ {r}</div>', unsafe_allow_html=True)
                        st.markdown("**Other options:**")
                        for opt in rec.get('ranked_options', []):
                            st.write(f"**{opt.get('name','')}** — Score: {opt.get('score','N/A')} — {opt.get('summary','')}")

                        if st.button(f"🚗 Assign to {rec_drv['name']}", key=f"assign_{rx['id']}"):
                            eta_val = f"~{rec.get('estimated_delivery_minutes', 30)} min"
                            st.session_state[exp_key] = True
                            for r in ready:
                                update_prescription_status(
                                    r['id'], 'out_for_delivery',
                                    driver_id=rec_id,
                                    driver_name=rec_drv['name'],
                                    estimated_delivery_time=eta_val
                                )
                            for d in st.session_state.drivers:
                                if d['id'] == rec_id:
                                    d['status'] = 'busy'
                                    break
                            add_activity(f"Driver {rec_drv['name']} assigned to pharmacy account {pharmacy_account}")
                            time.sleep(0.15)
                            st.rerun()

    with tab4:
        if not delivered_today:
            st.info("No deliveries completed yet today.")
        for rx in delivered_today:
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:12px; padding:10px 14px; background:#F8FAFC; border-radius:10px; margin-bottom:6px; border:1px solid #E2E8F0;">
                <span style="font-size:1.2rem;">✅</span>
                <div>
                    <span style="font-weight:600; color:#0F172A;">{rx['id']}</span>
                    <span style="color:#64748B;"> · {rx['patient_name']} · {rx['medication']}</span>
                    <div style="font-size:0.8rem; color:#94A3B8; margin-top:2px;">🚗 {rx.get('driver_name','—')} · {rx.get('delivered_at','')}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


# =====================================================
# DRIVER APP
# =====================================================

def page_driver():
    user = USERS[st.session_state.username]
    driver_id   = user['driver_id']
    driver_name = user['name']

    page_header("🚗", "Driver App", f"Logged in as {driver_name}", "driver")

    driver_obj = next((d for d in st.session_state.drivers if d['id'] == driver_id), None)

    active    = [r for r in st.session_state.prescriptions if r['status'] == 'out_for_delivery' and r.get('driver_id') == driver_id]
    completed = [r for r in st.session_state.prescriptions if r['status'] == 'delivered' and r.get('driver_id') == driver_id]

    is_available = driver_obj and driver_obj['status'] == 'available'
    status_html = (
        '<span style="background:#D1FAE5;color:#065F46;padding:4px 14px;border-radius:99px;font-weight:700;font-size:0.85rem;">🟢 Available</span>'
        if is_available else
        '<span style="background:#FEE2E2;color:#991B1B;padding:4px 14px;border-radius:99px;font-weight:700;font-size:0.85rem;">🔴 On Delivery</span>'
    )
    st.markdown(status_html, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("📦 Active Deliveries", len(active))
    c2.metric("✅ Completed Today",   len(completed))
    c3.metric("⭐ Rating", driver_obj['rating'] if driver_obj else "—")

    tab1, tab2 = st.tabs(["🚚 Active Deliveries", "✅ Completed"])

    with tab1:
        if not active:
            st.markdown("""
            <div style="text-align:center; padding:2.5rem; background:#FFFBEB; border-radius:16px; border:2px dashed #FCD34D; margin-top:1rem;">
                <div style="font-size:2.5rem;">🚗</div>
                <h3 style="color:#92400E;">No active deliveries</h3>
                <p style="color:#B45309;">You'll see new deliveries here once a pharmacy assigns them to you.</p>
            </div>
            """, unsafe_allow_html=True)
        for rx in active:
            exp_key = f"drv_exp_{rx['id']}"
            with st.expander(f"{rx['id']}  ·  {rx['patient_name']}  ·  {rx['medication']}", expanded=st.session_state.get(exp_key, False)):
                col_info, col_steps = st.columns([1.2, 1])

                with col_info:
                    st.markdown(f"""
                    <div style="background:#FAFAFA; border-radius:12px; padding:14px; font-size:0.9rem; line-height:1.8;">
                        <div><strong>👤 Patient:</strong> {rx['patient_name']}</div>
                        <div><strong>📍 Address:</strong> {rx.get('location','—')}</div>
                        <div><strong>💊 Medication:</strong> {rx['medication']}</div>
                        <div><strong>🕐 Window:</strong> {rx.get('delivery_time','—')}</div>
                        <div><strong>🏪 Pickup:</strong> {rx.get('pharmacy_name','—')}</div>
                        {"<div><strong>📝 Note:</strong> " + rx['instructions'] + "</div>" if rx.get('instructions') else ""}
                    </div>
                    """, unsafe_allow_html=True)

                with col_steps:
                    ms = rx['milestones']
                    st.markdown("**Delivery Steps:**")

                    if not ms['gps_started']:
                        if st.button("📍 Start GPS", key=f"gps_{rx['id']}"):
                            ms['gps_started'] = True
                            st.session_state[exp_key] = True
                            add_activity(f"{driver_name} started GPS for {rx['id']}")
                            time.sleep(0.15)
                            st.rerun()
                    else:
                        st.markdown('<div class="milestone-step milestone-done">✅ GPS Started</div>', unsafe_allow_html=True)

                    if ms['gps_started'] and not ms['photo_captured']:
                        if st.button("📸 Capture Photo", key=f"photo_{rx['id']}"):
                            ms['photo_captured'] = True
                            st.session_state[exp_key] = True
                            add_activity(f"{driver_name} captured photo for {rx['id']}")
                            time.sleep(0.15)
                            st.rerun()
                    elif ms['photo_captured']:
                        st.markdown('<div class="milestone-step milestone-done">✅ Photo Captured</div>', unsafe_allow_html=True)

                    if ms['photo_captured'] and not ms['signature_obtained']:
                        if st.button("✍️ Get Signature", key=f"sig_{rx['id']}"):
                            ms['signature_obtained'] = True
                            st.session_state[exp_key] = True
                            add_activity(f"{driver_name} got signature for {rx['id']}")
                            time.sleep(0.15)
                            st.rerun()
                    elif ms['signature_obtained']:
                        st.markdown('<div class="milestone-step milestone-done">✅ Signature Obtained</div>', unsafe_allow_html=True)

                    if ms['signature_obtained'] and not ms['delivered']:
                        if st.button("🏁 Complete Delivery", key=f"complete_{rx['id']}"):
                            st.session_state[exp_key] = True
                            update_prescription_status(
                                rx['id'], 'delivered',
                                delivered_at=datetime.now().strftime("%Y-%m-%d %H:%M")
                            )
                            ms['delivered'] = True
                            still_active = [r for r in st.session_state.prescriptions
                                            if r['status'] == 'out_for_delivery' and r.get('driver_id') == driver_id]
                            if not still_active and driver_obj:
                                driver_obj['status'] = 'available'
                            add_activity(f"{driver_name} completed delivery of {rx['id']}")
                            time.sleep(0.15)
                            st.rerun()

    with tab2:
        if not completed:
            st.info("No completed deliveries yet.")
        for rx in completed:
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:12px; padding:10px 14px; background:#F0FDF4; border-radius:10px; margin-bottom:6px; border:1px solid #BBF7D0;">
                <span style="font-size:1.2rem;">✅</span>
                <div>
                    <span style="font-weight:600; color:#14532D;">{rx['id']}</span>
                    <span style="color:#166534;"> · {rx['medication']} · {rx['patient_name']}</span>
                    <div style="font-size:0.8rem; color:#4ADE80; margin-top:2px;">🕐 {rx.get('delivered_at','')}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


# =====================================================
# ADMIN DASHBOARD
# =====================================================

def page_admin():
    page_header("📊", "Admin Dashboard", f"Logged in as {st.session_state.user_display_name}", "admin")

    rxs = st.session_state.prescriptions
    drivers = st.session_state.drivers

    active        = [r for r in rxs if r['status'] != 'delivered']
    delivered     = [r for r in rxs if r['status'] == 'delivered']
    avail_drivers = [d for d in drivers if d['status'] == 'available']

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💊 Active Prescriptions", len(active))
    c2.metric("✅ Delivered Today",       len(delivered))
    c3.metric("🚗 Available Drivers",     len(avail_drivers))
    c4.metric("⏱ Avg Delivery Time",      "22 min")

    col_feed, col_stats = st.columns([2, 1])

    with col_feed:
        st.markdown("#### 📡 Live Activity Feed")
        with st.container(height=420):
            if not st.session_state.activity_log:
                st.markdown("""
                <div style="text-align:center; color:#94A3B8; padding:2rem;">
                    No activity yet. Actions across all portals will appear here in real time.
                </div>
                """, unsafe_allow_html=True)
            for entry in reversed(st.session_state.activity_log):
                st.markdown(f'<div class="activity-entry">{entry}</div>', unsafe_allow_html=True)

    with col_stats:
        st.markdown("#### 📈 Status Breakdown")
        status_counts = {
            ('pending',          '⏳', 'Pending',         '#FEF3C7', '#92400E'):  sum(1 for r in rxs if r['status'] == 'pending'),
            ('assigned',         '📋', 'Assigned',        '#FED7AA', '#9A3412'):  sum(1 for r in rxs if r['status'] == 'assigned'),
            ('filling',          '⚗️', 'Filling',         '#DBEAFE', '#1E40AF'):  sum(1 for r in rxs if r['status'] == 'filling'),
            ('ready',            '✅', 'Ready',            '#D1FAE5', '#065F46'):  sum(1 for r in rxs if r['status'] == 'ready'),
            ('out_for_delivery', '🚚', 'Out for Delivery', '#E0E7FF', '#3730A3'):  sum(1 for r in rxs if r['status'] == 'out_for_delivery'),
            ('delivered',        '🏁', 'Delivered',        '#DCFCE7', '#14532D'):  sum(1 for r in rxs if r['status'] == 'delivered'),
        }
        for (_, icon, label, bg, color), count in status_counts.items():
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center;
                        background:{bg}; border-radius:10px; padding:10px 14px; margin-bottom:6px;">
                <span style="font-weight:600; color:{color};">{icon} {label}</span>
                <span style="font-weight:800; color:{color}; font-size:1.2rem;">{count}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 📋 All Prescriptions")
    if not rxs:
        st.info("No prescriptions in the system yet.")
    else:
        for rx in rxs:
            ph_acct = f" · Pharmacy {rx.get('pharmacy_account','—')}" if rx.get('pharmacy_account') else ""
            st.markdown(f"""
            <div style="display:flex; align-items:center; justify-content:space-between;
                        padding:10px 16px; background:white; border:1px solid #E2E8F0;
                        border-radius:10px; margin-bottom:5px;">
                <div>
                    <span style="font-weight:700; color:#0F172A;">{rx['id']}</span>
                    <span style="color:#64748B;"> · {rx['patient_name']} · {rx['medication']}{ph_acct}</span>
                </div>
                {status_pill(rx['status'])}
            </div>
            """, unsafe_allow_html=True)


# =====================================================
# MAIN APP
# =====================================================

def main():
    apply_custom_css()

    if not st.session_state.logged_in:
        login_page()
        return

    role = st.session_state.user_role
    name = st.session_state.user_display_name
    colors = ROLE_COLORS.get(role, ROLE_COLORS["patient"])

    with st.sidebar:
        st.markdown(f"""
        <div class="sidebar-brand">
            <div style="display:flex; justify-content:center; margin-bottom:4px;">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect width="48" height="48" rx="14" fill="url(#sidebarGrad)"/>
                    <defs>
                        <linearGradient id="sidebarGrad" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
                            <stop offset="0%" stop-color="#0EA5E9"/>
                            <stop offset="100%" stop-color="#6366F1"/>
                        </linearGradient>
                    </defs>
                    <rect x="22" y="10" width="4" height="28" rx="2" fill="white"/>
                    <rect x="10" y="22" width="28" height="4" rx="2" fill="white"/>
                </svg>
            </div>
            <div class="sidebar-brand-title">RxPrescribe</div>
            <div class="sidebar-brand-subtitle">Prescription Platform</div>
        </div>
        """, unsafe_allow_html=True)

        initials = "".join(w[0].upper() for w in name.split()[:2])
        st.markdown(f"""
        <div style="
            background: linear-gradient(145deg, #1E293B 0%, #162032 100%);
            border: 1px solid rgba(99,102,241,0.22);
            border-radius: 16px;
            padding: 16px 16px 14px 16px;
            margin-bottom: 1rem;
            box-shadow: 0 4px 18px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.04);
        ">
            <div style="display:flex; align-items:center; gap:12px;">
                <div style="
                    width:44px; height:44px; border-radius:50%;
                    background: {colors['gradient']};
                    display:flex; align-items:center; justify-content:center;
                    font-size:1rem; font-weight:800; color:white;
                    flex-shrink:0;
                    box-shadow: 0 2px 10px {colors['primary']}55;
                ">{initials}</div>
                <div style="min-width:0;">
                    <div style="font-size:0.68rem; color:#475569; text-transform:uppercase;
                                letter-spacing:0.1em; font-weight:600; margin-bottom:2px;">Signed in as</div>
                    <div style="font-weight:700; color:#F1F5F9; font-size:0.92rem;
                                white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{name}</div>
                </div>
            </div>
            <div style="margin-top:12px; padding-top:10px; border-top:1px solid rgba(99,102,241,0.15);">
                <span style="
                    background: {colors['primary']}28;
                    color: {colors['primary']};
                    padding: 3px 12px;
                    border-radius: 99px;
                    font-size: 0.7rem;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 0.07em;
                    border: 1px solid {colors['primary']}40;
                ">{role}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        role_nav = {
            "provider": "👨‍⚕️  Provider Portal",
            "patient":  "👤  Patient Portal",
            "pharmacy": "🏪  Pharmacy Dashboard",
            "driver":   "🚗  Driver App",
            "admin":    "📊  Admin Dashboard",
        }
        st.markdown(f"""
        <div style="background:{colors['primary']}18; border-left:3px solid {colors['primary']};
                    border-radius:0 8px 8px 0; padding:8px 14px; font-weight:600;
                    color:{colors['primary']}; font-size:0.9rem; margin-bottom:1rem;">
            {role_nav.get(role, role)}
        </div>
        """, unsafe_allow_html=True)

        def sign_out():
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.user_role = None
            st.session_state.user_display_name = None

        st.markdown("""
        <div style="
            margin: 1.25rem 0 0.75rem;
            border-top: 1px solid rgba(239,68,68,0.15);
            padding-top: 0.75rem;
        "></div>
        """, unsafe_allow_html=True)
        st.button("→  Sign Out", on_click=sign_out, use_container_width=True)

    if role == "provider":
        page_provider()
    elif role == "patient":
        page_patient()
    elif role == "pharmacy":
        page_pharmacy()
    elif role == "driver":
        page_driver()
    elif role == "admin":
        page_admin()
    else:
        st.error("Unknown role. Please sign out and try again.")


st.set_page_config(
    page_title="RxPrescribe – Prescription Delivery",
    page_icon="⚕️",
    layout="wide",
    initial_sidebar_state="expanded"
)
init_session_state()

if __name__ == "__main__":
    main()
