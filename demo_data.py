"""
Generates demo-specific datasets designed to produce compelling, clear answers
for the 4 target demo questions. Each dataset is hand-tuned so the chatbot's
tools return insightful, non-random results.

Run once:  python demo_data.py
Outputs:   demo_listings.csv, demo_listings_leads.csv, demo_listings_credits.csv

Demo agent: AGT001 (Sarah Al Mansoori) — all demo questions assume this agent.

Target questions & expected insights:
1. "What should be my next target location to maximize?"
   → Business Bay (high opportunity 0.92, 18 expected leads, agent has 0 listings there)
   → Meydan City (opportunity 0.88, 15 expected leads, agent absent)

2. "Which of my listings can be optimized for quality score?"
   → LST0003 (score 42, weak: image_quality) — easy fix
   → LST0005 (score 51, weak: description) — needs better copy
   → LST0008 (score 58, weak: listing_completion) — missing fields

3. "Which of my listings is performing the best in terms of quality of leads?"
   → LST0001 (genuine ratio 0.95, response rate 0.90) — top performer
   → LST0004 (genuine ratio 0.92, response rate 0.85)
   → LST0009 (genuine ratio 0.88, response rate 0.80)

4. "For which listings did I spend most credits last week?"
   → LST0002 (Palm Jumeirah villa, 520 credits — heavy Featured+Premium)
   → LST0006 (Downtown penthouse, 380 credits — multiple Boosts)
   → LST0001 (Marina apartment, 200 credits — steady Refresh+Featured)
"""
import pandas as pd
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Reference date: "today" for the demo — all dates are relative to this
# ---------------------------------------------------------------------------
TODAY = datetime(2026, 7, 2)


