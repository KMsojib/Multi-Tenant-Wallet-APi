# Multi-Tenant Wallet & Ledger API

A clean and well-structured **Multi-Tenant Wallet / Ledger service** built with **Django** and **Django REST Framework**.

Multiple tenants (merchants or organizations) share the same platform while their data remains fully isolated. The system treats the **ledger as the single source of truth**, supports atomic transfers, row-level locking, and idempotent money operations.

---

## Features

- Multi-tenant isolation via `X-Tenant-ID` header **or** API Key
- Immutable ledger (balance is calculated from transactions)
- Atomic transfers with `select_for_update` + deadlock prevention
- Idempotent Deposit / Withdraw / Transfer (scoped per tenant)
- Money stored as integer minor units (never float)
- Clear validation and error responses
- Paginated transaction history + live balance
- Comprehensive test suite for critical flows

---

## Tech Stack

- Python 3.11+
- Django 5 / 6
- Django REST Framework
- SQLite (can be switched to PostgreSQL easily)
- `drf-spectacular` for API documentation
- UUID primary keys

---