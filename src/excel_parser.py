"""Excel -> per-page dicts (VERTICAL workbook format).

Workbook layout expected:

    Col A (Sl No) | Col B (Page) | Col C (Attribute) | Col D (Required/Optional) | Col E (Remarks/Value)
    ------------- | ------------ | ----------------- | ------------------------- | --------------------
       1          | Merchant     | Organization      | Required                  | 6032
       2          | Merchant     | Merchant ID       | Required                  | 01
       ...

Each Page block (Merchant, Store, Chain, Merchant Criteria, Instrument
Criteria) is mapped POSITIONALLY: the first row in a page becomes the
first canonical key in `PAGE_SEQUENCES[page]`, the second row the second
key, and so on. This is robust as long as the user keeps the standard
template row order.

Output:
    {
      "merchant":            {"merchant_org": "6032", "merchant_id": "01", ...},
      "store":               {...},
      "chain":               {...},
      "merchant_criteria":   {...},
      "instrument_criteria": {...},
    }
"""
from __future__ import annotations

from io import BytesIO
from typing import Dict, List, Tuple

import openpyxl


PAGE_NAMES = {
    "merchant":            "merchant",
    "store":               "store",
    "chain":               "chain",
    "merchant criteria":   "merchant_criteria",
    "instrument criteria": "instrument_criteria",
}


# Each list is the canonical key for the i-th attribute row of that page.
MERCHANT_SEQUENCE: List[str] = [
    "merchant_org",                 # 1  Organization
    "merchant_id",                  # 2  Merchant ID
    "merchant_name",                # 3  Merchant Name
    "merchant_status",              # 4  Status
    "merchant_governing_state",     # 5  Governing State
    "merchant_time_zone",           # 6  Time Zone
    "merchant_demographics_id",     # 7  Merchant Demographic ID
    "address_type",                 # 8  Address Type
    "address_line1",                # 9  Address Line
    "city",                         # 10 City
    "state",                        # 11 State
    "postal_code",                  # 12 Postal Code
    "country",                      # 13 Country
    "language",                     # 14 Language
    "longitude",                    # 15 Longitude
    "longitude_direction",          # 16 Longitude Direction
    "latitude",                     # 17 Latitude
    "latitude_direction",           # 18 Latitude Direction
    "phone_country",                # 19 Phone Country
    "phone_number",                 # 20 Phone Number
    "phone_type",                   # 21 Type   (phone)
    "email",                        # 22 Email Address
    "email_type",                   # 23 Type   (email)
    "social_media",                 # 24 Social Media
    "logo",                         # 25 Logo
    "photo",                        # 26 Photo
    "facebook_url",                 # 27 Facebook URL
    "instagram_url",                # 28 Instagram URL
    "twitter_url",                  # 29 X (Twitter)
    "google_id",                    # 30 Google ID
    "channel_name",                 # 31 Channel Name
    "channel_identifier",           # 32 Channel Identifier
    "chain_id_link",                # 33 Chain ID  (link to chain)
    "iva_table_id",                 # 34 IVA (Table)
    "sku_table_id",                 # 35 SKU (Table)
    "coupon_table_id",              # 36 Coupon (Table)
    "connector_table_id",           # 37 Connector (Table)
    "criteria_table_id",            # 38 Merchant Criteria(Table)
]

STORE_SEQUENCE: List[str] = [
    "store_id",                     # 1  Store ID
    "store_name",                   # 2  Store Name
    "store_status",                 # 3  Status
    "store_merchant_id",            # 4  Merchant
    "store_governing_state",        # 5  Governing State
    "store_demographics_id",        # 6  Store Demographic ID
    "address_type",                 # 7  Address Type
    "address_line1",                # 8  Address Line
    "city",                         # 9  City
    "state",                        # 10 State
    "postal_code",                  # 11 Postal Code
    "country",                      # 12 Country
    "language",                     # 13 Language
    "longitude",                    # 14 Longitude
    "longitude_direction",          # 15 Longitude Direction
    "latitude",                     # 16 Latitude
    "latitude_direction",           # 17 Latitude Direction
    "location_identifier_type",     # 18 Location Identifier Type
    "location_identifier_value",    # 19 Location Identifier Value
    "phone_country",                # 20 Phone Country
    "phone_number",                 # 21 Phone Number
    "phone_type",                   # 22 Phone Type
    "email",                        # 23 Email Address
    "email_type",                   # 24 Email Type
    "social_media",                 # 25 Social Media
    "logo",                         # 26 Logo
    "photo",                        # 27 Photo
    "facebook_url",                 # 28 Facebook URL
    "instagram_url",                # 29 Instagram URL
    "twitter_url",                  # 30 X (Twitter)
    "google_id",                    # 31 Google ID
    "terminal_information",         # 32 Terminal Information
    "printer",                      # 33 Printer
    "chain_id_link",                # 34 Chain ID
    "iva_table_id",                 # 35 IVA (Table)
    "sku_table_id",                 # 36 SKU (Table)
    "coupon_table_id",              # 37 Coupon (Table)
    "connector_table_id",           # 38 Connector (Table)
    "merchant_criteria_table_id",   # 39 Merchant Criteria(Table)
    "instrument_criteria_table_id", # 40 Instrument Criteria(Table)
]

