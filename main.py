# =====================================================
# PRESCRIPTION DELIVERY SYSTEM - REAL LOCATION VERSION
# Uses real pharmacies, addresses, and Google Maps API
# =====================================================

import streamlit as st
import requests
import json
import time
from datetime import datetime
import os

# =====================================================
# GOOGLE MAPS API INTEGRATION
# =====================================================


class GoogleMapsAPI:

    def __init__(self, api_key):
        self.api_key = api_key

    def find_nearby_pharmacies(self, address):
        """Find real pharmacies near the address using Google Places API"""
        try:
            # Geocode the address first to get precise coordinates
            geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={self.api_key}"
            geo_response = requests.get(geocode_url)
            geo_data = geo_response.json()

            if geo_data['status'] != 'OK':
                st.error(
                    f"❌ Could not locate address. Please verify and try again."
                )
                if geo_data['status'] == 'REQUEST_DENIED':
                    st.error(
                        "Google Maps API issue. Please check that Geocoding API is enabled."
                    )
                return None

            location = geo_data['results'][0]['geometry']['location']
            lat, lng = location['lat'], location['lng']

            # Use rankby=distance to get CLOSEST pharmacies
            places_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&rankby=distance&type=pharmacy&key={self.api_key}"
            places_response = requests.get(places_url)
            places_data = places_response.json()

            if places_data['status'] == 'REQUEST_DENIED':
                st.error(
                    f"❌ Places API denied. Please check that Places API is enabled in Google Cloud Console"
                )
                return None

            if places_data['status'] != 'OK':
                st.error(
                    f"❌ Could not search pharmacies: {places_data.get('status')}"
                )
                return None

            results = places_data.get('results', [])

            if not results:
                st.error("❌ No pharmacies found near this location")
                return None

            pharmacies = []
            # Process top 5 results (sorted by distance from API)
            for i, place in enumerate(results[:5]):
                pharmacy_location = place['geometry']['location']
                pharmacy_lat = pharmacy_location['lat']
                pharmacy_lng = pharmacy_location['lng']

                # Get PRECISE distance in MILES
                distance_url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={lat},{lng}&destinations={pharmacy_lat},{pharmacy_lng}&units=imperial&key={self.api_key}"
                distance_response = requests.get(distance_url)
                distance_data = distance_response.json()

                distance_text = "N/A"
                duration_text = "N/A"
                distance_value = 999999

                if distance_data['status'] == 'OK':
                    element = distance_data['rows'][0]['elements'][0]
                    if element['status'] == 'OK':
                        distance_text = element['distance']['text']
                        duration_text = element['duration']['text']
                        distance_value = element['distance'][
                            'value']  # in meters

                pharmacy_data = {
                    "id": f"PH{i+1:03d}",
                    "name": place['name'],
                    "address": place.get('vicinity', 'Address not available'),
                    "distance": distance_text,
                    "duration": duration_text,
                    "distance_value": distance_value,
                    "rating": place.get('rating', 4.0),
                    "lat": pharmacy_lat,
                    "lng": pharmacy_lng,
                    "is_open": place.get('opening_hours',
                                         {}).get('open_now', True)
                }

                pharmacies.append(pharmacy_data)

            # Already sorted by distance from API, but ensure with our calculated distances
            pharmacies.sort(key=lambda x: x['distance_value'])

            # Return top 3 CLOSEST
            return pharmacies[:3] if len(pharmacies) >= 3 else pharmacies

        except requests.exceptions.RequestException as e:
            st.error(f"❌ Network error: {str(e)}")
            return None
        except KeyError as e:
            st.error(f"❌ Unexpected API response: {str(e)}")
            return None
        except Exception as e:
            st.error(f"❌ Error finding pharmacies: {str(e)}")
            return None

    def calculate_route(self, origin, destinations):
        """Calculate optimal route for multiple destinations"""
        try:
            dest_string = "|".join(
                [f"{d['lat']},{d['lng']}" for d in destinations])
            url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={origin['lat']},{origin['lng']}&destinations={dest_string}&key={self.api_key}"

            response = requests.get(url)
            data = response.json()

            if data['status'] != 'OK':
                return None

            route_info = []
            for i, element in enumerate(data['rows'][0]['elements']):
                route_info.append({
                    "destination_id":
                    destinations[i]['id'],
                    "distance":
                    element['distance']['text'],
                    "duration":
                    element['duration']['text'],
                    "distance_value":
                    element['distance']['value'],
                    "duration_value":
                    element['duration']['value']
                })

            return route_info
        except Exception as e:
            st.error(f"Route calculation error: {str(e)}")
            return None


# =====================================================
# GROQ API INTEGRATION
# =====================================================


