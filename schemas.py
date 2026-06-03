"""
Validation schemas mirroring the Quarkus DTOs across services.

Each schema is a dict:
    "<excel_column>" : {
        "bson"       : "<bson key in mongo>",       # name as stored in Mongo
        "required"   : True/False,
        "type"       : "str" | "int" | "float" | "bool" | "list" | "dict",
        "enum"       : ["A", "I"]   (optional),
        "pattern"    : "^[AI]$"     (optional regex),
        "min"        : 0            (optional, numeric or string len),
        "max"        : 60           (optional, numeric or string len),
        "default"    : ...          (optional),
    }

Allowed/required values are taken from:
  - merchant-services           DTOs
  - merchant-criteria-service   DTOs
  - instrument-criteria-service DTOs
  - demographic-services        DTOs
  - connector-services          DTOs
  - connector-table-services    DTOs
  - store-services              DTOs

Cross-service ID fields are validated by the orchestrator.
"""

# ---------------------------------------------------------------------------
# demographic-services -> collection: demographic
# ---------------------------------------------------------------------------
DEMOGRAPHIC_SCHEMA = {
    "demographic_id": {"bson": "demographic_id", "required": True, "type": "str"},
    "demographic_type": {
        "bson": "demographic_type", "required": True, "type": "str",
        "enum": ["M", "S", "C"],
    },
    # Nested: addresses[], phone_numbers[], emails[], social_media (orchestrator merge)
}


# ---------------------------------------------------------------------------
# merchant-criteria-service -> collection: criteria
# ---------------------------------------------------------------------------
MERCHANT_CRITERIA_SCHEMA = {
    "criteria": {"bson": "criteria", "required": True, "type": "str"},
    "criteria_org": {"bson": "criteria_org", "required": True, "type": "int"},
    "criteria_description": {"bson": "criteria_description", "required": True, "type": "str"},
    "criteria_status": {
        "bson": "criteria_status", "required": True, "type": "str",
        "enum": ["A", "I"],
    },
    "block_installments": {"bson": "block_installments", "required": True, "type": "bool"},
    "block_cashback": {"bson": "block_cashback", "required": True, "type": "bool"},
    "block_international": {"bson": "block_international", "required": True, "type": "bool"},
}


# ---------------------------------------------------------------------------
# instrument-criteria-service -> collection: instrument-criteria
# ---------------------------------------------------------------------------
INSTRUMENT_CRITERIA_SCHEMA = {
    "criteria_id": {"bson": "criteria", "required": True, "type": "str"},
    "criteria_org": {"bson": "criteria_org", "required": True, "type": "int"},
    "description": {
        "bson": "description", "required": True, "type": "str",
        "min": 1, "max": 200,
    },
    "criteria_status": {
        "bson": "criteria_status", "required": True, "type": "str",
        "enum": ["A", "I"],
    },
    "no_declines_daily": {
        "bson": "no_declines_daily", "required": False, "type": "int",
        "min": 0, "max": 20,
    },
    "cool_of_period": {
        "bson": "cool_of_period", "required": False, "type": "int",
        "min": 0, "max": 60,
    },
    "months_to_purge": {
        "bson": "months_to_purge", "required": False, "type": "int",
        "min": 0, "max": 12,
    },
    "transaction_count": {
        "bson": "transaction_count", "required": False, "type": "int",
        "min": 0, "max": 10,
    },
    "limit_type": {
        "bson": "limit_type", "required": False, "type": "str",
        "enum": ["N", "C", "R", "O", "Q", "A", "D", "RE", "CT"],
    },
    "time_limit": {
        "bson": "time_limit", "required": False, "type": "int",
        "min": 0, "max": 60,
    },
    "temp_perm": {
        "bson": "temp_perm", "required": False, "type": "str",
        "enum": ["TEMPORARY", "PERMANENT"],
    },
    "time_unit": {
        "bson": "time_unit", "required": False, "type": "str",
        "enum": ["SECOND", "MINUTE", "HOUR", "DAY", "WEEK", "MONTH", "YEAR"],
    },
}


# ---------------------------------------------------------------------------
# connector-services -> collection: connector_properties
# ---------------------------------------------------------------------------
CONNECTOR_SCHEMA = {
    "connector_id": {"bson": "connector_id", "required": True, "type": "str"},
    "connector_org": {"bson": "connector_org", "required": True, "type": "int"},
    "connector_name": {"bson": "connector_name", "required": True, "type": "str"},
    "connector_status": {
        "bson": "connector_status", "required": True, "type": "str",
        "enum": ["A", "I"],
    },
    "connector_type": {
        "bson": "connector_type", "required": True, "type": "str",
        "enum": ["IN", "OUT"],
    },
    "connector_serialization_type": {
        "bson": "connector_serialization_type", "required": True, "type": "str",
    },
    "authorization_type": {
        "bson": "authorization_type", "required": True, "type": "str",
    },
    "connection_type": {
        "bson": "connection_type", "required": True, "type": "str",
    },
    "connector_url": {"bson": "connector_url", "required": False, "type": "str"},
}


# ---------------------------------------------------------------------------
# connector-table-services -> collection: connector_table
# ---------------------------------------------------------------------------
CONNECTOR_TABLE_SCHEMA = {
    "connector_table_id": {"bson": "connector_table_id", "required": True, "type": "str"},
    "connector_table_org": {"bson": "connector_table_org", "required": True, "type": "int"},
    "name": {"bson": "name", "required": True, "type": "str"},
    "description": {"bson": "description", "required": True, "type": "str"},
    "connector_type": {"bson": "connector_type", "required": True, "type": "str"},
    "connector_id": {"bson": "connector_id", "required": True, "type": "str"},  # FK
}


