# Premier Padel BGA — Inventory System

## Test Data Cleanup Rule

**CRITICAL:** After running any tests (pytest, manual API tests, or any script that creates test data), you MUST delete ALL dummy data created during testing. This includes:

- **Users**: any with emails matching `*@battery.test`, `*@test.premierpadel.com`, or test patterns
- **Products**: names matching `__test_*__`, `__battery_*__`, `BATTERY_TEST_*`, `__oversell_*__`, `__inv_exceed_*__`, `CSV_TEST_*`
- **Categories**: names matching `__test_*__`, `__csv_test_*__`
- **Suppliers**: names matching `__test_*__`, `__csv_test_*__`
- **Sales, sale_items, inventory_entries, internal_use**: any records created during testing
- **Cash closings**: any with test dates (e.g., 2019-01-01, 2020-01-01)
- **Audit log**: entries referencing test entities

Delete in FK-safe order: audit_log → cash_closings → sale_items → sales → internal_use → inventory_entries → products → categories → suppliers → users.

Never leave test artifacts in the database. The production database should only contain real data and the seed CSV inventory.