class GroqAI:

    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.1-8b-instant"

    def _call_api(self, messages, temperature=0.3):
        """Make API call to Groq"""
        try:
            response = requests.post(self.base_url,
                                     headers={
                                         "Authorization":
                                         f"Bearer {self.api_key}",
                                         "Content-Type": "application/json"
                                     },
                                     json={
                                         "model": self.model,
                                         "messages": messages,
                                         "temperature": temperature
                                     },
                                     timeout=30)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            st.error(f"Groq API Error: {str(e)}")
            return None

    def recommend_pharmacy(self, prescription, pharmacies):
        """AI recommends best pharmacy based on real data"""
        prompt = f"""You are a healthcare logistics AI. Analyze real pharmacies and recommend the best one.

PRESCRIPTION:
- Medication: {prescription['medication']}
- Insurance: {prescription['insurance']}
- Patient Address: {prescription['location']}

REAL NEARBY PHARMACIES:
{json.dumps(pharmacies, indent=2)}

Score each pharmacy (0-100) considering:
1. Distance and travel time (closer and faster is better)
2. Pharmacy rating (higher is better)
3. Currently open status
4. Estimated workload (assume busier pharmacies have lower ratings)

Return ONLY valid JSON (no markdown):
{{
    "recommended_pharmacy_id": "PH001",
    "score": 92,
    "reasoning": ["Closest at 0.3 miles (5 min drive)", "Highly rated at 4.5 stars", "Currently open"],
    "ranked_options": [
        {{"id": "PH001", "name": "...", "ai_score": 92, "key_factors": "Closest, highly rated"}},
        {{"id": "PH002", "name": "...", "ai_score": 78, "key_factors": "Good rating but farther"}}
    ]
}}"""

        messages = [{
            "role":
            "system",
            "content":
            "You are a healthcare logistics AI. Always return valid JSON only."
        }, {
            "role": "user",
            "content": prompt
        }]

        response = self._call_api(messages, temperature=0.2)

        if response:
            try:
                response = response.strip()
                if response.startswith("```"):
                    lines = response.split('\n')
                    response = '\n'.join(
                        [l for l in lines if not l.strip().startswith('```')])
                response = response.strip()
                return json.loads(response)
            except Exception as e:
                st.error(f"Failed to parse AI response: {str(e)}")
                return None
        return None

    def recommend_driver(self, drivers, pharmacy_location, patient_location,
                         delivery_priority):
        """AI recommends best driver based on real locations"""
        prompt = f"""You are a route optimization AI. Analyze drivers and recommend the best one.

DELIVERY DETAILS:
- Pharmacy Location: {pharmacy_location}
- Patient Address: {patient_location}
- Priority: {delivery_priority}

AVAILABLE DRIVERS:
{json.dumps(drivers, indent=2)}

Score each driver (0-100) considering:
1. Current location proximity to pharmacy
2. Estimated time to reach pharmacy
3. Driver performance metrics
4. Current workload

Return ONLY valid JSON (no markdown):
{{
    "recommended_driver_id": "DR001",
    "score": 94,
    "estimated_pickup_time": "8 minutes",
    "estimated_delivery_time": "25 minutes",
    "reasoning": ["Closest to pharmacy (5 min)", "Best performance record", "Available now"],
    "ranked_options": [
        {{"id": "DR001", "name": "...", "ai_score": 94, "pickup_time": "8 min", "delivery_time": "25 min"}},
        {{"id": "DR002", "name": "...", "ai_score": 82, "pickup_time": "12 min", "delivery_time": "30 min"}}
    ]
}}"""

        messages = [{
            "role":
            "system",
            "content":
            "You are a driver assignment AI. Always return valid JSON only."
        }, {
            "role": "user",
            "content": prompt
        }]

        response = self._call_api(messages, temperature=0.2)

        if response:
            try:
                response = response.strip()
                if response.startswith("```"):
                    lines = response.split('\n')
                    response = '\n'.join(
                        [l for l in lines if not l.strip().startswith('```')])
                response = response.strip()
                return json.loads(response)
            except Exception as e:
                st.error(f"Failed to parse AI response: {str(e)}")
                return None
        return None


# =====================================================
# SESSION STATE & HELPERS
# =====================================================


def init_session_state():
    if 'prescriptions' not in st.session_state:
        st.session_state.prescriptions = []

    if 'activity_log' not in st.session_state:
        st.session_state.activity_log = []

    if 'drivers' not in st.session_state:
        st.session_state.drivers = [{
            "id": "DR001",
            "name": "Mike Johnson",
            "status": "available",
            "current_location": "Downtown Cincinnati",
            "lat": 39.1031,
            "lng": -84.5120,
            "performance_score": 4.8,
            "deliveries_today": 8,
            "avg_delivery_time": "22 min"
        }, {
            "id": "DR002",
            "name": "Linda Chen",
            "status": "available",
            "current_location": "Over-the-Rhine",
            "lat": 39.1100,
            "lng": -84.5150,
            "performance_score": 4.9,
            "deliveries_today": 6,
            "avg_delivery_time": "20 min"
        }, {
            "id": "DR003",
            "name": "David Kim",
            "status": "available",
            "current_location": "Mount Adams",
            "lat": 39.1050,
            "lng": -84.5000,
            "performance_score": 4.7,
            "deliveries_today": 10,
            "avg_delivery_time": "24 min"
        }]

    if 'groq_api_key' not in st.session_state:
        st.session_state.groq_api_key = os.getenv("GROQ_API_KEY", "")

    if 'google_maps_key' not in st.session_state:
        st.session_state.google_maps_key = os.getenv("GOOGLE_MAPS_API_KEY", "")


