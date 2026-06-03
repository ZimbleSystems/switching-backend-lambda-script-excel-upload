"""Free-text Excel value -> canonical service enum.

Each map is keyed by the lower-cased / stripped Excel value. If a value
is unrecognised, the original is returned unchanged so the validator can
flag it explicitly with a useful message ("must be one of [...] got X").
"""
from __future__ import annotations

import unicodedata
from typing import Any, Dict


def _norm_key(s: str) -> str:
    """Lowercase, strip accents — matches config-metadata element `state` displays."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


# config-metadata-switching application.yml — element: state (MX)
_STATE_ENTRIES: tuple[tuple[str, str], ...] = (
    ("AGU", "Aguascalientes"),
    ("BCN", "Baja California"),
    ("BCS", "Baja California Sur"),
    ("CAM", "Campeche"),
    ("CHP", "Chiapas"),
    ("CHH", "Chihuahua"),
    ("COA", "Coahuila de Zaragoza"),
    ("COL", "Colima"),
    ("CMX", "Ciudad de México"),
    ("DUR", "Durango"),
    ("GUA", "Guanajuato"),
    ("GRO", "Guerrero"),
    ("HID", "Hidalgo"),
    ("JAL", "Jalisco"),
    ("MEX", "Estado de México"),
    ("MIC", "Michoacán de Ocampo"),
    ("MOR", "Morelos"),
    ("NAY", "Nayarit"),
    ("NLE", "Nuevo León"),
    ("OAX", "Oaxaca"),
    ("PUE", "Puebla"),
    ("QUE", "Querétaro"),
    ("ROO", "Quintana Roo"),
    ("SLP", "San Luis Potosí"),
    ("SIN", "Sinaloa"),
    ("SON", "Sonora"),
    ("TAB", "Tabasco"),
    ("TAM", "Tamaulipas"),
    ("TLA", "Tlaxcala"),
    ("VER", "Veracruz de Ignacio de la Llave"),
    ("YUC", "Yucatán"),
    ("ZAC", "Zacatecas"),
)

_STATE_CODES: frozenset[str] = frozenset(code for code, _ in _STATE_ENTRIES)

GOVERNING_STATE_MAP: Dict[str, str] = {}
for _code, _display in _STATE_ENTRIES:
    GOVERNING_STATE_MAP[_norm_key(_code)] = _code
    GOVERNING_STATE_MAP[_norm_key(_display)] = _code

# Common Excel / typo variants without accents
GOVERNING_STATE_MAP.update({
    _norm_key("Nuevo Leon"): "NLE",
    _norm_key("Ciudad de Mexico"): "CMX",
    _norm_key("Estado de Mexico"): "MEX",
    _norm_key("Michoacan de Ocampo"): "MIC",
    _norm_key("Queretaro"): "QUE",
    _norm_key("San Luis Potosi"): "SLP",
    _norm_key("Yucatan"): "YUC",
})

STATUS_MAP: Dict[str, str] = {
    "activo": "A", "activado": "A", "active": "A", "activated": "A", "a": "A",
    "inactivo": "I", "inactive": "I", "i": "I",
}

BLOCK_MAP: Dict[str, str] = {
    "yes": "E", "y": "E", "true": "E", "maybe": "N",
    "no": "N", "n": "N", "false": "N",
    "include": "I", "included": "I",
    "exclude": "E", "excluded": "E",
    "none": "N",
}

ADDRESS_TYPE_MAP: Dict[str, str] = {
    "physical": "P", "p": "P",
    "billing": "B", "b": "B",
}

PHONE_TYPE_MAP: Dict[str, str] = {
    "linea fija": "PL", "personal landline": "PL", "pl": "PL",
    "linea movil": "PM", "personal mobile": "PM", "pm": "PM",
    "trabajo fija": "WL", "work landline": "WL", "wl": "WL",
    "trabajo movil": "WM", "work mobile": "WM", "wm": "WM",
    "alterno": "AP", "alternate": "AP", "ap": "AP",
}

EMAIL_TYPE_MAP: Dict[str, str] = {
    "personal": "P", "p": "P",
    "trabajo": "W", "work": "W", "w": "W",
    "organizacional": "W", "organizational": "W", "organisation": "W",
}

TIME_UNIT_MAP: Dict[str, str] = {
    "second": "SECOND", "seconds": "SECOND", "sec": "SECOND", "secs": "SECOND",
    "minute": "MINUTE", "minutes": "MINUTE", "min": "MINUTE", "mins": "MINUTE",
    "hour": "HOUR", "hours": "HOUR", "hr": "HOUR", "hrs": "HOUR",
    "day": "DAY", "days": "DAY",
    "week": "WEEK", "weeks": "WEEK",
    "month": "MONTH", "months": "MONTH",
    "year": "YEAR", "years": "YEAR",
}

TEMP_PERM_MAP: Dict[str, str] = {
    "temporary": "TEMPORARY", "temporal": "TEMPORARY", "temp": "TEMPORARY",
    "permanent": "PERMANENT", "permanente": "PERMANENT", "perm": "PERMANENT",
}

BOOLEAN_MAP: Dict[str, bool] = {
    "yes": True, "y": True, "true": True, "1": True, "si": True,
    "no": False, "n": False, "false": False, "0": False,
}


def _try_map(value: Any, mapping: Dict[str, Any]) -> Any:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return mapping.get(s.lower(), value)


def _governing_state(value: Any) -> Any:
    """Map metadata `state` display (or code) -> stored code (e.g. NLE)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    upper = s.upper()
    if upper in _STATE_CODES:
        return upper
    return GOVERNING_STATE_MAP.get(_norm_key(s), value)


def transform(field: str, value: Any) -> Any:
    """Map free-text values to canonical enum values when the field name
    matches a known semantic family. Otherwise the original is returned."""
    if value is None:
        return None
    f = field.lower()
    if f.endswith("_governing_state"):
        return _governing_state(value)
    if f.endswith("_status"):
        return _try_map(value, STATUS_MAP)
    if f.startswith("block_"):
        return _try_map(value, BLOCK_MAP)
    if f == "address_type":
        return _try_map(value, ADDRESS_TYPE_MAP)
    if f == "phone_type":
        return _try_map(value, PHONE_TYPE_MAP)
    if f == "email_type":
        return _try_map(value, EMAIL_TYPE_MAP)
    if f.endswith("time_unit") or f == "time_unit":
        return _try_map(value, TIME_UNIT_MAP)
    if f == "temp_perm":
        return _try_map(value, TEMP_PERM_MAP)
    if f in ("check_for_expiry", "validate_instrument"):
        return _try_map(value, BOOLEAN_MAP)
    return value


def transform_all(record: Dict[str, Any]) -> Dict[str, Any]:
    return {k: transform(k, v) for k, v in record.items()}
