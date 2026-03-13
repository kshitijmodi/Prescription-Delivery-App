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
    # Provider
    "provider": {
        "password": "rx2024",
        "role": "provider",
        "name": "Dr. James Wilson"
    },
    # Patients
    "john_doe":     {"password": "pass123", "role": "patient", "name": "John Doe"},
    "sarah_smith":  {"password": "pass123", "role": "patient", "name": "Sarah Smith"},
    "michael_chen": {"password": "pass123", "role": "patient", "name": "Michael Chen"},
    "emily_davis":  {"password": "pass123", "role": "patient", "name": "Emily Davis"},
    "robert_jones": {"password": "pass123", "role": "patient", "name": "Robert Jones"},
    # Pharmacies
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
    # Drivers
    "mike_j":   {"password": "drive1", "role": "driver", "name": "Mike Johnson",  "driver_id": "DR001"},
    "linda_c":  {"password": "drive1", "role": "driver", "name": "Linda Chen",    "driver_id": "DR002"},
    "david_k":  {"password": "drive1", "role": "driver", "name": "David Kim",     "driver_id": "DR003"},
    # Admin
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
    # Login state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'user_display_name' not in st.session_state:
        st.session_state.user_display_name = None
    # Pharmacy name → account mapping (first distinct name = 1, second = 2)
    if 'pharmacy_name_to_account' not in st.session_state:
        st.session_state.pharmacy_name_to_account = {}


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
    """Map a real pharmacy name to account 1 or 2 for the demo."""
    mapping = st.session_state.pharmacy_name_to_account
    if pharmacy_name not in mapping:
        if len(mapping) == 0:
            mapping[pharmacy_name] = 1
        elif len(mapping) == 1:
            mapping[pharmacy_name] = 2
        else:
            # Any additional pharmacies go to account 2
            mapping[pharmacy_name] = 2
    return mapping[pharmacy_name]


def apply_custom_css():
    st.markdown("""
    <style>
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stButton > button:hover { background-color: #1d4ed8; color: white; }
    .success-msg { background: #d1fae5; padding: 12px 16px; border-radius: 8px;
                   border-left: 4px solid #10b981; color: #065f46; margin: 8px 0; }
    .warning-msg { background: #fef3c7; padding: 12px 16px; border-radius: 8px;
                   border-left: 4px solid #f59e0b; color: #92400e; margin: 8px 0; }
    .info-msg    { background: #dbeafe; padding: 12px 16px; border-radius: 8px;
                   border-left: 4px solid #3b82f6; color: #1e40af; margin: 8px 0; }
    .login-container { max-width: 420px; margin: 60px auto; padding: 40px;
                       background: white; border-radius: 16px;
                       box-shadow: 0 4px 24px rgba(0,0,0,0.08); }
    </style>
    """, unsafe_allow_html=True)


# =====================================================
# LOGIN PAGE
# =====================================================

