"""
Generates dummy listings_leads and listings_credits datasets and saves them as CSV.
Run once: python dummy_data.py
"""
import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)

AGENTS = [
    ("AGT001", "Sarah Al Mansoori", "Betterhomes"),
    ("AGT002", "James Mitchell", "Espace Real Estate"),
    ("AGT003", "Fatima Hassan", "Allsopp & Allsopp"),
    ("AGT004", "Raj Patel", "Driven Properties"),
    ("AGT005", "Emma Clarke", "Dubizzle Property"),
    ("AGT006", "Mohammed Al Rashid", "Provident Estate"),
    ("AGT007", "Priya Nair", "Hamptons International"),
    ("AGT008", "Tom Reynolds", "Knight Frank"),
    ("AGT009", "Aisha Al Zaabi", "CBRE"),
    ("AGT010", "Carlos Mendez", "Savills"),
]

COMMUNITIES = {
    "Dubai": [
        "Dubai Marina", "Downtown Dubai", "Palm Jumeirah", "Business Bay",
        "Jumeirah Village Circle", "Arabian Ranches", "DIFC", "JBR",
        "Emirates Hills", "Meydan City",
    ],
    "Abu Dhabi": [
        "Yas Island", "Saadiyat Island", "Al Reem Island", "Khalifa City",
        "Al Maryah Island",
    ],
    "Sharjah": [
        "Al Majaz", "Al Nahda", "Muwailih Commercial",
    ],
}

PROPERTY_TYPES = ["Apartment", "Villa", "Townhouse", "Penthouse", "Studio"]
LEAD_SOURCES = ["PropertyFinder", "Bayut", "Direct Call", "Referral", "Walk-in"]
LEAD_STATUSES = ["New", "Contacted", "Qualified", "Converted", "Lost"]
CREDIT_TYPES = ["Featured", "Premium Listing", "Refresh", "Hot Property", "Boost"]


def random_date(start_days_ago=180):
    return (datetime.now() - timedelta(days=random.randint(0, start_days_ago))).strftime("%Y-%m-%d")


def build_listings(n=300):
    listings = []
    for i in range(1, n + 1):
        emirate = random.choice(list(COMMUNITIES.keys()))
        community = random.choice(COMMUNITIES[emirate])
        prop_type = random.choice(PROPERTY_TYPES)
        agent = random.choice(AGENTS)
        beds = random.choice([0, 1, 2, 3, 4, 5]) if prop_type != "Studio" else 0
        base_price = {"Apartment": 800_000, "Villa": 3_000_000, "Townhouse": 1_800_000,
                      "Penthouse": 5_000_000, "Studio": 500_000}[prop_type]
        price = round(base_price * random.uniform(0.6, 2.5), -3)
        listings.append({
            "listing_id": f"LST{i:04d}",
            "agent_id": agent[0],
            "agent_name": agent[1],
            "agency": agent[2],
            "property_type": prop_type,
            "bedrooms": beds,
            "community": community,
            "emirate": emirate,
            "price": price,
            "listing_date": random_date(365),
        })
    return listings


def build_leads(listings, n=800):
    leads = []
    for i in range(1, n + 1):
        listing = random.choice(listings)
        leads.append({
            "lead_id": f"LED{i:04d}",
            "listing_id": listing["listing_id"],
            "agent_id": listing["agent_id"],
            "agent_name": listing["agent_name"],
            "agency": listing["agency"],
            "property_type": listing["property_type"],
            "bedrooms": listing["bedrooms"],
            "community": listing["community"],
            "emirate": listing["emirate"],
            "listing_price": listing["price"],
            "lead_source": random.choice(LEAD_SOURCES),
            "lead_status": random.choice(LEAD_STATUSES),
            "lead_date": random_date(180),
            "buyer_name": f"Buyer_{i:04d}",
        })
    return leads


def build_credits(listings, n=600):
    credits = []
    for i in range(1, n + 1):
        listing = random.choice(listings)
        credit_type = random.choice(CREDIT_TYPES)
        cost = {"Featured": 50, "Premium Listing": 120, "Refresh": 10,
                "Hot Property": 75, "Boost": 30}[credit_type]
        credits.append({
            "credit_id": f"CRD{i:04d}",
            "listing_id": listing["listing_id"],
            "agent_id": listing["agent_id"],
            "agent_name": listing["agent_name"],
            "agency": listing["agency"],
            "property_type": listing["property_type"],
            "community": listing["community"],
            "emirate": listing["emirate"],
            "listing_price": listing["price"],
            "credit_type": credit_type,
            "credits_used": cost,
            "transaction_date": random_date(180),
        })
    return credits


if __name__ == "__main__":
    listings = build_listings(300)
    leads = build_leads(listings, 800)
    credits = build_credits(listings, 600)

    pd.DataFrame(listings).to_csv("listings.csv", index=False)
    pd.DataFrame(leads).to_csv("listings_leads.csv", index=False)
    pd.DataFrame(credits).to_csv("listings_credits.csv", index=False)

    print(f"Generated {len(listings)} listings, {len(leads)} leads, {len(credits)} credit transactions.")
    print("Files: listings.csv, listings_leads.csv, listings_credits.csv")