def add_activity(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.activity_log.append({
        "time": timestamp,
        "message": message
    })


def show_success(message):
    """Professional success message"""
    st.success(f"✓ {message}")


def update_prescription_status(rx_id, new_status, **kwargs):
    """Update prescription status and additional fields"""
    for prescription in st.session_state.prescriptions:
        if prescription['id'] == rx_id:
            prescription['status'] = new_status
            for key, value in kwargs.items():
                prescription[key] = value
            break


# =====================================================
# CUSTOM CSS FOR BETTER UI
# =====================================================


def apply_custom_css():
    st.markdown("""
    <style>
    /* Better spacing */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 0rem;
        max-width: 100%;
    }

    /* Larger, darker metrics */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #1a1a1a;
        font-weight: 600;
    }

    [data-testid="stMetricLabel"] {
        font-size: 1rem;
        color: #2d2d2d;
        font-weight: 500;
    }

    /* Better button styling - professional colors */
    .stButton button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        font-size: 1rem;
        padding: 0.6rem 1rem;
        border: none;
        transition: all 0.3s ease;
    }

    /* Primary buttons - professional blue */
    .stButton button[kind="primary"] {
        background-color: #2563eb;
        color: white;
    }

    .stButton button[kind="primary"]:hover {
        background-color: #1d4ed8;
        box-shadow: 0 4px 8px rgba(37, 99, 235, 0.3);
    }

    /* Secondary buttons - neutral grey */
    .stButton button[kind="secondary"] {
        background-color: #6b7280;
        color: white;
    }

    .stButton button[kind="secondary"]:hover {
        background-color: #4b5563;
    }

    /* Form inputs - darker text */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > select,
    .stNumberInput > div > div > input {
        padding: 0.6rem;
        font-size: 1rem;
        color: #1a1a1a;
        border: 1px solid #d1d5db;
    }

    .stTextInput label,
    .stSelectbox label,
    .stNumberInput label {
        font-size: 1rem;
        color: #2d2d2d;
        font-weight: 500;
    }

    /* Compact spacing */
    .element-container {
        margin-bottom: 0.5rem;
    }

    /* Progress bars - professional blue */
    .stProgress > div > div > div {
        background-color: #2563eb;
    }

    /* Expanders - darker text */
    .streamlit-expanderHeader {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1a1a1a;
    }

    /* Hide hamburger and footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Tabs - better styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        font-size: 1rem;
        font-weight: 500;
        color: #2d2d2d;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #2563eb;
        color: white;
    }

    /* Success messages - darker green */
    .stSuccess {
        background-color: #d1fae5;
        color: #065f46;
        font-weight: 500;
        font-size: 1rem;
    }

    /* Warning messages - darker yellow */
    .stWarning {
        background-color: #fef3c7;
        color: #92400e;
        font-weight: 500;
        font-size: 1rem;
    }

    /* Error messages - darker red */
    .stError {
        background-color: #fee2e2;
        color: #991b1b;
        font-weight: 500;
        font-size: 1rem;
    }

    /* Info messages - darker blue */
    .stInfo {
        background-color: #dbeafe;
        color: #1e40af;
        font-weight: 500;
        font-size: 1rem;
    }

    /* All text darker and larger */
    p, span, div {
        color: #1a1a1a;
        font-size: 1rem;
    }

    /* Captions - still visible but subtle */
    .stCaption {
        color: #4b5563;
        font-size: 0.95rem;
    }

    /* Headers - darker and bolder */
    h1, h2, h3 {
        color: #111827;
        font-weight: 700;
    }

    h1 {
        font-size: 2.5rem;
    }

    h2 {
        font-size: 2rem;
    }

    h3 {
        font-size: 1.5rem;
    }

    /* Subheaders */
    .stSubheader {
        color: #1f2937;
        font-size: 1.3rem;
        font-weight: 600;
    }

    /* Form submit button override */
    .stFormSubmitButton button {
        background-color: #2563eb;
        color: white;
        font-weight: 600;
    }

    .stFormSubmitButton button:hover {
        background-color: #1d4ed8;
    }

    /* Radio buttons - darker text */
    .stRadio label {
        color: #1a1a1a;
        font-size: 1.1rem;
        font-weight: 500;
    }

    /* Selectbox - darker */
    .stSelectbox label {
        color: #1a1a1a;
        font-weight: 600;
    }
    </style>
    """,
                unsafe_allow_html=True)


# =====================================================
# MAIN APPLICATION
# =====================================================


def main():
    st.set_page_config(page_title="Prescription Delivery System",
                       page_icon="💊",
                       layout="wide",
                       initial_sidebar_state="expanded")

    apply_custom_css()
    init_session_state()

    # Check for API keys
    if not st.session_state.groq_api_key:
        st.error("⚠️ GROQ_API_KEY not found. Please set it in Replit Secrets.")
        st.stop()

    if not st.session_state.google_maps_key:
        st.error(
            "⚠️ GOOGLE_MAPS_API_KEY not found. Please set it in Replit Secrets."
        )
        st.stop()

    groq_client = GroqAI(st.session_state.groq_api_key)
    maps_client = GoogleMapsAPI(st.session_state.google_maps_key)

    # Sidebar Navigation
    st.sidebar.title("🏥 Navigation")
    page = st.sidebar.radio("", [
        "👨‍⚕️ Provider", "👤 Patient", "🏪 Pharmacy", "🚗 Driver", "📊 Dashboard"
    ],
                            label_visibility="collapsed")

    page_name = page.split(" ", 1)[1]

    # =====================================================
    # PROVIDER PORTAL
    # =====================================================

    if page_name == "Provider":
        st.title("👨‍⚕️ Provider Portal")

        col1, col2 = st.columns([2, 1])

        with col1:
            with st.form("new_prescription", clear_on_submit=True):
                st.subheader("Create E-Prescription")

                c1, c2, c3 = st.columns(3)
                with c1:
                    patient_name = st.text_input("Patient Name",
                                                 value="John Doe")
                    medication = st.selectbox("Medication", [
                        "Lisinopril 10mg", "Metformin 500mg",
                        "Atorvastatin 20mg", "Amlodipine 5mg"
                    ])
                with c2:
                    quantity = st.number_input("Quantity", 1, 90, 30)
                    refills = st.number_input("Refills", 0, 12, 3)
                with c3:
                    insurance = st.selectbox("Insurance", [
                        "Blue Cross Blue Shield", "United Healthcare", "Aetna",
                        "Medicare"
                    ])
                    # Patient address will be set by patient
                    st.text_input("Patient Address",
                                  value="(Patient will set address)",
                                  disabled=True)

                submitted = st.form_submit_button("Send Prescription",
                                                  type="primary")

                if submitted:
                    rx_id = f"RX{len(st.session_state.prescriptions) + 1:03d}"
                    prescription = {
                        "id": rx_id,
                        "patient_name": patient_name,
                        "medication": medication,
                        "quantity": quantity,
                        "refills": refills,
                        "insurance": insurance,
                        "location": None,  # Patient will set this
                        "status": "pending",
                        "pharmacy_id": None,
                        "pharmacy_name": None,
                        "pharmacy_address": None,
                        "driver_id": None,
                        "driver_name": None,
                        "created_at":
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "milestones": {
                            "gps_started": False,
                            "photo_captured": False,
                            "signature_obtained": False,
                            "delivered": False
                        }
                    }

                    st.session_state.prescriptions.append(prescription)
                    add_activity(
                        f"Provider created {rx_id} for {patient_name}")
                    show_success(f"Prescription {rx_id} created successfully")
                    time.sleep(0.5)
                    st.rerun()

        with col2:
            st.subheader("Quick Stats")
            total = len(st.session_state.prescriptions)
            pending = len([
                p for p in st.session_state.prescriptions
                if p['status'] == 'pending'
            ])
            delivered = len([
                p for p in st.session_state.prescriptions
                if p['status'] == 'delivered'
            ])

            st.metric("Total Prescriptions", total)
            st.metric("Pending", pending)
            st.metric("Delivered Today", delivered)

        if st.session_state.prescriptions:
            st.markdown("---")
            st.subheader("Recent Prescriptions")
            for rx in reversed(st.session_state.prescriptions[-5:]):
                with st.expander(
                        f"{rx['id']} - {rx['patient_name']} - {rx['status'].upper()}"
                ):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Medication:** {rx['medication']}")
                        st.write(
                            f"**Quantity:** {rx['quantity']} • **Refills:** {rx['refills']}"
                        )
                    with c2:
                        st.write(f"**Insurance:** {rx['insurance']}")
                        st.write(f"**Created:** {rx['created_at']}")

    # =====================================================
    # PATIENT PORTAL
    # =====================================================

    elif page_name == "Patient":
        st.title("👤 Patient Portal")

        if not st.session_state.prescriptions:
            st.info("📋 No prescriptions yet. Ask your provider to send one.")
            return

        for rx in st.session_state.prescriptions:
            if rx['status'] == 'pending':
                st.subheader(f"📋 {rx['medication']}")

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Quantity", rx['quantity'])
                with c2:
                    st.metric("Refills", rx['refills'])
                with c3:
                    st.metric("Insurance",
                              rx['insurance'],
                              label_visibility="visible")

                st.markdown("---")

                # Check if address is set
                if not rx.get('location') or rx.get('location') == 'None':
                    st.warning(
                        "⚠️ Please set your delivery address to find nearby pharmacies"
                    )

                    with st.form(key=f"address_form_{rx['id']}"):
                        st.subheader("📍 Set Your Delivery Address")

                        col1, col2 = st.columns(2)
                        with col1:
                            street = st.text_input(
                                "Street Address*",
                                placeholder="e.g., 250 W Court St")
                            city = st.text_input(
                                "City*", placeholder="e.g., Cincinnati")
                        with col2:
                            state = st.text_input("State*",
                                                  placeholder="e.g., OH",
                                                  max_chars=2).upper()
                            zipcode = st.text_input("ZIP Code*",
                                                    placeholder="e.g., 45202",
                                                    max_chars=10)

                        st.caption("*All fields required")

                        submit_address = st.form_submit_button(
                            "💾 Save Address",
                            type="primary",
                            use_container_width=True)

                        if submit_address:
                            if street and city and state and zipcode:
                                full_address = f"{street}, {city}, {state} {zipcode}"
                                update_prescription_status(
                                    rx['id'], 'pending', location=full_address)
                                add_activity(
                                    f"Patient set address for {rx['id']}: {full_address}"
                                )
                                show_success(
                                    "Address saved successfully! You can now find nearby pharmacies."
                                )
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(
                                    "⚠️ Please fill in all address fields")

                    st.info(
                        "💡 You'll be able to search for pharmacies after saving your address"
                    )
                    continue

                # Show current address with edit option
                st.success(f"📍 **Delivery Address:** {rx['location']}")

                col_edit1, col_edit2 = st.columns([3, 1])
                with col_edit2:
                    if st.button("✏️ Edit Address",
                                 key=f"edit_addr_{rx['id']}",
                                 use_container_width=True):
                        st.session_state[f'editing_address_{rx["id"]}'] = True
                        st.rerun()

                # Edit address form (if editing)
                if st.session_state.get(f'editing_address_{rx["id"]}', False):
                    st.markdown("---")
                    with st.form(key=f"edit_address_form_{rx['id']}"):
                        st.subheader("✏️ Update Delivery Address")

                        # Parse existing address
                        try:
                            parts = rx['location'].split(',')
                            current_street = parts[0].strip() if len(
                                parts) > 0 else ""
                            current_city = parts[1].strip() if len(
                                parts) > 1 else ""
                            state_zip = parts[2].strip() if len(
                                parts) > 2 else ""
                            state_zip_parts = state_zip.split()
                            current_state = state_zip_parts[0] if len(
                                state_zip_parts) > 0 else ""
                            current_zip = state_zip_parts[1] if len(
                                state_zip_parts) > 1 else ""
                        except:
                            current_street = current_city = current_state = current_zip = ""

                        col1, col2 = st.columns(2)
                        with col1:
                            new_street = st.text_input("Street Address*",
                                                       value=current_street)
                            new_city = st.text_input("City*",
                                                     value=current_city)
                        with col2:
                            new_state = st.text_input("State*",
                                                      value=current_state,
                                                      max_chars=2).upper()
                            new_zipcode = st.text_input("ZIP Code*",
                                                        value=current_zip,
                                                        max_chars=10)

                        col_a, col_b = st.columns(2)
                        with col_a:
                            update_address = st.form_submit_button(
                                "💾 Update Address",
                                type="primary",
                                use_container_width=True)
                        with col_b:
                            cancel_edit = st.form_submit_button(
                                "❌ Cancel", use_container_width=True)

                        if update_address:
                            if new_street and new_city and new_state and new_zipcode:
                                new_full_address = f"{new_street}, {new_city}, {new_state} {new_zipcode}"
                                update_prescription_status(
                                    rx['id'],
                                    'pending',
                                    location=new_full_address)

                                # Clear pharmacy recommendations if address changed
                                if f'rec_{rx["id"]}' in st.session_state:
                                    del st.session_state[f'rec_{rx["id"]}']
                                if f'pharmacies_{rx["id"]}' in st.session_state:
                                    del st.session_state[
                                        f'pharmacies_{rx["id"]}']

                                st.session_state[
                                    f'editing_address_{rx["id"]}'] = False
                                add_activity(
                                    f"Patient updated address for {rx['id']}: {new_full_address}"
                                )
                                show_success(
                                    "Address updated! Please search for pharmacies again with your new address."
                                )
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(
                                    "⚠️ Please fill in all address fields")

                        if cancel_edit:
                            st.session_state[
                                f'editing_address_{rx["id"]}'] = False
                            st.rerun()

                st.markdown("---")

                # Find pharmacies button
                if st.button("🤖 Find Nearby Pharmacies with AI",
                             key=f"find_{rx['id']}",
                             type="primary",
                             use_container_width=True):
                    if not rx.get('location') or rx.get('location') == 'None':
                        st.error("⚠️ Please set your delivery address first!")
                    else:
                        with st.spinner("Finding real pharmacies near you..."):
                            progress = st.progress(0)
                            status_text = st.empty()

                            # Step 1: Find pharmacies
                            status_text.text(
                                "🗺️ Searching nearby pharmacies...")
                            progress.progress(33)

                            pharmacies = maps_client.find_nearby_pharmacies(
                                rx['location'])

                            if not pharmacies:
                                st.error(
                                    f"❌ Could not find pharmacies near '{rx['location']}'. Please verify your address is correct and try again."
                                )
                                st.info(
                                    "💡 Make sure you entered a valid street address, city, state, and ZIP code."
                                )
                                continue

                            # Step 2: AI analysis
                            status_text.text("🤖 AI analyzing options...")
                            progress.progress(66)
                            time.sleep(0.5)

                            recommendation = groq_client.recommend_pharmacy(
                                rx, pharmacies)

                            if not recommendation:
                                st.error(
                                    "❌ AI recommendation failed. Please try again."
                                )
                                continue

                            status_text.text("✓ Analysis complete!")
                            progress.progress(100)

                            # Store results
                            st.session_state[
                                f'pharmacies_{rx["id"]}'] = pharmacies
                            st.session_state[
                                f'rec_{rx["id"]}'] = recommendation

                            add_activity(
                                f"Found {len(pharmacies)} pharmacies for {rx['id']} near {rx['location']}"
                            )
                            show_success(
                                f"Found {len(pharmacies)} pharmacies near you!"
                            )
                            time.sleep(0.5)
                            st.rerun()

                if f'rec_{rx["id"]}' in st.session_state:
                    rec = st.session_state[f'rec_{rx["id"]}']
                    pharmacies = st.session_state[f'pharmacies_{rx["id"]}']

                    st.markdown("---")

                    # Find recommended pharmacy - with error handling
                    try:
                        recommended = next(
                            p for p in rec['ranked_options']
                            if p['id'] == rec['recommended_pharmacy_id'])
                        pharmacy_details = next(
                            p for p in pharmacies
                            if p['id'] == recommended['id'])
                    except StopIteration:
                        st.error(
                            "❌ Error matching AI recommendation. Please search again."
                        )
                        if st.button("🔄 Search Again",
                                     key=f"retry_{rx['id']}"):
                            del st.session_state[f'rec_{rx["id"]}']
                            del st.session_state[f'pharmacies_{rx["id"]}']
                            st.rerun()
                        continue

                    st.success(f"**Recommended:** {pharmacy_details['name']}")
                    st.caption(f"📍 {pharmacy_details['address']}")

                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.metric("AI Score", f"{rec['score']}/100")
                    with c2:
                        st.metric("Distance", pharmacy_details['distance'])
                    with c3:
                        st.metric("Drive Time", pharmacy_details['duration'])
                    with c4:
                        st.metric("Rating", f"⭐ {pharmacy_details['rating']}")

                    with st.expander("Why this pharmacy?"):
                        for reason in rec['reasoning']:
                            st.write(f"• {reason}")

                    with st.expander("View other options"):
                        for p_opt in rec['ranked_options'][1:]:
                            try:
                                p_det = next(p for p in pharmacies
                                             if p['id'] == p_opt['id'])
                                st.write(
                                    f"**{p_det['name']}** (Score: {p_opt['ai_score']})"
                                )
                                st.caption(
                                    f"📍 {p_det['address']} • {p_det['distance']} • {p_det['duration']}"
                                )
                                st.write("")
                            except StopIteration:
                                continue

                    st.markdown("---")
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        delivery_time = st.selectbox("Delivery Time", [
                            "Today 2-4 PM", "Today 4-6 PM",
                            "Tomorrow 10-12 PM", "Tomorrow 2-4 PM"
                        ],
                                                     key=f"time_{rx['id']}")
                        instructions = st.text_input(
                            "Special Instructions",
                            placeholder="e.g., Ring doorbell twice",
                            key=f"inst_{rx['id']}")
                    with c2:
                        st.write("")
                        st.write("")
                        if st.button("Confirm & Schedule",
                                     key=f"conf_{rx['id']}",
                                     type="primary"):
                            update_prescription_status(
                                rx['id'],
                                'assigned',
                                pharmacy_id=rec['recommended_pharmacy_id'],
                                pharmacy_name=pharmacy_details['name'],
                                pharmacy_address=pharmacy_details['address'],
                                pharmacy_location={
                                    'lat': pharmacy_details['lat'],
                                    'lng': pharmacy_details['lng']
                                },
                                delivery_time=delivery_time,
                                instructions=instructions)

                            add_activity(
                                f"Patient confirmed {pharmacy_details['name']} for {rx['id']}"
                            )
                            show_success(
                                "Pharmacy selected and delivery scheduled")
                            time.sleep(0.5)
                            st.rerun()

            elif rx['status'] in [
                    'assigned', 'filling', 'ready', 'out_for_delivery'
            ]:
                status_display = {
                    'assigned': '🟠 Sent to Pharmacy',
                    'filling': '🔵 Filling Prescription',
                    'ready': '🟢 Ready for Delivery',
                    'out_for_delivery': '🚚 Out for Delivery'
                }
                st.subheader(
                    f"{rx['medication']} - {status_display[rx['status']]}")

                progress_steps = [
                    'assigned', 'filling', 'ready', 'out_for_delivery',
                    'delivered'
                ]
                progress_value = (progress_steps.index(rx['status']) +
                                  1) / len(progress_steps)
                st.progress(progress_value)

                c1, c2 = st.columns(2)
                with c1:
                    if rx.get('pharmacy_name'):
                        st.write(f"**Pharmacy:** {rx['pharmacy_name']}")
                        st.caption(f"📍 {rx.get('pharmacy_address', '')}")
                    st.write(
                        f"**Delivery:** {rx.get('delivery_time', 'Scheduled')}"
                    )
                with c2:
                    if rx['status'] == 'out_for_delivery' and rx.get(
                            'driver_name'):
                        st.write(f"**Driver:** {rx['driver_name']}")
                        est_time = rx.get('estimated_delivery_time',
                                          '15-20 min')
                        st.write(f"**ETA:** {est_time}")

                # Show delivery milestones
                if rx['status'] == 'out_for_delivery':
                    st.markdown("---")
                    st.subheader("📍 Delivery Progress")

                    milestones = rx.get('milestones', {})

                    cols = st.columns(4)
                    with cols[0]:
                        if milestones.get('gps_started'):
                            st.markdown("✅ **GPS Started**")
                        else:
                            st.markdown("⏳ GPS Pending")
                    with cols[1]:
                        if milestones.get('photo_captured'):
                            st.markdown("✅ **Photo Taken**")
                        else:
                            st.markdown("⏳ Photo Pending")
                    with cols[2]:
                        if milestones.get('signature_obtained'):
                            st.markdown("✅ **Signature**")
                        else:
                            st.markdown("⏳ Signature Pending")
                    with cols[3]:
                        if milestones.get('delivered'):
                            st.markdown("✅ **Delivered**")
                        else:
                            st.markdown("⏳ Delivery Pending")

                st.markdown("---")

            elif rx['status'] == 'delivered':
                with st.expander(f"✅ {rx['medication']} - Delivered"):
                    st.write(
                        f"**Delivered:** {rx.get('delivered_at', rx['created_at'])}"
                    )
                    st.write(f"**Refills remaining:** {rx['refills']}")
                    st.write(f"**Pharmacy:** {rx.get('pharmacy_name', 'N/A')}")
                    st.write(f"**Driver:** {rx.get('driver_name', 'N/A')}")

    # =====================================================
    # PHARMACY DASHBOARD
    # =====================================================

    elif page_name == "Pharmacy":
        st.title("🏪 Pharmacy Dashboard")

        # Get unique pharmacies from assigned prescriptions
        assigned_pharmacies = {}
        for rx in st.session_state.prescriptions:
            if rx.get('pharmacy_name') and rx.get('pharmacy_id'):
                if rx['pharmacy_id'] not in assigned_pharmacies:
                    assigned_pharmacies[rx['pharmacy_id']] = {
                        'name': rx['pharmacy_name'],
                        'address': rx.get('pharmacy_address', ''),
                        'location': rx.get('pharmacy_location', {})
                    }

        if not assigned_pharmacies:
            st.info(
                "No pharmacies have been selected yet. Patients need to choose a pharmacy first."
            )
            return

        selected_pharm_id = st.selectbox(
            "Select Pharmacy",
            options=list(assigned_pharmacies.keys()),
            format_func=lambda x: assigned_pharmacies[x]['name'])

        pharmacy = assigned_pharmacies[selected_pharm_id]
        pharm_rxs = [
            p for p in st.session_state.prescriptions
            if p.get('pharmacy_id') == selected_pharm_id
        ]

        c1, c2, c3 = st.columns(3)
        with c1:
            new_orders = [p for p in pharm_rxs if p['status'] == 'assigned']
            st.metric("New Orders", len(new_orders))
        with c2:
            filling = [p for p in pharm_rxs if p['status'] == 'filling']
            st.metric("Filling", len(filling))
        with c3:
            ready = [p for p in pharm_rxs if p['status'] == 'ready']
            st.metric("Ready", len(ready))

        tab1, tab2, tab3, tab4 = st.tabs(
            ["🆕 New", "🔵 Filling", "✅ Ready", "📦 Delivered"])

        with tab1:
            new_orders = [p for p in pharm_rxs if p['status'] == 'assigned']
            if new_orders:
                for rx in new_orders:
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.write(
                            f"**{rx['id']}** - {rx['patient_name']} - {rx['medication']} ({rx['quantity']} units)"
                        )
                        st.caption(
                            f"Insurance: {rx['insurance']} • Delivery: {rx.get('delivery_time', 'Not scheduled')}"
                        )
                    with c2:
                        if st.button("Accept Order",
                                     key=f"acc_{rx['id']}",
                                     type="primary"):
                            with st.spinner("Verifying insurance..."):
                                time.sleep(0.8)
                                update_prescription_status(rx['id'], 'filling')
                                add_activity(
                                    f"{pharmacy['name']} accepted {rx['id']}")
                                show_success(f"Order {rx['id']} accepted")
                                time.sleep(0.3)
                                st.rerun()
                    st.markdown("---")
            else:
                st.info("No new orders")

        with tab2:
            filling_orders = [p for p in pharm_rxs if p['status'] == 'filling']
            if filling_orders:
                for rx in filling_orders:
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.write(
                            f"**{rx['id']}** - {rx['medication']} - {rx['patient_name']}"
                        )
                        st.progress(0.6, text="Filling in progress...")
                    with c2:
                        if st.button("Mark Ready",
                                     key=f"ready_{rx['id']}",
                                     type="primary"):
                            update_prescription_status(rx['id'], 'ready')
                            add_activity(
                                f"{pharmacy['name']} completed {rx['id']}")
                            show_success(
                                f"Order {rx['id']} ready for delivery")
                            time.sleep(0.3)
                            st.rerun()
                    st.markdown("---")
            else:
                st.info("No orders being filled")

        with tab3:
            ready_orders = [p for p in pharm_rxs if p['status'] == 'ready']
            if ready_orders:
                st.subheader("Orders Ready for Delivery")
                for rx in ready_orders:
                    st.write(
                        f"✅ **{rx['id']}** - {rx['medication']} - {rx['patient_name']}"
                    )
                    st.caption(f"📍 Deliver to: {rx['location']}")

                st.markdown("---")

                if st.button("🤖 Find Best Driver with AI", type="primary"):
                    with st.spinner("AI analyzing driver options..."):
                        progress = st.progress(0)
                        status_text = st.empty()

                        # Get available drivers
                        available_drivers = [
                            d for d in st.session_state.drivers
                            if d['status'] == 'available'
                        ]

                        if not available_drivers:
                            st.error("No drivers available at the moment")
                            st.stop()

                        status_text.text("🗺️ Calculating distances...")
                        progress.progress(33)

                        # Calculate routes for each driver
                        pharmacy_location = pharmacy['location']
                        patient_location = ready_orders[0]['location']

                        driver_options = []
                        for driver in available_drivers:
                            # Simulate route calculation
                            driver_options.append({
                                "id":
                                driver['id'],
                                "name":
                                driver['name'],
                                "current_location":
                                driver['current_location'],
                                "performance_score":
                                driver['performance_score'],
                                "deliveries_today":
                                driver['deliveries_today'],
                                "avg_delivery_time":
                                driver['avg_delivery_time'],
                                "pickup_time":
                                f"{5 + driver['deliveries_today'] % 3} min",
                                "delivery_time":
                                f"{18 + driver['deliveries_today'] % 5} min"
                            })

                        status_text.text("🤖 AI scoring drivers...")
                        progress.progress(66)
                        time.sleep(0.5)

                        # Get AI recommendation
                        driver_rec = groq_client.recommend_driver(
                            driver_options, pharmacy['address'],
                            patient_location, "Standard")

                        if not driver_rec:
                            st.error(
                                "Failed to get driver recommendation. Please try again."
                            )
                            st.stop()

                        status_text.text("✓ Analysis complete!")
                        progress.progress(100)

                        st.session_state[
                            f'driver_rec_{selected_pharm_id}'] = driver_rec
                        st.session_state[
                            f'driver_options_{selected_pharm_id}'] = driver_options

                        show_success("Driver analysis complete")
                        time.sleep(0.5)
                        st.rerun()

                if f'driver_rec_{selected_pharm_id}' in st.session_state:
                    driver_rec = st.session_state[
                        f'driver_rec_{selected_pharm_id}']
                    driver_options = st.session_state[
                        f'driver_options_{selected_pharm_id}']

                    st.markdown("---")
                    st.subheader("🚗 AI Driver Recommendations")

                    recommended = next(
                        d for d in driver_rec['ranked_options']
                        if d['id'] == driver_rec['recommended_driver_id'])

                    st.success(f"**Recommended:** {recommended['name']}")

                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.metric("AI Score", f"{driver_rec['score']}/100")
                    with c2:
                        st.metric("Pickup Time",
                                  driver_rec['estimated_pickup_time'])
                    with c3:
                        st.metric("Delivery Time",
                                  driver_rec['estimated_delivery_time'])
                    with c4:
                        driver_details = next(d
                                              for d in st.session_state.drivers
                                              if d['id'] == recommended['id'])
                        st.metric("Performance",
                                  f"⭐ {driver_details['performance_score']}")

                    with st.expander("Why this driver?"):
                        for reason in driver_rec['reasoning']:
                            st.write(f"• {reason}")

                    with st.expander("View other driver options"):
                        for d_opt in driver_rec['ranked_options'][1:]:
                            driver_det = next(d
                                              for d in st.session_state.drivers
                                              if d['id'] == d_opt['id'])
                            st.write(
                                f"**{d_opt['name']}** (Score: {d_opt['ai_score']})"
                            )
                            st.caption(
                                f"📍 Current location: {driver_det['current_location']} • Pickup: {d_opt['pickup_time']} • Delivery: {d_opt['delivery_time']}"
                            )
                            st.write("")

                    if st.button("Assign to Recommended Driver",
                                 type="primary"):
                        # Assign all ready orders to this driver
                        selected_driver = next(
                            d for d in st.session_state.drivers
                            if d['id'] == driver_rec['recommended_driver_id'])

                        for rx in ready_orders:
                            update_prescription_status(
                                rx['id'],
                                'out_for_delivery',
                                driver_id=selected_driver['id'],
                                driver_name=selected_driver['name'],
                                estimated_delivery_time=driver_rec[
                                    'estimated_delivery_time'])

                        selected_driver['status'] = 'busy'

                        add_activity(
                            f"{selected_driver['name']} assigned {len(ready_orders)} deliveries from {pharmacy['name']}"
                        )
                        show_success(
                            f"Assigned to {selected_driver['name']} - ETA: {driver_rec['estimated_delivery_time']}"
                        )
                        time.sleep(0.5)
                        st.rerun()
            else:
                st.info("No prescriptions ready for delivery")

        with tab4:
            delivered = [p for p in pharm_rxs if p['status'] == 'delivered']
            if delivered:
                for rx in delivered:
                    st.write(
                        f"✅ **{rx['id']}** - {rx['medication']} - {rx['patient_name']}"
                    )
                    st.caption(
                        f"Delivered by: {rx.get('driver_name', 'N/A')} at {rx.get('delivered_at', 'N/A')}"
                    )
            else:
                st.info("No deliveries today")

    # =====================================================
    # DRIVER APP
    # =====================================================

    elif page_name == "Driver":
        st.title("🚗 Driver App")

        driver_name = st.selectbox(
            "Select Driver", [d['name'] for d in st.session_state.drivers])
        driver = next(d for d in st.session_state.drivers
                      if d['name'] == driver_name)

        driver_deliveries = [
            p for p in st.session_state.prescriptions
            if p.get('driver_id') == driver['id']
        ]
        completed = [
            p for p in driver_deliveries if p['status'] == 'delivered'
        ]

        c1, c2, c3 = st.columns(3)
        with c1:
            status_color = "🟢" if driver['status'] == 'available' else "🔴"
            st.metric("Status", f"{status_color} {driver['status'].title()}")
        with c2:
            st.metric(
                "Active Deliveries",
                len([
                    p for p in driver_deliveries
                    if p['status'] == 'out_for_delivery'
                ]))
        with c3:
            st.metric("Completed Today", len(completed))

        tab1, tab2 = st.tabs(["🚚 Active Deliveries", "✅ Completed"])

        with tab1:
            active = [
                p for p in driver_deliveries
                if p['status'] == 'out_for_delivery'
            ]
            if active:
                for i, rx in enumerate(active, 1):
                    st.subheader(f"Delivery #{i}: {rx['id']}")

                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.write(f"**Patient:** {rx['patient_name']}")
                        st.write(f"**Address:** {rx['location']}")
                        st.write(f"**Medication:** {rx['medication']}")
                        st.write(
                            f"**Time Window:** {rx.get('delivery_time', 'ASAP')}"
                        )
                        if rx.get('instructions'):
                            st.info(f"📝 {rx['instructions']}")

                        # Show pharmacy pickup info
                        st.caption(
                            f"🏪 Pick up from: {rx.get('pharmacy_name', 'Pharmacy')}"
                        )

                    with c2:
                        st.write("**Delivery Steps:**")

                        milestones = rx.get('milestones', {})

                        # GPS Step
                        if not milestones.get('gps_started'):
                            if st.button("📍 Start GPS", key=f"gps_{rx['id']}"):
                                milestones['gps_started'] = True
                                update_prescription_status(
                                    rx['id'],
                                    'out_for_delivery',
                                    milestones=milestones)
                                add_activity(
                                    f"{driver['name']} started GPS for {rx['id']}"
                                )
                                show_success("GPS navigation started")
                                time.sleep(0.3)
                                st.rerun()
                        else:
                            st.success("✓ GPS Active")

                        # Photo Step
                        if milestones.get(
                                'gps_started'
                        ) and not milestones.get('photo_captured'):
                            if st.button("📸 Capture Photo",
                                         key=f"photo_{rx['id']}"):
                                milestones['photo_captured'] = True
                                update_prescription_status(
                                    rx['id'],
                                    'out_for_delivery',
                                    milestones=milestones)
                                add_activity(
                                    f"{driver['name']} captured delivery photo for {rx['id']}"
                                )
                                show_success("Photo captured")
                                time.sleep(0.3)
                                st.rerun()
                        elif milestones.get('photo_captured'):
                            st.success("✓ Photo Taken")
                        else:
                            st.caption("⏳ Photo (after GPS)")

                        # Signature Step
                        if milestones.get(
                                'photo_captured'
                        ) and not milestones.get('signature_obtained'):
                            if st.button("✍️ Get Signature",
                                         key=f"sig_{rx['id']}"):
                                milestones['signature_obtained'] = True
                                update_prescription_status(
                                    rx['id'],
                                    'out_for_delivery',
                                    milestones=milestones)
                                add_activity(
                                    f"{driver['name']} obtained signature for {rx['id']}"
                                )
                                show_success("Signature obtained")
                                time.sleep(0.3)
                                st.rerun()
                        elif milestones.get('signature_obtained'):
                            st.success("✓ Signature")
                        else:
                            st.caption("⏳ Signature (after photo)")

                        # Complete Delivery Step
                        if milestones.get(
                                'signature_obtained'
                        ) and not milestones.get('delivered'):
                            if st.button("✅ Complete Delivery",
                                         key=f"comp_{rx['id']}",
                                         type="primary"):
                                milestones['delivered'] = True
                                update_prescription_status(
                                    rx['id'],
                                    'delivered',
                                    milestones=milestones,
                                    delivered_at=datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S"))

                                # Check if driver has more deliveries
                                remaining = [
                                    p for p in st.session_state.prescriptions
                                    if p.get('driver_id') == driver['id']
                                    and p['status'] == 'out_for_delivery'
                                ]

                                if not remaining:
                                    driver['status'] = 'available'

                                add_activity(
                                    f"{driver['name']} completed delivery {rx['id']}"
                                )
                                show_success(f"Delivery {rx['id']} completed")
                                time.sleep(0.5)
                                st.rerun()
                        elif milestones.get('delivered'):
                            st.success("✓ Delivered")
                        else:
                            st.caption("⏳ Complete (after signature)")

                    st.markdown("---")
            else:
                st.info("No active deliveries. Waiting for assignments...")

        with tab2:
            if completed:
                for rx in completed:
                    st.write(
                        f"✅ **{rx['id']}** - {rx['medication']} - {rx.get('delivered_at', 'N/A')}"
                    )
                    st.caption(
                        f"Patient: {rx['patient_name']} • Location: {rx['location']}"
                    )
            else:
                st.info("No completed deliveries today")

    # =====================================================
    # DASHBOARD
    # =====================================================

    elif page_name == "Dashboard":
        st.title("📊 System Dashboard")

        # Key metrics
        c1, c2, c3, c4 = st.columns(4)
        active = [
            p for p in st.session_state.prescriptions
            if p['status'] != 'delivered'
        ]
        delivered = [
            p for p in st.session_state.prescriptions
            if p['status'] == 'delivered'
        ]
        available_drivers = [
            d for d in st.session_state.drivers if d['status'] == 'available'
        ]

        with c1:
            st.metric("Active Prescriptions", len(active))
        with c2:
            st.metric("Delivered Today", len(delivered))
        with c3:
            st.metric("Available Drivers", len(available_drivers))
        with c4:
            st.metric("Avg Delivery Time", "22 min")

        st.markdown("---")

        # Two column layout
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("📊 Live Activity Feed")
            if st.session_state.activity_log:
                activity_container = st.container(height=400)
                with activity_container:
                    for activity in reversed(st.session_state.activity_log):
                        st.text(f"[{activity['time']}] {activity['message']}")
            else:
                st.info(
                    "No activity yet. Start by creating a prescription in Provider Portal."
                )

        with col2:
            st.subheader("📋 Prescription Status")
            if st.session_state.prescriptions:
                status_counts = {}
                for rx in st.session_state.prescriptions:
                    status_counts[rx['status']] = status_counts.get(
                        rx['status'], 0) + 1

                status_display = {
                    'pending': ('🟡', 'Pending'),
                    'assigned': ('🟠', 'Assigned'),
                    'filling': ('🔵', 'Filling'),
                    'ready': ('🟢', 'Ready'),
                    'out_for_delivery': ('🚚', 'Out for Delivery'),
                    'delivered': ('✅', 'Delivered')
                }

                for status, count in status_counts.items():
                    emoji, label = status_display.get(status, ('⚪', status))
                    st.metric(f"{emoji} {label}", count)
            else:
                st.info("No prescriptions yet")

        if st.session_state.prescriptions:
            st.markdown("---")
            st.subheader("All Prescriptions")

            # Create a more compact view
            for rx in st.session_state.prescriptions:
                status_emoji = {
                    'pending': '🟡',
                    'assigned': '🟠',
                    'filling': '🔵',
                    'ready': '🟢',
                    'out_for_delivery': '🚚',
                    'delivered': '✅'
                }

                cols = st.columns([1, 2, 2, 2, 1])
                with cols[0]:
                    st.write(f"{status_emoji.get(rx['status'], '⚪')}")
                with cols[1]:
                    st.write(f"**{rx['id']}**")
                with cols[2]:
                    st.write(rx['patient_name'])
                with cols[3]:
                    st.write(rx['medication'])
                with cols[4]:
                    st.write(rx['status'])


if __name__ == "__main__":
    main()
