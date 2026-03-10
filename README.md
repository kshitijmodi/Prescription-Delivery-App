# 💊 Prescription Delivery App

Architected a full-stack prescription delivery platform bringing on-demand delivery infrastructure to medications, with AI-powered smart pharmacy matching, route optimization, and predictive inventory, targeting a $600B market still reliant on phone calls.

---

## 🔍 The Problem

4.9 billion prescriptions are filled annually in the US. Most deliveries still rely on manual scheduling, basic SMS updates, and zero route optimization. Patients manage multiple pharmacy apps with no unified view of their medications. Pharmacies assign drivers manually. There is no intelligent layer connecting providers, pharmacies, drivers, and patients.

While food and e-commerce delivery have been transformed by modern logistics, prescription delivery hasn't caught up.

## 💡 The Solution

Prescription Delivery App is a full-stack platform (B2B SaaS + B2C marketplace) that acts as the intelligent coordination layer for prescription delivery. Think of it as the infrastructure that brought on-demand delivery to food — applied to medications.

---

## ⚡ Key Capabilities

### 🤖 AI-Powered Logistics
- Smart pharmacy matching based on insurance cost, drug availability, proximity, and delivery speed
- Route optimization engine factoring traffic, priority orders, and delivery time windows
- Predictive inventory and demand forecasting for pharmacies

### 📱 Unified Patient Experience
- Single dashboard consolidating prescriptions across all linked pharmacies
- Electronic pharmacy-to-pharmacy transfers (no phone calls)
- Real-time delivery tracking with predictive ETA
- Medication adherence tools and refill reminders

### 🏥 Pharmacy Operations
- Automated insurance verification and prior authorization
- Inbound prescription queue with priority sorting
- Delivery management and driver assignment
- Analytics: fill rates, delivery SLAs, revenue per delivery

### 🩺 Provider Integration
- EHR-integrated e-prescription submission (HL7 FHIR / USCDI)
- Drug interaction checking at point of prescribing
- Patient medication history and adherence visibility

### 🚗 Driver Workflow
- Optimized navigation with turn-by-turn directions
- Identity verification, signature capture, and delivery photo
- Controlled substance enhanced verification (DEA-compliant)

---

## 🧩 Platform Modules

| Module | Description |
|--------|-------------|
| 📱 Patient App | iOS + Android + Web. Unified Rx dashboard, delivery scheduling, real-time tracking |
| 🏥 Pharmacy Dashboard | Order management, inventory forecasting, insurance verification, analytics |
| 🩺 Provider Portal | EHR integration, e-prescribing, patient adherence visibility |
| 🚗 Driver App | Route navigation, ID verification, signature capture, earnings dashboard |
| ⚙️ Admin Dashboard | Fleet management, route optimization, compliance audit trails, reporting |

---

## 🏗️ Architecture

```
Provider (EHR/Portal)
    │
    ▼
┌──────────────────────────────────────┐
│     Prescription Delivery Engine      │
│                                       │
│  📋 Prescription Routing              │
│  🔐 Insurance Verification            │
│  🤖 Smart Pharmacy Matching           │
│  🗺️ Route Optimization (AI)           │
│  📍 Real-Time Tracking                │
│  🛡️ Compliance & Audit Layer          │
└──────┬───────────┬───────────┬───────┘
       │           │           │
       ▼           ▼           ▼
   Pharmacy     Driver      Patient
   Dashboard     App          App
```

### 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit (prototyping), React Native (mobile) |
| AI/ML | Groq API (Llama 3.1-8b-instant) |
| Maps & Logistics | Google Maps API |
| Healthcare Standards | HL7 FHIR, USCDI, Surescripts |
| Insurance | Change Healthcare API |
| Security | HIPAA-compliant, AES-256 encryption, audit logging |

---

## 🔄 Delivery Flow

```
 1. 🩺 Provider creates e-prescription via EHR
 2. 🤖 System routes Rx to optimal pharmacy (location, inventory, cost)
 3. 💳 Automated insurance verification and copay calculation
 4. 🏥 Pharmacy fills, reviews, and packages the order
 5. 📱 Patient selects delivery window via app
 6. 🗺️ AI engine generates optimized delivery route
 7. 🚗 Driver receives order with navigation and patient details
 8. 📍 Patient tracks delivery in real time
 9. 🔐 Driver verifies identity, captures signature and photo
10. ✅ Confirmation sent to all parties; refill reminders scheduled
```

---

## 📊 Market Context

| Metric | Value |
|--------|-------|
| US Prescription Market | $600B |
| Annual Prescriptions Filled | 4.9B |
| E-Prescriptions Shiftable to Delivery | 2.6B |
| Serviceable Addressable Market | $100B (~40K pharmacies) |
| Target Y1 Pharmacies | ~500 |
| Target Y3 Pharmacies | ~6,000 |

---

## 💰 Revenue Model

### B2B (Pharmacy SaaS)
- Subscription tiers per pharmacy location (Basic / Pro / Enterprise)
- 2–5% transaction fee per prescription delivered
- API integration licensing ($0.05–$0.15 per call)
- White-label setup + revenue share

### B2C (Consumer)
- Free tier with minimum order size
- Premium: $9.99/mo (unlimited deliveries, priority)
- Family Plan: $19.99/mo (multiple household members)
- Standard delivery: $2.99–$5.99 | Express: $8.99–$12.99
- Add-ons: adherence tools, caregiver monitoring, Rx sync

---

## 🛡️ Regulatory Compliance

| Domain | Requirements |
|--------|-------------|
| 🔐 HIPAA | BAAs, PHI encryption, audit trails, breach notification |
| 💊 DEA | EPCS compliance, 2FA for controlled substances, chain-of-custody logging |
| 🔗 EHR Interoperability | 21st Century Cures Act, ONC Final Rule, HL7 FHIR |
| 🏛️ State Regulations | 50-state delivery framework mapping |
| 🏥 Medicare/Medicaid | Part D, Advantage Plans, Medicaid formulary support |
| ⚕️ FDA | Clinical decision support classification, 510(k) assessment |

---

## 🗺️ Roadmap

**Phase 1 — Foundation (Months 1–6)**
Core patient, pharmacy, and driver apps. HIPAA infrastructure. Insurance verification API.

**Phase 2 — Intelligence (Months 7–12)**
AI route optimization. Multi-pharmacy linking. Real-time tracking. EHR integration. 3 pilot markets.

**Phase 3 — Scale (Months 13–18)**
White-label B2B. Smart pharmacy routing. Controlled substance workflows. 15+ markets.

**Phase 4 — Moat (Months 19–24)**
Predictive demand forecasting. Medicare/Medicaid integration. API marketplace. National coverage.

---

## 🚀 Getting Started

```bash
# Clone the repository
git clone https://github.com/yourusername/Prescription-Delivery-App.git
cd Prescription-Delivery-App

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Add your API keys: GROQ_API_KEY, GOOGLE_MAPS_API_KEY

# Run the application
streamlit run app.py
```

### 🔑 Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key for AI features |
| `GOOGLE_MAPS_API_KEY` | Google Maps for routing and geocoding |
| `DATABASE_URL` | PostgreSQL connection string |
| `ENCRYPTION_KEY` | AES-256 key for PHI encryption |

---

## 🤝 Contributing

Contributions are welcome. Please open an issue first to discuss proposed changes.

1. Fork the repository
2. Create your branch (`git checkout -b feature/your-feature`)
3. Commit changes (`git commit -m 'Add your feature'`)
4. Push to branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## 📄 License

```
MIT License

Copyright (c) 2026 Kshitij Modi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

Built by [Kshitij Modi](https://github.com/yourusername)
