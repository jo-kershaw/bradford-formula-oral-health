# Decision log

## 2026-07-16 — Repository ownership

**Decision:** Create the repository in my personal GitHub account

**Reason:** The repository can be transferred later if appropriate.

---

## 2026-07-16 — Repository visibility

**Decision:** Begin with a private repository.

**Reason:** The project is at an early stage and its eventual ownership and release conditions have not yet been agreed.

---

## 2026-07-16 — Development data

**Decision:** Develop initially using synthetic data only.

**Reason:** This allows the code structure and causal-analysis workflow to be developed before access to the Secure Data Environment, without using sensitive records.

---

## 2026-07-16 — Data directories

**Decision:** Use `synthetic_data/` and remove the generic `data/` directory.

**Reason:** Reduces the risk of confusing synthetic development data with secure project data.

---

## 2026-07-16 — Repository structure

**Decision:** Use a single repository with a Python `src` layout.

**Reason:** The project currently forms one coherent analysis workflow. The `src` layout supports reliable imports and leaves open the option of extracting reusable packages later.

---

## 2026-07-16 — Project licence

**Decision:** Do not apply an open-source licence at this stage; record the project as proprietary temporarily.

**Reason:** Code ownership and possible public release need to be agreed with the supervisors and relevant organisations first.
