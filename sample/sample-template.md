# Excel Workbook Template

Create a single `.xlsx` with one sheet **per entity**. Sheet names must match
exactly (case-insensitive, hyphens/spaces normalized to underscores).

## Sheet: `demographic`

Required columns:

| demographic_id | demographic_type | demographic_org | demographic_name | address_type | address_line1 | city | state | country | postal_code | phone_type | phone_number | email_type | email |
|----------------|------------------|-----------------|------------------|--------------|---------------|------|-------|---------|-------------|------------|--------------|------------|-------|

- `demographic_type` must be `M`, `S`, or `C`
- `address_type` must be `P` or `B`
- `phone_type` ∈ `PL|PM|WL|WM|AP|1|2|3|4`
- `email_type` ∈ `P|W|1|2|3|4`
- `email` must be a valid email

## Sheet: `merchant_criteria`

| criteria | criteria_org | criteria_description | criteria_status | block_installments | block_cashback | block_international |
|----------|--------------|----------------------|-----------------|---------------------|----------------|---------------------|

- `criteria_status` ∈ `A|I`
- `block_*` ∈ `I|E|N`

## Sheet: `instrument_criteria`

| criteria_id | criteria_org | description | criteria_status | no_declines_daily | cool_of_period | months_to_purge | transaction_count | limit_type | time_limit | temp_perm | time_unit |
|-------------|--------------|-------------|-----------------|--------------------|----------------|-----------------|--------------------|------------|------------|-----------|-----------|

- Numeric ranges enforced (see README/schemas).
- `limit_type` ∈ `N|C|R|O|Q|A|D|RE|CT`
- `temp_perm` ∈ `TEMPORARY|PERMANENT`
- `time_unit` ∈ `SECOND|MINUTE|HOUR|DAY|WEEK|MONTH|YEAR`

## Sheet: `connector`

| connector_id | connector_org | connector_name | connector_status | connector_type | connector_serialization_type | authorization_type | connection_type | connector_url |
|--------------|---------------|----------------|------------------|----------------|------------------------------|--------------------|-----------------|---------------|

- `connector_status` ∈ `A|I`
- `connector_type` ∈ `IN|OUT`

## Sheet: `chain`

| chain_id | chain_org | chain_name | chain_status | chain_governing_state |
|----------|-----------|------------|--------------|------------------------|

- `chain_status` ∈ `A|I`

## Sheet: `connector_table`  (depends on `connector`)

| connector_table_id | connector_table_org | name | description | connector_type | connector_id |
|--------------------|----------------------|------|-------------|----------------|--------------|

`connector_id` must match an id in the `connector` sheet (or already in Mongo).

## Sheet: `merchant`  (depends on demographic, criteria, instrument_criteria, chain, connector_table)

| merchant_id | merchant_org | merchant_name | merchant_status | merchant_governing_state | merchant_demographics_id | criteria | instrument_criteria | merchant_chain_id | merchant_table_type | merchant_table_id |
|-------------|--------------|----------------|------------------|---------------------------|---------------------------|----------|---------------------|--------------------|----------------------|--------------------|

- `merchant_status` ∈ `A|I`
- `merchant_table_type` ∈ `IVA|SKU|COUPON|CONNECTOR`

## Sheet: `store`  (depends on merchant, demographic, criteria, instrument_criteria, connector_table)

| store_id | store_org | store_name | store_status | store_governing_state | store_merchant_id | store_demographics_id | criteria | instrument_criteria | store_table_type | store_table_id |
|----------|-----------|------------|--------------|------------------------|--------------------|------------------------|----------|---------------------|-------------------|-----------------|

- `store_status` ∈ `A|I`
- `store_table_type` ∈ `IVA|SKU|COUPON|CONNECTOR`

## Execution order (enforced by the lambda)

```
Pass 1 (parallel-safe):  demographic, merchant_criteria, instrument_criteria, connector, chain
Pass 2:                  connector_table
Pass 3:                  merchant
Pass 4:                  store
```