# ---------------------------------------------------------------------------
# merchant-services -> chain_auth (collection)
# ---------------------------------------------------------------------------
CHAIN_SCHEMA = {
    "chain_id": {"bson": "chain_id", "required": True, "type": "str"},
    "chain_org": {"bson": "chain_org", "required": True, "type": "int"},
    "chain_name": {"bson": "chain_name", "required": True, "type": "str"},
    "chain_status": {
        "bson": "chain_status", "required": True, "type": "str",
        "enum": ["A", "I"],
    },
    "chain_governing_state": {"bson": "chain_governing_state", "required": False, "type": "str"},
    "chain_demographics_id": {"bson": "chain_demographics_id", "required": False, "type": "str"},
}


# ---------------------------------------------------------------------------
# merchant-services -> merchant_auth (collection)
# ---------------------------------------------------------------------------
MERCHANT_SCHEMA = {
    "merchant_id": {"bson": "merchant_id", "required": True, "type": "str"},
    "merchant_org": {"bson": "merchant_org", "required": True, "type": "int"},
    "merchant_name": {"bson": "merchant_name", "required": True, "type": "str"},
    "merchant_status": {
        "bson": "merchant_status", "required": True, "type": "str",
        "enum": ["A", "I"],
    },
    "merchant_governing_state": {
        "bson": "merchant_governing_state", "required": True, "type": "str",
    },
    "merchant_demographics_id": {
        "bson": "merchant_demographics_id", "required": True, "type": "str",
    },
    "criteria": {"bson": "criteria", "required": False, "type": "str"},
    "instrument_criteria": {"bson": "instrument_criteria", "required": False, "type": "str"},
    "merchant_chain_id": {"bson": "merchant_chain_id", "required": False, "type": "str"},
    "merchant_table_type": {
        "bson": "merchant_table_type", "required": False, "type": "str",
        "enum": ["IVA", "SKU", "COUPON", "CONNECTOR"],
    },
    "merchant_table_id": {"bson": "merchant_table_id", "required": False, "type": "str"},
}


# ---------------------------------------------------------------------------
# store-services -> store_auth (collection)
# ---------------------------------------------------------------------------
STORE_SCHEMA = {
    "store_id": {"bson": "store_id", "required": True, "type": "str"},
    "store_org": {"bson": "store_org", "required": True, "type": "int"},
    "store_name": {"bson": "store_name", "required": True, "type": "str"},
    "store_status": {
        "bson": "store_status", "required": True, "type": "str",
        "enum": ["A", "I"],
    },
    "store_governing_state": {"bson": "store_governing_state", "required": True, "type": "str"},
    "store_merchant_id": {"bson": "store_merchant_id", "required": True, "type": "str"},
    "store_demographics_id": {"bson": "store_demographics_id", "required": True, "type": "str"},
    "criteria": {"bson": "criteria", "required": False, "type": "str"},
    "instrument_criteria": {"bson": "instrument_criteria", "required": False, "type": "str"},
    "store_table_type": {
        "bson": "store_table_type", "required": False, "type": "str",
        "enum": ["IVA", "SKU", "COUPON", "CONNECTOR"],
    },
    "store_table_id": {"bson": "store_table_id", "required": False, "type": "str"},
    "store_chain_id": {"bson": "store_chain_id", "required": False, "type": "str"},
}


# ---------------------------------------------------------------------------
# Registry: sheet name -> (schema, collection, id_field, parents)
# Parents are excel column names that must reference an already-existing id
# in the corresponding parent entity (either previously inserted in this run
# or already present in mongo).
# ---------------------------------------------------------------------------
SHEETS = {
    "demographic": {
        "schema": DEMOGRAPHIC_SCHEMA,
        "collection": "demographic",
        "id_field": "demographic_id",
        "parents": {},  # no parents
        "order": 1,
    },
    "merchant_criteria": {
        "schema": MERCHANT_CRITERIA_SCHEMA,
        "collection": "criteria",
        "id_field": "criteria",
        "parents": {},
        "order": 1,
    },
    "instrument_criteria": {
        "schema": INSTRUMENT_CRITERIA_SCHEMA,
        "collection": "instrument-criteria",
        "id_field": "criteria_id",
        "parents": {},
        "order": 1,
    },
    "connector": {
        "schema": CONNECTOR_SCHEMA,
        "collection": "connector_properties",
        "id_field": "connector_id",
        "parents": {},
        "order": 1,
    },
    "chain": {
        "schema": CHAIN_SCHEMA,
        "collection": "chain_auth",
        "id_field": "chain_id",
        "parents": {},
        "order": 1,
    },
    "connector_table": {
        "schema": CONNECTOR_TABLE_SCHEMA,
        "collection": "connector_table",
        "id_field": "connector_table_id",
        "parents": {"connector_id": "connector"},
        "order": 2,
    },
    "merchant": {
        "schema": MERCHANT_SCHEMA,
        "collection": "merchant_auth",
        "id_field": "merchant_id",
        "parents": {
            "merchant_demographics_id": "demographic",
            "criteria": "merchant_criteria",
            "instrument_criteria": "instrument_criteria",
            "merchant_chain_id": "chain",
            # merchant_table_id can point at connector_table when type=CONNECTOR
            "merchant_table_id": "connector_table",
        },
        "order": 3,
    },
    "store": {
        "schema": STORE_SCHEMA,
        "collection": "store_auth",
        "id_field": "store_id",
        "parents": {
            "store_merchant_id": "merchant",
            "store_demographics_id": "demographic",
            "criteria": "merchant_criteria",
            "instrument_criteria": "instrument_criteria",
            "store_table_id": "connector_table",
            "store_chain_id": "chain",
        },
        "order": 4,
    },
}