CHAIN_SEQUENCE: List[str] = [
    "chain_id",                     # 1  Chain ID
    "chain_name",                   # 2  Chain Name
    "chain_status",                 # 3  Status
    "chain_governing_state",        # 4  Governing State
    "chain_demographics_id",        # 5  Chain Demographic ID
    "address_type",                 # 6  Address Type
    "address_line1",                # 7  Address Line
    "city",                         # 8  City
    "state",                        # 9  State
    "postal_code",                  # 10 Postal Code
    "country",                      # 11 Country
    "language",                     # 12 Language
    "longitude",                    # 13 Longitude
    "longitude_direction",          # 14 Longitude Direction
    "latitude",                     # 15 Latitude
    "latitude_direction",           # 16 Latitude Direction
    "phone_country",                # 17 Phone Country
    "phone_number",                 # 18 Phone Number
    "phone_type",                   # 19 Phone Type
    "email",                        # 20 Email Address
    "email_type",                   # 21 Email Type
    "social_media",                 # 22 Social Media
    "logo",                         # 23 Logo
    "photo",                        # 24 Photo
    "facebook_url",                 # 25 Facebook URL
    "instagram_url",                # 26 Instagram URL
    "twitter_url",                  # 27 X (Twitter)
    "google_id",                    # 28 Google ID
    "channel_name",                 # 29 Channel Name
    "channel_identifier",           # 30 Channel Identifier
    "chain_id_link",                # 31 Chain ID (parent chain link)
    "iva_table_id",                 # 32 IVA (Table)
    "sku_table_id",                 # 33 SKU (Table)
    "coupon_table_id",              # 34 Coupon (Table)
    "connector_table_id",           # 35 Connector (Table)
    "merchant_criteria_table_id",   # 36 Merchant Criteria(Table)
    "instrument_criteria_table_id", # 37 Instrument Criteria(Table)
]

MERCHANT_CRITERIA_SEQUENCE: List[str] = [
    "criteria",                     # 1  Criteria ID
    "criteria_description",         # 2  Criteria Description
    "countries_list",               # 3  List of countries to be excluded or included
    "states_list",                  # 4  List of states ...
    "currencies_list",              # 5  List of currencies ...
    "mcc_list",                     # 6  List or range of MCC's ...
    "purchase_international_type",  # 7  International Type (Purchase Type)
    "purchase_type",                # 8  Purchase Type (Purchase Type)
    "entry_international_type",     # 9  International Type (Entry type)
    "entry_type",                   # 10 Entry Type (Entry type)
    "limit_international_type",     # 11 International Type (Limit Type)
    "limit_type",                   # 12 Limit Type (Limit Type)
    "tx_limit_type",                # 13 Limit Type (Transaction Limit)
    "tx_amount",                    # 14 Amount (Transaction Limit)
    "tx_limit",                     # 15 Limit (Transaction Limit)
    "block_cashback",               # 16 Block CashBack?
    "block_installments",           # 17 Block Installment
    "block_international",          # 18 Block International
]

INSTRUMENT_CRITERIA_SEQUENCE: List[str] = [
    "criteria",                     # 1  Criteria ID
    "description",                  # 2  Criteria Description
    "timed_limit_type",             # 3  Limit Type (Timed Transaction Limit)
    "timed_tx_amount",              # 4  Transaction Amount (Timed Transaction Limit)
    "timed_tx_count",               # 5  Transaction Count (Timed Transaction Limit)
    "timed_time_limit",             # 6  Time Limit (Timed Transaction Limit)
    "timed_time_unit",              # 7  Time Unit (Timed Transaction Limit)
    "daily_limit_type",             # 8  Limit Type (Daily Limit)
    "daily_tx_amount",              # 9  Transaction Amount (Daily Limit)
    "daily_tx_count",               # 10 Transaction Count (Daily Limit)
    "susp_channel",                 # 11 Channel (Suspension Control)
    "susp_response_code",           # 12 Response Code (Suspension Control)
    "susp_no_declines",             # 13 Number of Declines (Suspension Control)
    "susp_tracking_duration",       # 14 Tracking Duration (Suspension Control)
    "susp_tracking_time_unit",      # 15 Tracking Time Unit (Suspension Control)
    "susp_type",                    # 16 Suspension Type (Suspension Control)
    "susp_duration",                # 17 Suspension Duration (Suspension Control)
    "susp_time_unit",               # 18 Suspension Time Unit (Suspension Control)
    "check_for_expiry",             # 19 Check for Expiry
    "validate_instrument",          # 20 Validate Instrument
]

PAGE_SEQUENCES: Dict[str, List[str]] = {
    "merchant":            MERCHANT_SEQUENCE,
    "store":               STORE_SEQUENCE,
    "chain":               CHAIN_SEQUENCE,
    "merchant_criteria":   MERCHANT_CRITERIA_SEQUENCE,
    "instrument_criteria": INSTRUMENT_CRITERIA_SEQUENCE,
}


def _is_blank(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def parse_workbook(payload: bytes) -> Dict[str, Dict[str, object]]:
    """Read the vertical workbook and return one dict per page."""
    wb = openpyxl.load_workbook(BytesIO(payload), data_only=True)
    ws = wb.active

    page_rows: Dict[str, List[Tuple[str, object]]] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or len(row) < 5:
            continue
        page = row[1]
        attribute = row[2]
        value = row[4]  # Remarks column holds the value
        if _is_blank(page):
            continue
        page_norm = str(page).strip().lower()
        page_key = PAGE_NAMES.get(page_norm)
        if not page_key:
            continue
        page_rows.setdefault(page_key, []).append(
            (str(attribute or "").strip(), value)
        )

    out: Dict[str, Dict[str, object]] = {}
    for page_key, rows in page_rows.items():
        sequence = PAGE_SEQUENCES.get(page_key, [])
        record: Dict[str, object] = {}
        for idx, (attr, value) in enumerate(rows):
            if idx >= len(sequence):
                break
            canonical = sequence[idx]
            record[canonical] = value
        out[page_key] = record

    return out