def login_page():
    st.markdown("""
    <div style='text-align:center; padding: 40px 0 20px 0;'>
        <h1 style='font-size:2.2rem; color:#2563eb;'>💊 Prescription Delivery</h1>
        <p style='color:#6b7280; font-size:1rem;'>Sign in to your account</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

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

        st.markdown("---")
        st.markdown("**Demo Credentials**")

        with st.expander("View all logins"):
            st.markdown("""
| Role | Username | Password |
|------|----------|----------|
| Provider | `provider` | `rx2024` |
| Patient – John Doe | `john_doe` | `pass123` |
| Patient – Sarah Smith | `sarah_smith` | `pass123` |
| Patient – Michael Chen | `michael_chen` | `pass123` |
| Patient – Emily Davis | `emily_davis` | `pass123` |
| Patient – Robert Jones | `robert_jones` | `pass123` |
| Pharmacy 1 | `pharmacy1` | `pharma1` |
| Pharmacy 2 | `pharmacy2` | `pharma2` |
| Driver – Mike Johnson | `mike_j` | `drive1` |
| Driver – Linda Chen | `linda_c` | `drive1` |
| Driver – David Kim | `david_k` | `drive1` |
| Admin | `admin` | `admin1` |
""")


# =====================================================
# PROVIDER PORTAL
# =====================================================

def page_provider():
    st.title("👨‍⚕️ Provider Portal")
    st.caption(f"Logged in as {st.session_state.user_display_name}")

    with st.form("rx_form"):
        st.subheader("Create E-Prescription")
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

        submitted = st.form_submit_button("Send Prescription", use_container_width=True)

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
        add_activity(f"Provider created {rx_id} for {patient_name} – {medication}")
        st.success(f"✅ Prescription {rx_id} sent to {patient_name}")

    # Stats
    st.markdown("---")
    total = len(st.session_state.prescriptions)
    pending = sum(1 for r in st.session_state.prescriptions if r['status'] == 'pending')
    delivered = sum(1 for r in st.session_state.prescriptions if r['status'] == 'delivered')
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Prescriptions", total)
    c2.metric("Pending", pending)
    c3.metric("Delivered Today", delivered)

    # Recent prescriptions
    st.subheader("All Prescriptions")
    if not st.session_state.prescriptions:
        st.info("No prescriptions created yet.")
    for rx in reversed(st.session_state.prescriptions[-10:]):
        with st.expander(f"{rx['id']} – {rx['patient_name']} – {rx['medication']} [{rx['status'].upper()}]"):
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Qty:** {rx['quantity']}")
            c2.write(f"**Refills:** {rx['refills']}")
            c3.write(f"**Insurance:** {rx['insurance']}")
            st.caption(f"Created: {rx['created_at']}")


# =====================================================
# PATIENT PORTAL
# =====================================================

def page_patient():
    patient_name = st.session_state.user_display_name
    st.title(f"👤 Patient Portal")
    st.caption(f"Logged in as {patient_name}")

    my_rxs = [r for r in st.session_state.prescriptions if r['patient_name'] == patient_name]

    if not my_rxs:
        st.info("No prescriptions have been sent to you yet by your provider.")
        return

    maps_key = st.session_state.google_maps_api_key
    groq_key = st.session_state.groq_api_key

    for rx in my_rxs:
        st.markdown("---")
        with st.container():
            st.subheader(f"{rx['id']} – {rx['medication']}")

            # ── ADDRESS SETUP ──────────────────────────────────────
            if rx['status'] == 'pending':
                if not rx['location']:
                    st.markdown("**Set your delivery address to continue:**")
                    with st.form(f"addr_{rx['id']}"):
                        c1, c2 = st.columns(2)
                        street = c1.text_input("Street Address")
                        city   = c2.text_input("City")
                        c3, c4 = st.columns(2)
                        state  = c3.text_input("State")
                        zipcode = c4.text_input("ZIP Code")
                        if st.form_submit_button("Save Address"):
                            if all([street, city, state, zipcode]):
                                full_address = f"{street}, {city}, {state} {zipcode}"
                                rx['location'] = full_address
                                rx.pop('pharmacy_recommendations', None)
                                add_activity(f"{patient_name} set address for {rx['id']}")
                                st.rerun()
                            else:
                                st.error("All fields are required.")
                else:
                    # Show address + edit option
                    col_addr, col_edit = st.columns([3, 1])
                    col_addr.markdown(f"📍 **Delivery Address:** {rx['location']}")
                    if col_edit.button("✏️ Edit", key=f"edit_addr_{rx['id']}"):
                        rx['_editing_address'] = True
                        st.rerun()

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
                            if sc1.form_submit_button("Update"):
                                if all([street, city, state, zipcode]):
                                    rx['location'] = f"{street}, {city}, {state} {zipcode}"
                                    rx.pop('_editing_address', None)
                                    rx.pop('pharmacy_recommendations', None)
                                    st.rerun()
                            if sc2.form_submit_button("Cancel"):
                                rx.pop('_editing_address', None)
                                st.rerun()

                    # ── PHARMACY SEARCH ────────────────────────────
                    if rx['location'] and not rx.get('pharmacy_confirmed'):
                        if not maps_key or not groq_key:
                            st.error("⚠️ API keys are not configured. An admin must add GOOGLE_MAPS_API_KEY and GROQ_API_KEY as environment secrets in the HF Space settings.")
                        elif st.button(f"🤖 Find Nearby Pharmacies with AI", key=f"find_ph_{rx['id']}"):
                            if True:
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
                                        status.update(label="Done!", state="complete")
                                        st.rerun()

                        if rx.get('pharmacy_recommendations'):
                            data = rx['pharmacy_recommendations']
                            rec  = data['recommendation']
                            phs  = data['pharmacies']
                            rec_id = rec.get('recommended_id')
                            rec_ph = next((p for p in phs if p['id'] == rec_id), phs[0])

                            st.markdown("#### 🏆 Recommended Pharmacy")
                            st.markdown(f"**{rec_ph['name']}**  \n📍 {rec_ph['address']}")
                            m1, m2, m3, m4 = st.columns(4)
                            m1.metric("AI Score", f"{rec.get('score', 'N/A')}/100")
                            m2.metric("Distance", f"{rec_ph['distance_miles']} mi")
                            m3.metric("Drive Time", rec_ph['drive_time'])
                            m4.metric("Rating", f"⭐ {rec_ph['rating']}")

                            with st.expander("Why this pharmacy?"):
                                for r in rec.get('reasoning', []):
                                    st.write(f"• {r}")
                            with st.expander("View other options"):
                                for opt in rec.get('ranked_options', []):
                                    st.write(f"**#{rec.get('ranked_options',[]).index(opt)+1} {opt.get('name','')}** — Score: {opt.get('score','N/A')} — {opt.get('summary','')}")

                            # ── CONFIRM & SCHEDULE ─────────────────
                            st.markdown("#### 📅 Schedule Delivery")
                            with st.form(f"schedule_{rx['id']}"):
                                delivery_time = st.selectbox("Delivery Window", [
                                    "Today 2–4 PM", "Today 4–6 PM",
                                    "Tomorrow 10 AM–12 PM", "Tomorrow 2–4 PM"
                                ])
                                instructions = st.text_input("Special Instructions (optional)")
                                if st.form_submit_button("✅ Confirm & Schedule"):
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
                                    st.rerun()

            # ── IN-TRANSIT TRACKING ────────────────────────────────
            elif rx['status'] in ['assigned', 'filling', 'ready', 'out_for_delivery']:
                status_map = {
                    'assigned': ('🟠 Assigned to Pharmacy', 25),
                    'filling':  ('🔵 Being Filled', 50),
                    'ready':    ('🟢 Ready for Pickup', 75),
                    'out_for_delivery': ('🚚 Out for Delivery', 90),
                }
                label, progress = status_map[rx['status']]
                st.markdown(f"**Status:** {label}")
                st.progress(progress)

                c1, c2 = st.columns(2)
                c1.markdown(f"**Pharmacy:** {rx.get('pharmacy_name', '—')}")
                c1.markdown(f"📍 {rx.get('pharmacy_address', '—')}")
                c2.markdown(f"**Delivery Window:** {rx.get('delivery_time', '—')}")

                if rx['status'] == 'out_for_delivery':
                    st.markdown(f"🚗 **Driver:** {rx.get('driver_name', '—')}")
                    st.markdown(f"⏱ **ETA:** {rx.get('estimated_delivery_time', 'Calculating...')}")

                ms = rx.get('milestones', {})
                st.markdown("**Delivery Milestones:**")
                steps = [
                    ("GPS Started",        ms.get('gps_started')),
                    ("Photo Taken",        ms.get('photo_captured')),
                    ("Signature Obtained", ms.get('signature_obtained')),
                    ("Delivered",          ms.get('delivered')),
                ]
                for label_m, done in steps:
                    icon = "✅" if done else "⬜"
                    st.write(f"{icon} {label_m}")

            # ── DELIVERED ─────────────────────────────────────────
            elif rx['status'] == 'delivered':
                with st.expander(f"✅ Delivered – {rx.get('delivered_at', '')}"):
                    st.write(f"**Pharmacy:** {rx.get('pharmacy_name', '—')}")
                    st.write(f"**Driver:** {rx.get('driver_name', '—')}")
                    st.write(f"**Refills Remaining:** {rx['refills']}")


# =====================================================
# PHARMACY DASHBOARD
# =====================================================

def page_pharmacy():
    user = USERS[st.session_state.username]
    pharmacy_account = user['pharmacy_id']
    pharmacy_label   = user['name']

    st.title(f"🏪 {pharmacy_label}")
    st.caption(f"Logged in as {st.session_state.user_display_name}")

    # Filter prescriptions belonging to this pharmacy account
    my_rxs = [r for r in st.session_state.prescriptions if r.get('pharmacy_account') == pharmacy_account]

    assigned = [r for r in my_rxs if r['status'] == 'assigned']
    filling  = [r for r in my_rxs if r['status'] == 'filling']
    ready    = [r for r in my_rxs if r['status'] == 'ready']
    delivered_today = [r for r in my_rxs if r['status'] == 'delivered']

    c1, c2, c3 = st.columns(3)
    c1.metric("New Orders",  len(assigned))
    c2.metric("Filling",     len(filling))
    c3.metric("Ready",       len(ready))

    if pharmacy_account == 2 and not my_rxs:
        st.info("No prescriptions assigned to this pharmacy yet. Prescriptions appear here when a patient's AI recommendation selects a second pharmacy location.")
        return

    tab1, tab2, tab3, tab4 = st.tabs(["📥 New Orders", "⚗️ Filling", "✅ Ready", "📦 Delivered"])

    with tab1:
        if not assigned:
            st.info("No new orders.")
        for rx in assigned:
            with st.expander(f"{rx['id']} – {rx['patient_name']} – {rx['medication']}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Qty:** {rx['quantity']}")
                c2.write(f"**Insurance:** {rx['insurance']}")
                c3.write(f"**Window:** {rx.get('delivery_time','—')}")
                if rx.get('instructions'):
                    st.write(f"**Instructions:** {rx['instructions']}")
                if st.button(f"Accept Order", key=f"accept_{rx['id']}"):
                    with st.spinner("Verifying insurance..."):
                        time.sleep(0.8)
                    update_prescription_status(rx['id'], 'filling')
                    st.rerun()

    with tab2:
        if not filling:
            st.info("No prescriptions being filled.")
        for rx in filling:
            with st.expander(f"{rx['id']} – {rx['patient_name']} – {rx['medication']}"):
                st.progress(60, text="Filling in progress... 60%")
                if st.button(f"Mark Ready", key=f"ready_{rx['id']}"):
                    update_prescription_status(rx['id'], 'ready')
                    st.rerun()

    with tab3:
        if not ready:
            st.info("No prescriptions ready for pickup.")

        groq_key = st.session_state.groq_api_key
        maps_key = st.session_state.google_maps_api_key

        for rx in ready:
            with st.expander(f"{rx['id']} – {rx['patient_name']} – {rx['medication']}"):
                st.write(f"📍 Patient: {rx.get('location','—')}")

                if st.button(f"🤖 Find Best Driver with AI", key=f"find_drv_{rx['id']}"):
                    avail = [d for d in st.session_state.drivers if d['status'] == 'available']
                    if not avail:
                        st.warning("No drivers available right now.")
                    elif not groq_key:
                        st.error("Groq API key not configured.")
                    else:
                        with st.spinner("Finding best driver..."):
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
                        st.rerun()

                if rx.get('driver_recommendation'):
                    rec = rx['driver_recommendation']
                    rec_id = rec.get('recommended_driver_id')
                    rec_drv = next((d for d in st.session_state.drivers if d['id'] == rec_id), None)

                    if rec_drv:
                        st.success(f"🏆 Recommended: **{rec_drv['name']}**")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("AI Score", f"{rec.get('score','N/A')}/100")
                        m2.metric("Pickup ETA", f"{rec.get('estimated_pickup_minutes','?')} min")
                        m3.metric("Delivery ETA", f"{rec.get('estimated_delivery_minutes','?')} min")
                        m4.metric("Rating", f"⭐ {rec_drv['rating']}")

                        st.markdown("**Why this driver:**")
                        for r in rec.get('reasoning', []):
                            st.write(f"• {r}")
                        st.markdown("**Other options:**")
                        for opt in rec.get('ranked_options', []):
                            st.write(f"**{opt.get('name','')}** — Score: {opt.get('score','N/A')} — {opt.get('summary','')}")

                        if st.button(f"Assign to {rec_drv['name']}", key=f"assign_{rx['id']}"):
                            eta = f"~{rec.get('estimated_delivery_minutes', 30)} min"
                            # Assign all ready prescriptions for this pharmacy
                            for r in ready:
                                update_prescription_status(
                                    r['id'], 'out_for_delivery',
                                    driver_id=rec_id,
                                    driver_name=rec_drv['name'],
                                    estimated_delivery_time=eta
                                )
                            # Mark driver busy
                            for d in st.session_state.drivers:
                                if d['id'] == rec_id:
                                    d['status'] = 'busy'
                                    break
                            add_activity(f"Driver {rec_drv['name']} assigned to pharmacy account {pharmacy_account}")
                            st.rerun()

    with tab4:
        if not delivered_today:
            st.info("No deliveries completed yet.")
        for rx in delivered_today:
            st.write(f"✅ **{rx['id']}** – {rx['patient_name']} – {rx['medication']} – Driver: {rx.get('driver_name','—')} – {rx.get('delivered_at','')}")


# =====================================================
# DRIVER APP
# =====================================================

def page_driver():
    user = USERS[st.session_state.username]
    driver_id   = user['driver_id']
    driver_name = user['name']

    st.title(f"🚗 Driver App")
    st.caption(f"Logged in as {driver_name}")

    driver_obj = next((d for d in st.session_state.drivers if d['id'] == driver_id), None)

    active    = [r for r in st.session_state.prescriptions if r['status'] == 'out_for_delivery' and r.get('driver_id') == driver_id]
    completed = [r for r in st.session_state.prescriptions if r['status'] == 'delivered' and r.get('driver_id') == driver_id]

    c1, c2, c3 = st.columns(3)
    status_label = "🟢 Available" if driver_obj and driver_obj['status'] == 'available' else "🔴 Busy"
    c1.metric("Status",            status_label)
    c2.metric("Active Deliveries", len(active))
    c3.metric("Completed Today",   len(completed))

    tab1, tab2 = st.tabs(["🚚 Active Deliveries", "✅ Completed"])

    with tab1:
        if not active:
            st.info("No active deliveries assigned to you.")
        for rx in active:
            with st.expander(f"{rx['id']} – {rx['patient_name']} – {rx['medication']}"):
                col_info, col_steps = st.columns([1.2, 1])

                with col_info:
                    st.write(f"**Patient:** {rx['patient_name']}")
                    st.write(f"**Address:** {rx.get('location','—')}")
                    st.write(f"**Medication:** {rx['medication']}")
                    st.write(f"**Window:** {rx.get('delivery_time','—')}")
                    if rx.get('instructions'):
                        st.write(f"**Instructions:** {rx['instructions']}")
                    st.write(f"**Pickup Pharmacy:** {rx.get('pharmacy_name','—')}")

                with col_steps:
                    ms = rx['milestones']
                    st.markdown("**Delivery Steps:**")

                    if not ms['gps_started']:
                        if st.button("📍 Start GPS", key=f"gps_{rx['id']}"):
                            ms['gps_started'] = True
                            add_activity(f"{driver_name} started GPS for {rx['id']}")
                            st.rerun()
                    else:
                        st.success("✅ GPS Started")

                    if ms['gps_started'] and not ms['photo_captured']:
                        if st.button("📸 Capture Photo", key=f"photo_{rx['id']}"):
                            ms['photo_captured'] = True
                            add_activity(f"{driver_name} captured photo for {rx['id']}")
                            st.rerun()
                    elif ms['photo_captured']:
                        st.success("✅ Photo Captured")

                    if ms['photo_captured'] and not ms['signature_obtained']:
                        if st.button("✍️ Get Signature", key=f"sig_{rx['id']}"):
                            ms['signature_obtained'] = True
                            add_activity(f"{driver_name} got signature for {rx['id']}")
                            st.rerun()
                    elif ms['signature_obtained']:
                        st.success("✅ Signature Obtained")

                    if ms['signature_obtained'] and not ms['delivered']:
                        if st.button("🏁 Complete Delivery", key=f"complete_{rx['id']}"):
                            update_prescription_status(
                                rx['id'], 'delivered',
                                delivered_at=datetime.now().strftime("%Y-%m-%d %H:%M")
                            )
                            ms['delivered'] = True
                            # Check if driver has remaining deliveries
                            still_active = [r for r in st.session_state.prescriptions
                                            if r['status'] == 'out_for_delivery' and r.get('driver_id') == driver_id]
                            if not still_active and driver_obj:
                                driver_obj['status'] = 'available'
                            add_activity(f"{driver_name} completed delivery of {rx['id']}")
                            st.rerun()

    with tab2:
        if not completed:
            st.info("No completed deliveries.")
        for rx in completed:
            st.write(f"✅ **{rx['id']}** – {rx['medication']} – {rx['patient_name']} – {rx.get('delivered_at','')}")


# =====================================================
# ADMIN DASHBOARD
# =====================================================

def page_admin():
    st.title("📊 Admin Dashboard")
    st.caption(f"Logged in as {st.session_state.user_display_name}")

    rxs = st.session_state.prescriptions
    drivers = st.session_state.drivers

    active    = [r for r in rxs if r['status'] != 'delivered']
    delivered = [r for r in rxs if r['status'] == 'delivered']
    avail_drivers = [d for d in drivers if d['status'] == 'available']

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Prescriptions", len(active))
    c2.metric("Delivered Today",      len(delivered))
    c3.metric("Available Drivers",    len(avail_drivers))
    c4.metric("Avg Delivery Time",    "22 min")

    col_feed, col_stats = st.columns([2, 1])

    with col_feed:
        st.subheader("Live Activity Feed")
        with st.container(height=400):
            if not st.session_state.activity_log:
                st.info("No activity yet.")
            for entry in reversed(st.session_state.activity_log):
                st.text(entry)

    with col_stats:
        st.subheader("Status Summary")
        status_counts = {
            '🟡 Pending':         sum(1 for r in rxs if r['status'] == 'pending'),
            '🟠 Assigned':        sum(1 for r in rxs if r['status'] == 'assigned'),
            '🔵 Filling':         sum(1 for r in rxs if r['status'] == 'filling'),
            '🟢 Ready':           sum(1 for r in rxs if r['status'] == 'ready'),
            '🚚 Out for Delivery': sum(1 for r in rxs if r['status'] == 'out_for_delivery'),
            '✅ Delivered':        sum(1 for r in rxs if r['status'] == 'delivered'),
        }
        for label, count in status_counts.items():
            st.metric(label, count)

    st.markdown("---")
    st.subheader("All Prescriptions")
    if not rxs:
        st.info("No prescriptions in the system yet.")
    else:
        for rx in rxs:
            status_icons = {
                'pending': '🟡', 'assigned': '🟠', 'filling': '🔵',
                'ready': '🟢', 'out_for_delivery': '🚚', 'delivered': '✅'
            }
            icon = status_icons.get(rx['status'], '⬜')
            ph_acct = f" | Pharmacy {rx.get('pharmacy_account','—')}" if rx.get('pharmacy_account') else ""
            st.write(f"{icon} **{rx['id']}** – {rx['patient_name']} – {rx['medication']} – `{rx['status']}`{ph_acct}")


# =====================================================
# MAIN APP
# =====================================================

def main():
    st.set_page_config(
        page_title="Prescription Delivery",
        page_icon="💊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    apply_custom_css()
    init_session_state()

    # ── Show login if not authenticated ──
    if not st.session_state.logged_in:
        login_page()
        return

    role = st.session_state.user_role
    name = st.session_state.user_display_name

    # ── Sidebar ──
    with st.sidebar:
        st.markdown(f"**{name}**")
        st.caption(f"Role: {role.capitalize()}")
        st.markdown("---")

        if role == "provider":
            st.markdown("👨‍⚕️ Provider Portal")
        elif role == "patient":
            st.markdown("👤 Patient Portal")
        elif role == "pharmacy":
            st.markdown("🏪 Pharmacy Dashboard")
        elif role == "driver":
            st.markdown("🚗 Driver App")
        elif role == "admin":
            st.markdown("📊 Admin Dashboard")

        st.markdown("---")
        if st.button("🚪 Sign Out"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.user_role = None
            st.session_state.user_display_name = None
            st.rerun()

    # ── Route to correct page ──
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


if __name__ == "__main__":
    main()
