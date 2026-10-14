# 🏛️ Ontario LTB Intelligence & Tenant Screening Hub

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live-emerald)](https://madgetr.github.io/ltb-data-hub/)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-amber?logo=buy-me-a-coffee)](https://buymeacoffee.com/madgetr)

An open-source, automated data intelligence dashboard and batch tenant screening platform built on official **Ontario Landlord and Tenant Board (LTB)** public order records.

🔗 **Live Hub:** [https://madgetr.github.io/ltb-data-hub/](https://madgetr.github.io/ltb-data-hub/)

---

## 🌟 Overview

Navigating publicly available Ontario LTB records can be cumbersome and fragmented. This hub automatically aggregates, cleans, geocodes, and parses official Ontario open data records to provide housing providers, property managers, and independent landlords with actionable insights:

* **Batch Tenant Screening:** Instantly screen lists of rental applicants against public LTB order records to uncover past eviction filings, non-payment claims, or property damage disputes.
* **Parsed Order Judgment Amounts:** Automated extraction of monetary order summaries (arrears, compensation, damages) directly from order PDFs (e.g., L1/L9/L10 applications).
* **Geospatial & Radius Search:** Search orders interactively within a specified distance (km) of any target location in Ontario.
* **Fast Data Explorer:** Full client-side searching, sorting, and multi-field filtering across tens of thousands of official records.

---

## ✨ Key Features

- **⚡ Fast Multi-Threaded Data Pipeline:** Python engine using high-concurrency PDF text stream parsing to process thousands of orders in seconds.
- **📍 Municipal Geocoding:** Automatically maps records to Ontario municipal coordinates for spatial visualization.
- **🔍 Smart Tenant Screening Engine:** Cleans, deduplicates, and aggregates applicant lists with immediate **CLEAR** vs. **FLAGGED** statuses, breakdown of application types, and claim totals.
- **📱 Fully Mobile Responsive:** Adapted for seamless usability across desktop, tablet, and mobile devices (with adaptive table-to-card UI).
- **☕ Open Source & Free:** Built as a public utility to bring clarity and accessibility to rental market data.

---

## 🚀 Architecture & Tech Stack

* **Frontend:** Single-Page Application (SPA) built with **HTML5**, **Tailwind CSS**, **Vanilla JS**, and **Leaflet.js** for interactive maps.
* **Data Processing & Pipeline:** **Python 3** using `requests`, `pypdf`, and `concurrent.futures` for high-throughput multi-threaded extraction.
* **CI/CD & Automation:** **GitHub Actions** running daily data fetch and build pipelines deployed straight to **GitHub Pages**.


```

ltb-data-hub/
├── data/
│   └── ltb_orders.json          # Processed & geocoded order records
├── scripts/
│   └── fetch_data.py            # Main multi-threaded ingest & parsing script
├── index.html                   # Mobile-responsive frontend dashboard
├── frontend/
│   └── index.html               # Redirect page for legacy URLs
├── canadacities.csv             # Geocoding reference data for Ontario
└── README.md

```

---

## 🛠️ Local Development & Setup

### Prerequisites
* Python 3.9+
* `pip`

### 1. Clone the Repository
```bash
git clone [https://github.com/madgetr/ltb-data-hub.git](https://github.com/madgetr/ltb-data-hub.git)
cd ltb-data-hub

```

### 2. Install Dependencies

```bash
pip install requests pypdf

```

### 3. Run Data Ingestion Pipeline

To fetch the latest records from the Ontario Open Data Portal and parse PDFs locally:

```bash
python scripts/fetch_data.py

```

### 4. Serve the Dashboard Locally

Start a lightweight HTTP server to view the frontend in your browser:

```bash
python -m http.server 8000

```

Open **`http://localhost:8000`** in your browser.

---

## ☕ Support the Project

This project is open-source and free to use. If you find this tool helpful in saving time or screening applicants for your properties, consider supporting ongoing hosting, geocoding API usage, and pipeline maintenance:

---

## 📄 License

This project is licensed under the [MIT License](https://www.google.com/search?q=LICENSE). Data sourced from the official Ontario Open Data Portal under the Open Government Licence – Ontario.
