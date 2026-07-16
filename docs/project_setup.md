# How this repository is organised

## 2026-07-16

### Repository

Created on personal GitHub account.

---

### Directory structure

Used `src` layout.

Reason: recommended by Python Packaging Authority and avoids accidental imports.

---

### Data

Renamed `data` to `synthetic_data`.

Reason: reinforce that secure patient data should never be placed in the repository.

---

### Packaging

Installed with

pip install -e .

Reason: allows normal imports during development without reinstalling.