def _date(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# AGENTS — 5 agents, AGT001 is the demo protagonist
# ---------------------------------------------------------------------------
AGENTS = {
    "AGT001": ("Sarah Al Mansoori", "Betterhomes"),
    "AGT002": ("James Mitchell", "Espace Real Estate"),
    "AGT003": ("Fatima Hassan", "Allsopp & Allsopp"),
    "AGT004": ("Raj Patel", "Driven Properties"),
    "AGT005": ("Emma Clarke", "Dubizzle Property"),
}


# ---------------------------------------------------------------------------
# LISTINGS — 40 total, 12 belong to AGT001
# ---------------------------------------------------------------------------
def build_listings():
    rows = [
        # ── AGT001: Sarah's 12 listings ──────────────────────────────────
        # Good listings (high quality) — these will show up in lead quality ranking
        {"listing_id": "LST0001", "agent_id": "AGT001", "property_type": "Apartment", "bedrooms": 2,
         "community": "Dubai Marina", "emirate": "Dubai", "price": 1_850_000,
         "listing_date": _date(120), "quality_score": 92, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.78, "expected_leads": 14},

        {"listing_id": "LST0002", "agent_id": "AGT001", "property_type": "Villa", "bedrooms": 5,
         "community": "Palm Jumeirah", "emirate": "Dubai", "price": 12_500_000,
         "listing_date": _date(90), "quality_score": 88, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.65, "expected_leads": 8},

        # Bad listings (low quality) — these answer "which can be optimized?"
        {"listing_id": "LST0003", "agent_id": "AGT001", "property_type": "Apartment", "bedrooms": 1,
         "community": "JBR", "emirate": "Dubai", "price": 950_000,
         "listing_date": _date(60), "quality_score": 42, "quality_color": "red",
         "weak_factor": "image_quality", "opportunity_score": 0.82, "expected_leads": 16},

        {"listing_id": "LST0004", "agent_id": "AGT001", "property_type": "Townhouse", "bedrooms": 3,
         "community": "Arabian Ranches", "emirate": "Dubai", "price": 3_200_000,
         "listing_date": _date(45), "quality_score": 85, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.71, "expected_leads": 12},

        {"listing_id": "LST0005", "agent_id": "AGT001", "property_type": "Studio", "bedrooms": 0,
         "community": "Jumeirah Village Circle", "emirate": "Dubai", "price": 480_000,
         "listing_date": _date(30), "quality_score": 51, "quality_color": "orange",
         "weak_factor": "description", "opportunity_score": 0.90, "expected_leads": 19},

        {"listing_id": "LST0006", "agent_id": "AGT001", "property_type": "Penthouse", "bedrooms": 4,
         "community": "Downtown Dubai", "emirate": "Dubai", "price": 8_700_000,
         "listing_date": _date(75), "quality_score": 79, "quality_color": "orange",
         "weak_factor": "price_realism", "opportunity_score": 0.55, "expected_leads": 7},

        {"listing_id": "LST0007", "agent_id": "AGT001", "property_type": "Apartment", "bedrooms": 3,
         "community": "DIFC", "emirate": "Dubai", "price": 4_100_000,
         "listing_date": _date(100), "quality_score": 91, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.60, "expected_leads": 9},

        {"listing_id": "LST0008", "agent_id": "AGT001", "property_type": "Apartment", "bedrooms": 2,
         "community": "Emirates Hills", "emirate": "Dubai", "price": 2_300_000,
         "listing_date": _date(20), "quality_score": 58, "quality_color": "orange",
         "weak_factor": "listing_completion", "opportunity_score": 0.75, "expected_leads": 13},

        {"listing_id": "LST0009", "agent_id": "AGT001", "property_type": "Villa", "bedrooms": 4,
         "community": "Dubai Marina", "emirate": "Dubai", "price": 5_600_000,
         "listing_date": _date(150), "quality_score": 94, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.50, "expected_leads": 6},

        {"listing_id": "LST0010", "agent_id": "AGT001", "property_type": "Apartment", "bedrooms": 1,
         "community": "Al Reem Island", "emirate": "Abu Dhabi", "price": 720_000,
         "listing_date": _date(40), "quality_score": 65, "quality_color": "orange",
         "weak_factor": "title", "opportunity_score": 0.68, "expected_leads": 11},

        {"listing_id": "LST0011", "agent_id": "AGT001", "property_type": "Townhouse", "bedrooms": 3,
         "community": "Yas Island", "emirate": "Abu Dhabi", "price": 2_800_000,
         "listing_date": _date(55), "quality_score": 73, "quality_color": "orange",
         "weak_factor": "verified", "opportunity_score": 0.62, "expected_leads": 10},

        {"listing_id": "LST0012", "agent_id": "AGT001", "property_type": "Villa", "bedrooms": 6,
         "community": "Palm Jumeirah", "emirate": "Dubai", "price": 18_000_000,
         "listing_date": _date(10), "quality_score": 47, "quality_color": "red",
         "weak_factor": "description", "opportunity_score": 0.85, "expected_leads": 15},

        # ── AGT002-AGT005: Other agents' listings (28 total) ─────────────
        # These populate communities Sarah is NOT in (Business Bay, Meydan, etc.)
        # with HIGH opportunity scores → drives location recommendation

        # Business Bay — high opportunity, Sarah absent
        {"listing_id": "LST0013", "agent_id": "AGT002", "property_type": "Apartment", "bedrooms": 2,
         "community": "Business Bay", "emirate": "Dubai", "price": 1_600_000,
         "listing_date": _date(80), "quality_score": 87, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.92, "expected_leads": 18},
        {"listing_id": "LST0014", "agent_id": "AGT003", "property_type": "Apartment", "bedrooms": 1,
         "community": "Business Bay", "emirate": "Dubai", "price": 1_100_000,
         "listing_date": _date(65), "quality_score": 83, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.91, "expected_leads": 17},
        {"listing_id": "LST0015", "agent_id": "AGT004", "property_type": "Studio", "bedrooms": 0,
         "community": "Business Bay", "emirate": "Dubai", "price": 650_000,
         "listing_date": _date(50), "quality_score": 79, "quality_color": "orange",
         "weak_factor": "description", "opportunity_score": 0.93, "expected_leads": 19},
        {"listing_id": "LST0016", "agent_id": "AGT005", "property_type": "Apartment", "bedrooms": 3,
         "community": "Business Bay", "emirate": "Dubai", "price": 2_400_000,
         "listing_date": _date(35), "quality_score": 90, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.90, "expected_leads": 17},

        # Meydan City — second-best opportunity, Sarah absent
        {"listing_id": "LST0017", "agent_id": "AGT002", "property_type": "Villa", "bedrooms": 4,
         "community": "Meydan City", "emirate": "Dubai", "price": 4_500_000,
         "listing_date": _date(70), "quality_score": 85, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.88, "expected_leads": 15},
        {"listing_id": "LST0018", "agent_id": "AGT003", "property_type": "Townhouse", "bedrooms": 3,
         "community": "Meydan City", "emirate": "Dubai", "price": 3_100_000,
         "listing_date": _date(55), "quality_score": 81, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.87, "expected_leads": 14},
        {"listing_id": "LST0019", "agent_id": "AGT004", "property_type": "Apartment", "bedrooms": 2,
         "community": "Meydan City", "emirate": "Dubai", "price": 1_900_000,
         "listing_date": _date(40), "quality_score": 78, "quality_color": "orange",
         "weak_factor": "image_quality", "opportunity_score": 0.89, "expected_leads": 16},

        # Saadiyat Island — third option, Sarah absent
        {"listing_id": "LST0020", "agent_id": "AGT005", "property_type": "Villa", "bedrooms": 5,
         "community": "Saadiyat Island", "emirate": "Abu Dhabi", "price": 7_200_000,
         "listing_date": _date(90), "quality_score": 91, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.84, "expected_leads": 13},
        {"listing_id": "LST0021", "agent_id": "AGT002", "property_type": "Penthouse", "bedrooms": 4,
         "community": "Saadiyat Island", "emirate": "Abu Dhabi", "price": 9_500_000,
         "listing_date": _date(60), "quality_score": 88, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.83, "expected_leads": 12},

        # Al Nahda — lower opportunity (should NOT be recommended)
        {"listing_id": "LST0022", "agent_id": "AGT003", "property_type": "Apartment", "bedrooms": 1,
         "community": "Al Nahda", "emirate": "Sharjah", "price": 350_000,
         "listing_date": _date(100), "quality_score": 72, "quality_color": "orange",
         "weak_factor": "image_quality", "opportunity_score": 0.35, "expected_leads": 4},
        {"listing_id": "LST0023", "agent_id": "AGT004", "property_type": "Studio", "bedrooms": 0,
         "community": "Al Nahda", "emirate": "Sharjah", "price": 220_000,
         "listing_date": _date(110), "quality_score": 68, "quality_color": "orange",
         "weak_factor": "title", "opportunity_score": 0.30, "expected_leads": 3},

        # Filler: other agents in communities Sarah IS in (adds market depth)
        {"listing_id": "LST0024", "agent_id": "AGT002", "property_type": "Apartment", "bedrooms": 2,
         "community": "Dubai Marina", "emirate": "Dubai", "price": 2_100_000,
         "listing_date": _date(85), "quality_score": 80, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.72, "expected_leads": 12},
        {"listing_id": "LST0025", "agent_id": "AGT003", "property_type": "Villa", "bedrooms": 4,
         "community": "Palm Jumeirah", "emirate": "Dubai", "price": 14_000_000,
         "listing_date": _date(95), "quality_score": 86, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.58, "expected_leads": 7},
        {"listing_id": "LST0026", "agent_id": "AGT004", "property_type": "Apartment", "bedrooms": 1,
         "community": "JBR", "emirate": "Dubai", "price": 1_050_000,
         "listing_date": _date(70), "quality_score": 75, "quality_color": "orange",
         "weak_factor": "description", "opportunity_score": 0.70, "expected_leads": 11},
        {"listing_id": "LST0027", "agent_id": "AGT005", "property_type": "Townhouse", "bedrooms": 3,
         "community": "Arabian Ranches", "emirate": "Dubai", "price": 2_900_000,
         "listing_date": _date(50), "quality_score": 82, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.67, "expected_leads": 10},
        {"listing_id": "LST0028", "agent_id": "AGT002", "property_type": "Penthouse", "bedrooms": 3,
         "community": "Downtown Dubai", "emirate": "Dubai", "price": 7_800_000,
         "listing_date": _date(45), "quality_score": 89, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.52, "expected_leads": 6},
        {"listing_id": "LST0029", "agent_id": "AGT003", "property_type": "Apartment", "bedrooms": 2,
         "community": "DIFC", "emirate": "Dubai", "price": 3_800_000,
         "listing_date": _date(30), "quality_score": 84, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.55, "expected_leads": 8},
        {"listing_id": "LST0030", "agent_id": "AGT004", "property_type": "Apartment", "bedrooms": 1,
         "community": "Jumeirah Village Circle", "emirate": "Dubai", "price": 520_000,
         "listing_date": _date(25), "quality_score": 70, "quality_color": "orange",
         "weak_factor": "verified", "opportunity_score": 0.80, "expected_leads": 14},

        # More filler for market depth
        {"listing_id": "LST0031", "agent_id": "AGT005", "property_type": "Studio", "bedrooms": 0,
         "community": "Al Reem Island", "emirate": "Abu Dhabi", "price": 580_000,
         "listing_date": _date(40), "quality_score": 76, "quality_color": "orange",
         "weak_factor": "listing_completion", "opportunity_score": 0.63, "expected_leads": 9},
        {"listing_id": "LST0032", "agent_id": "AGT002", "property_type": "Villa", "bedrooms": 5,
         "community": "Yas Island", "emirate": "Abu Dhabi", "price": 3_400_000,
         "listing_date": _date(60), "quality_score": 82, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.60, "expected_leads": 9},

        # Al Majaz — moderate opportunity
        {"listing_id": "LST0033", "agent_id": "AGT003", "property_type": "Apartment", "bedrooms": 2,
         "community": "Al Majaz", "emirate": "Sharjah", "price": 450_000,
         "listing_date": _date(80), "quality_score": 74, "quality_color": "orange",
         "weak_factor": "price_realism", "opportunity_score": 0.45, "expected_leads": 5},

        # Khalifa City
        {"listing_id": "LST0034", "agent_id": "AGT004", "property_type": "Villa", "bedrooms": 4,
         "community": "Khalifa City", "emirate": "Abu Dhabi", "price": 2_600_000,
         "listing_date": _date(70), "quality_score": 80, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.72, "expected_leads": 11},
        {"listing_id": "LST0035", "agent_id": "AGT005", "property_type": "Townhouse", "bedrooms": 3,
         "community": "Khalifa City", "emirate": "Abu Dhabi", "price": 1_900_000,
         "listing_date": _date(55), "quality_score": 77, "quality_color": "orange",
         "weak_factor": "image_quality", "opportunity_score": 0.70, "expected_leads": 10},

        # Extra Business Bay (more market signal)
        {"listing_id": "LST0036", "agent_id": "AGT002", "property_type": "Penthouse", "bedrooms": 3,
         "community": "Business Bay", "emirate": "Dubai", "price": 5_200_000,
         "listing_date": _date(20), "quality_score": 86, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.94, "expected_leads": 20},

        # Extra Emirates Hills
        {"listing_id": "LST0037", "agent_id": "AGT003", "property_type": "Villa", "bedrooms": 6,
         "community": "Emirates Hills", "emirate": "Dubai", "price": 22_000_000,
         "listing_date": _date(15), "quality_score": 93, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.48, "expected_leads": 5},

        # Extra Meydan
        {"listing_id": "LST0038", "agent_id": "AGT005", "property_type": "Apartment", "bedrooms": 2,
         "community": "Meydan City", "emirate": "Dubai", "price": 1_700_000,
         "listing_date": _date(30), "quality_score": 80, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.86, "expected_leads": 14},

        # Extra JVC
        {"listing_id": "LST0039", "agent_id": "AGT003", "property_type": "Apartment", "bedrooms": 1,
         "community": "Jumeirah Village Circle", "emirate": "Dubai", "price": 550_000,
         "listing_date": _date(35), "quality_score": 71, "quality_color": "orange",
         "weak_factor": "description", "opportunity_score": 0.78, "expected_leads": 13},

        # Extra Dubai Marina
        {"listing_id": "LST0040", "agent_id": "AGT004", "property_type": "Penthouse", "bedrooms": 4,
         "community": "Dubai Marina", "emirate": "Dubai", "price": 6_500_000,
         "listing_date": _date(25), "quality_score": 90, "quality_color": "green",
         "weak_factor": "", "opportunity_score": 0.70, "expected_leads": 11},
    ]

    for r in rows:
        aid = r["agent_id"]
        r["agent_name"] = AGENTS[aid][0]
        r["agency"] = AGENTS[aid][1]
        r["lead_value_per_upgrade_cost"] = round(r["expected_leads"] / max(r["opportunity_score"], 0.1) * 1.5, 1)

    return rows


# ---------------------------------------------------------------------------
# LEADS — hand-crafted for AGT001's listings to produce clear quality ranking
# ---------------------------------------------------------------------------
def build_leads(listings):
    rows = []
    lead_counter = 0

    def _add_leads(listing_id, agent_id, community, emirate, prop_type, beds, price,
                   total, spam_count, responded_count, resp_time_range):
        nonlocal lead_counter
        for i in range(total):
            lead_counter += 1
            is_spam = i < spam_count
            responded = (not is_spam) and i < (spam_count + responded_count)
            resp_time = None
            if responded:
                resp_time = resp_time_range[0] + (resp_time_range[1] - resp_time_range[0]) * (i / max(total, 1))
                resp_time = int(resp_time)

            rows.append({
                "lead_id": f"LED{lead_counter:04d}",
                "listing_id": listing_id,
                "agent_id": agent_id,
                "agent_name": AGENTS[agent_id][0],
                "agency": AGENTS[agent_id][1],
                "property_type": prop_type,
                "bedrooms": beds,
                "community": community,
                "emirate": emirate,
                "listing_price": price,
                "lead_source": ["PropertyFinder", "Bayut", "Direct Call", "Referral", "Walk-in"][lead_counter % 5],
                "lead_status": ["Converted", "Qualified", "Contacted", "New", "Lost"][lead_counter % 5],
                "lead_date": _date(lead_counter % 30),
                "buyer_name": f"Buyer_{lead_counter:04d}",
                "channel": ["whatsapp", "call", "email"][lead_counter % 3],
                "is_spam": is_spam,
                "responded": responded,
                "response_time_minutes": resp_time,
            })

    # AGT001's listings — carefully tuned lead quality
    # LST0001: BEST quality — 20 leads, only 1 spam, 17 responded, fast response
    _add_leads("LST0001", "AGT001", "Dubai Marina", "Dubai", "Apartment", 2, 1_850_000,
               total=20, spam_count=1, responded_count=17, resp_time_range=(5, 30))

    # LST0004: SECOND best — 16 leads, 1 spam, 13 responded
    _add_leads("LST0004", "AGT001", "Arabian Ranches", "Dubai", "Townhouse", 3, 3_200_000,
               total=16, spam_count=1, responded_count=13, resp_time_range=(10, 45))

    # LST0009: THIRD best — 12 leads, 1 spam, 9 responded
    _add_leads("LST0009", "AGT001", "Dubai Marina", "Dubai", "Villa", 4, 5_600_000,
               total=12, spam_count=1, responded_count=9, resp_time_range=(8, 60))

    # LST0007: Good — 10 leads, 2 spam, 6 responded
    _add_leads("LST0007", "AGT001", "DIFC", "Dubai", "Apartment", 3, 4_100_000,
               total=10, spam_count=2, responded_count=6, resp_time_range=(15, 90))

    # LST0002: Moderate — 14 leads, 3 spam, 7 responded (expensive but mediocre leads)
    _add_leads("LST0002", "AGT001", "Palm Jumeirah", "Dubai", "Villa", 5, 12_500_000,
               total=14, spam_count=3, responded_count=7, resp_time_range=(20, 120))

    # LST0006: Poor lead quality — 18 leads, 6 spam, 5 responded, slow
    _add_leads("LST0006", "AGT001", "Downtown Dubai", "Dubai", "Penthouse", 4, 8_700_000,
               total=18, spam_count=6, responded_count=5, resp_time_range=(60, 480))

    # LST0003: Low quality listing, decent leads — 8 leads, 2 spam, 4 responded
    _add_leads("LST0003", "AGT001", "JBR", "Dubai", "Apartment", 1, 950_000,
               total=8, spam_count=2, responded_count=4, resp_time_range=(30, 120))

    # LST0005: Few leads — 5 leads, 1 spam, 2 responded
    _add_leads("LST0005", "AGT001", "Jumeirah Village Circle", "Dubai", "Studio", 0, 480_000,
               total=5, spam_count=1, responded_count=2, resp_time_range=(45, 180))

    # LST0008: New listing, few leads — 3 leads, 0 spam, 2 responded
    _add_leads("LST0008", "AGT001", "Emirates Hills", "Dubai", "Apartment", 2, 2_300_000,
               total=3, spam_count=0, responded_count=2, resp_time_range=(10, 40))

    # LST0010-0012: Minimal leads
    _add_leads("LST0010", "AGT001", "Al Reem Island", "Abu Dhabi", "Apartment", 1, 720_000,
               total=4, spam_count=1, responded_count=2, resp_time_range=(20, 90))
    _add_leads("LST0011", "AGT001", "Yas Island", "Abu Dhabi", "Townhouse", 3, 2_800_000,
               total=6, spam_count=1, responded_count=3, resp_time_range=(25, 100))
    _add_leads("LST0012", "AGT001", "Palm Jumeirah", "Dubai", "Villa", 6, 18_000_000,
               total=3, spam_count=0, responded_count=2, resp_time_range=(15, 50))

    # Other agents' leads — less carefully tuned, just for market depth
    other_listings = [l for l in listings if l["agent_id"] != "AGT001"]
    for lst in other_listings:
        _add_leads(lst["listing_id"], lst["agent_id"], lst["community"], lst["emirate"],
                   lst["property_type"], lst["bedrooms"], lst["price"],
                   total=8, spam_count=2, responded_count=4, resp_time_range=(20, 150))

    return rows


# ---------------------------------------------------------------------------
# CREDITS — hand-crafted for AGT001 to show clear "last week" spending pattern
# ---------------------------------------------------------------------------
def build_credits(listings):
    rows = []
    crd_counter = 0

    # Reference date for "last week" = last 7 days relative to max transaction date
    # We'll make the max transaction date = TODAY, so "last week" = TODAY-7 to TODAY

    def _add_credit(listing_id, agent_id, community, emirate, prop_type, price,
                    credit_type, cost, days_ago):
        nonlocal crd_counter
        crd_counter += 1
        rows.append({
            "credit_id": f"CRD{crd_counter:04d}",
            "listing_id": listing_id,
            "agent_id": agent_id,
            "agent_name": AGENTS[agent_id][0],
            "agency": AGENTS[agent_id][1],
            "property_type": prop_type,
            "community": community,
            "emirate": emirate,
            "listing_price": price,
            "credit_type": credit_type,
            "credits_used": cost,
            "transaction_date": _date(days_ago),
        })

    # ── AGT001: Last 7 days — these drive the "credits last week" answer ──

    # LST0002 (Palm Jumeirah Villa) — HIGHEST spend: 520 credits
    _add_credit("LST0002", "AGT001", "Palm Jumeirah", "Dubai", "Villa", 12_500_000,
                "Featured", 50, 1)
    _add_credit("LST0002", "AGT001", "Palm Jumeirah", "Dubai", "Villa", 12_500_000,
                "Featured", 50, 2)
    _add_credit("LST0002", "AGT001", "Palm Jumeirah", "Dubai", "Villa", 12_500_000,
                "Premium Listing", 120, 3)
    _add_credit("LST0002", "AGT001", "Palm Jumeirah", "Dubai", "Villa", 12_500_000,
                "Premium Listing", 120, 4)
    _add_credit("LST0002", "AGT001", "Palm Jumeirah", "Dubai", "Villa", 12_500_000,
                "Hot Property", 75, 5)
    _add_credit("LST0002", "AGT001", "Palm Jumeirah", "Dubai", "Villa", 12_500_000,
                "Hot Property", 75, 6)
    _add_credit("LST0002", "AGT001", "Palm Jumeirah", "Dubai", "Villa", 12_500_000,
                "Boost", 30, 1)

    # LST0006 (Downtown Penthouse) — SECOND: 380 credits
    _add_credit("LST0006", "AGT001", "Downtown Dubai", "Dubai", "Penthouse", 8_700_000,
                "Premium Listing", 120, 1)
    _add_credit("LST0006", "AGT001", "Downtown Dubai", "Dubai", "Penthouse", 8_700_000,
                "Featured", 50, 2)
    _add_credit("LST0006", "AGT001", "Downtown Dubai", "Dubai", "Penthouse", 8_700_000,
                "Boost", 30, 3)
    _add_credit("LST0006", "AGT001", "Downtown Dubai", "Dubai", "Penthouse", 8_700_000,
                "Boost", 30, 4)
    _add_credit("LST0006", "AGT001", "Downtown Dubai", "Dubai", "Penthouse", 8_700_000,
                "Hot Property", 75, 5)
    _add_credit("LST0006", "AGT001", "Downtown Dubai", "Dubai", "Penthouse", 8_700_000,
                "Hot Property", 75, 6)

    # LST0001 (Marina Apartment) — THIRD: 200 credits
    _add_credit("LST0001", "AGT001", "Dubai Marina", "Dubai", "Apartment", 1_850_000,
                "Featured", 50, 1)
    _add_credit("LST0001", "AGT001", "Dubai Marina", "Dubai", "Apartment", 1_850_000,
                "Featured", 50, 3)
    _add_credit("LST0001", "AGT001", "Dubai Marina", "Dubai", "Apartment", 1_850_000,
                "Refresh", 10, 2)
    _add_credit("LST0001", "AGT001", "Dubai Marina", "Dubai", "Apartment", 1_850_000,
                "Refresh", 10, 4)
    _add_credit("LST0001", "AGT001", "Dubai Marina", "Dubai", "Apartment", 1_850_000,
                "Hot Property", 75, 5)
    _add_credit("LST0001", "AGT001", "Dubai Marina", "Dubai", "Apartment", 1_850_000,
                "Boost", 5, 6)  # small boost

    # LST0005 (JVC Studio) — FOURTH: 90 credits
    _add_credit("LST0005", "AGT001", "Jumeirah Village Circle", "Dubai", "Studio", 480_000,
                "Refresh", 10, 1)
    _add_credit("LST0005", "AGT001", "Jumeirah Village Circle", "Dubai", "Studio", 480_000,
                "Refresh", 10, 3)
    _add_credit("LST0005", "AGT001", "Jumeirah Village Circle", "Dubai", "Studio", 480_000,
                "Featured", 50, 5)
    _add_credit("LST0005", "AGT001", "Jumeirah Village Circle", "Dubai", "Studio", 480_000,
                "Boost", 20, 6)  # small boost

    # ── AGT001: Older transactions (before last week) — context only ──
    _add_credit("LST0001", "AGT001", "Dubai Marina", "Dubai", "Apartment", 1_850_000,
                "Featured", 50, 15)
    _add_credit("LST0001", "AGT001", "Dubai Marina", "Dubai", "Apartment", 1_850_000,
                "Refresh", 10, 20)
    _add_credit("LST0003", "AGT001", "JBR", "Dubai", "Apartment", 950_000,
                "Boost", 30, 25)
    _add_credit("LST0004", "AGT001", "Arabian Ranches", "Dubai", "Townhouse", 3_200_000,
                "Featured", 50, 30)
    _add_credit("LST0009", "AGT001", "Dubai Marina", "Dubai", "Villa", 5_600_000,
                "Premium Listing", 120, 35)
    _add_credit("LST0012", "AGT001", "Palm Jumeirah", "Dubai", "Villa", 18_000_000,
                "Hot Property", 75, 12)
    _add_credit("LST0007", "AGT001", "DIFC", "Dubai", "Apartment", 4_100_000,
                "Featured", 50, 18)
    _add_credit("LST0008", "AGT001", "Emirates Hills", "Dubai", "Apartment", 2_300_000,
                "Refresh", 10, 22)

    # ── Other agents: recent credits for market depth ──
    other_listings = [l for l in listings if l["agent_id"] != "AGT001"]
    costs = {"Featured": 50, "Premium Listing": 120, "Refresh": 10, "Hot Property": 75, "Boost": 30}
    credit_types = list(costs.keys())
    for idx, lst in enumerate(other_listings):
        ct = credit_types[idx % len(credit_types)]
        _add_credit(lst["listing_id"], lst["agent_id"], lst["community"], lst["emirate"],
                    lst["property_type"], lst["price"], ct, costs[ct], (idx % 14) + 1)
        # Add a second transaction for variety
        ct2 = credit_types[(idx + 2) % len(credit_types)]
        _add_credit(lst["listing_id"], lst["agent_id"], lst["community"], lst["emirate"],
                    lst["property_type"], lst["price"], ct2, costs[ct2], (idx % 10) + 3)

    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    listings = build_listings()
    leads = build_leads(listings)
    credits = build_credits(listings)

    pd.DataFrame(listings).to_csv("demo_listings.csv", index=False)
    pd.DataFrame(leads).to_csv("demo_listings_leads.csv", index=False)
    pd.DataFrame(credits).to_csv("demo_listings_credits.csv", index=False)

    # Print verification
    df_l = pd.DataFrame(listings)
    df_ld = pd.DataFrame(leads)
    df_c = pd.DataFrame(credits)

    print(f"Generated: {len(listings)} listings, {len(leads)} leads, {len(credits)} credit txns")
    print(f"Files: demo_listings.csv, demo_listings_leads.csv, demo_listings_credits.csv")
    print()
    print("=== DEMO VERIFICATION (AGT001 = Sarah Al Mansoori) ===")
    print()

    # Q1: Next target location
    agt001 = df_l[df_l["agent_id"] == "AGT001"]
    print(f"Q1 - Sarah's communities: {sorted(agt001['community'].unique())}")
    market = df_l.groupby("community").agg(
        avg_opp=("opportunity_score", "mean"),
        avg_leads=("expected_leads", "mean"),
        count=("listing_id", "count"),
    ).sort_values("avg_opp", ascending=False)
    absent = market[~market.index.isin(agt001["community"].unique())]
    print(f"     Top absent communities: {absent.head(3).to_dict('index')}")
    print()

    # Q2: Quality optimization
    low_q = agt001[agt001["quality_score"] < 80].sort_values("quality_score")
    print(f"Q2 - Listings to optimize ({len(low_q)}):")
    for _, r in low_q.iterrows():
        print(f"     {r['listing_id']} ({r['community']}) score={r['quality_score']} weak={r['weak_factor']}")
    print()

    # Q3: Best lead quality
    agt_leads = df_ld[df_ld["agent_id"] == "AGT001"]
    lead_q = agt_leads.groupby("listing_id").agg(
        total=("lead_id", "count"),
        genuine=("is_spam", lambda s: int((~s).sum())),
        responded=("responded", "sum"),
    )
    lead_q["genuine_ratio"] = (lead_q["genuine"] / lead_q["total"]).round(3)
    lead_q["response_rate"] = (lead_q["responded"] / lead_q["total"]).round(3)
    lead_q = lead_q.sort_values(["genuine_ratio", "response_rate"], ascending=False)
    print(f"Q3 - Lead quality ranking:")
    for lid, r in lead_q.head(5).iterrows():
        print(f"     {lid} genuine_ratio={r['genuine_ratio']} response_rate={r['response_rate']} total={r['total']}")
    print()

    # Q4: Credits last week
    agt_cred = df_c[df_c["agent_id"] == "AGT001"]
    agt_cred_dt = agt_cred.copy()
    agt_cred_dt["transaction_date"] = pd.to_datetime(agt_cred_dt["transaction_date"])
    ref = agt_cred_dt["transaction_date"].max()
    recent = agt_cred_dt[agt_cred_dt["transaction_date"] > ref - pd.Timedelta(days=7)]
    spend = recent.groupby("listing_id")["credits_used"].sum().sort_values(ascending=False)
    print(f"Q4 - Credit spend last 7 days (ref={ref.date()}):")
    for lid, total in spend.items():
        comm = agt001[agt001["listing_id"] == lid]["community"].values
        comm_name = comm[0] if len(comm) > 0 else "?"
        print(f"     {lid} ({comm_name}): {total} credits")
