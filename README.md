---
title: RxPrescribe
emoji: ⚕️
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.40.0
app_file: main.py
pinned: false
---

# 💊 Prescription Delivery App

A full-stack prescription delivery platform with AI-powered pharmacy matching, real-time driver assignment, and a multi-role login system — targeting the $600B US prescription market.

---

## 🔐 Demo Login Credentials

| Role | Username | Password |
|------|----------|----------|
| 👨‍⚕️ Provider | `provider` | `rx2024` |
| 👤 Patient – John Doe | `john_doe` | `pass123` |
| 👤 Patient – Sarah Smith | `sarah_smith` | `pass123` |
| 👤 Patient – Michael Chen | `michael_chen` | `pass123` |
| 👤 Patient – Emily Davis | `emily_davis` | `pass123` |
| 👤 Patient – Robert Jones | `robert_jones` | `pass123` |
| 🏪 Pharmacy 1 – Downtown | `pharmacy1` | `pharma1` |
| 🏪 Pharmacy 2 – Midtown | `pharmacy2` | `pharma2` |
| 🚗 Driver – Mike Johnson | `mike_j` | `drive1` |
| 🚗 Driver – Linda Chen | `linda_c` | `drive1` |
| 🚗 Driver – David Kim | `david_k` | `drive1` |
| 📊 Admin | `admin` | `admin1` |

---

## 🔍 The Problem

4.9 billion prescriptions are filled annually in the US. Most deliveries still rely on manual scheduling, basic SMS updates, and zero route optimization. Patients manage multiple pharmacy apps with no unified view. Pharmacies assign drivers manually. There is no intelligent layer connecting providers, pharmacies, drivers, and patients.

## 💡 The Solution

Prescription Delivery App is a full-stack platform that acts as the intelligent coordination layer for prescription delivery — bringing on-demand logistics infrastructure to medications.

---

## ⚡ Key Features

### 🔐 Multi-Role Login System
- Separate portals for Provider, Patients (5), Pharmacies (2), Drivers (3), and Admin
- Each user sees only their relevant data — full role-based access control
- Pharmacy 2 only receives prescriptions when a patient's AI recommendation selects a second distinct pharmacy location

### 🤖 AI-Powered Logistics
- Smart pharmacy matching via Groq AI (Llama 3.1-8b) based on distance, rating, and availability
- Intelligent driver assignment scoring proximity, workload, and performance
- Ranked recommendations with human-readable reasoning

### 🗺️ Google Maps Integration
- Real-time geocoding of patient addresses
- Nearest pharmacy discovery via Google Places API
- Driving distance and duration via Distance Matrix API

### 📱 End-to-End Workflow
- Provider creates e-prescription with patient dropdown (5 fixed patients)
- Patient sets delivery address and confirms AI-recommended pharmacy
- Pharmacy accepts, fills, and dispatches via AI driver selection
- Driver completes 4-step milestone workflow: GPS → Photo → Signature → Delivery
- Admin monitors live activity feed and full prescription pipeline

---

## 🔄 Prescription Lifecycle

```
PENDING → ASSIGNED → FILLING → READY → OUT FOR DELIVERY → DELIVERED
```

| Status | Who Acts |
|--------|----------|
| Pending | Provider creates Rx; Patient sets address & selects pharmacy |
| Assigned | Pharmacy receives and accepts order |
| Filling | Pharmacy fills and marks ready |
| Ready | Pharmacy runs AI driver selection |
| Out for Delivery | Driver completes GPS → Photo → Signature → Deliver |
| Delivered | Confirmation logged for all parties |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit |
| AI / Recommendations | Groq API (Llama 3.1-8b-instant) |
| Maps & Logistics | Google Maps API (Geocoding, Places, Distance Matrix) |
| Deployment | Hugging Face Spaces (auto-synced from GitHub Actions) |

---

## 🚀 Getting Started

```bash
git clone https://github.com/kshitijmodi/Prescription-Delivery-App.git
cd Prescription-Delivery-App
pip install -r requirements.txt

# Set environment variables
export GROQ_API_KEY=your_groq_key
export GOOGLE_MAPS_API_KEY=your_maps_key

streamlit run main.py
```

### 🔑 Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key for AI recommendations |
| `GOOGLE_MAPS_API_KEY` | Google Maps for routing and pharmacy search |

---

## 📄 License

MIT License — Copyright (c) 2026 Kshitij Modi

---

Built by [Kshitij Modi](https://github.com/kshitijmodi)
