"""Analysis shared by SQL Server aggregates and synthetic aggregates."""
import warnings

import numpy as np
import pandas as pd


def validate_aggregates(df, cfg):
    required = {"birth_year", "ethnicity", "deprivation", "formula", "n_children"} | {w.key for w in cfg.windows}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing aggregated study population columns: {sorted(missing)}")
    if df.empty:
        raise ValueError("Selected study population is empty")
    out = df.copy()
    for c in ["birth_year", "formula", "n_children"] + [w.key for w in cfg.windows]:
        out[c] = pd.to_numeric(out[c], errors="raise")
        if not np.all(np.isfinite(out[c])) or not np.all(out[c] == np.floor(out[c])):
            raise ValueError(f"{c} must contain finite integer counts")
    if not out.formula.isin([0, 1]).all():
        raise ValueError("formula must be binary 0/1")
    if (out.n_children <= 0).any():
        raise ValueError("All aggregated rows must have positive n_children")
    for w in cfg.windows:
        if (out[w.key] < 0).any() or (out[w.key] > out.n_children).any():
            raise ValueError(f"Invalid GA count for {w.name}")
    if out.duplicated(["birth_year", "ethnicity", "deprivation", "formula"]).any():
        raise ValueError("Duplicate aggregation strata")
    return out


def two_by_two(df, cfg):
    totals = df.groupby("formula").sum(numeric_only=True)
    rows = []
    for w in cfg.windows:
        for exposure, label in [(1, "Formula"), (0, "Other children")]:
            n = int(totals.loc[exposure, "n_children"]) if exposure in totals.index else 0
            ga = int(totals.loc[exposure, w.key]) if exposure in totals.index else 0
            rows.append({
                "ga_window": w.name, "group": label, "formula": exposure,
                "n_children": n, "ga_yes": ga, "ga_no": n - ga,
                "ga_percent": round(100 * ga / n, 4) if n else np.nan
            })
    return pd.DataFrame(rows)


def table_by_birth_year(df, cfg):
    y = (df.groupby(["birth_year", "formula"], as_index=False)
         .agg(n_children=("n_children", "sum"), ga_yes=(cfg.primary.key, "sum")))
    y["ga_percent"] = 100 * y.ga_yes / y.n_children
    return y


def table_by_ethnicity_deprivation(df, cfg):
    y = (df.groupby(["ethnicity", "deprivation", "formula"], as_index=False)
         .agg(n_children=("n_children", "sum"), ga_yes=(cfg.primary.key, "sum")))
    y["ga_percent"] = 100 * y.ga_yes / y.n_children
    return y


def fit_adjusted(df, cfg):
    """Original approach: observational associations only
    """
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    from patsy import build_design_matrices, dmatrix
    from scipy.special import expit

    m = df.copy()
    m["ga_fraction"] = m[cfg.primary.key] / m.n_children
    if set(m.formula) != {0, 1}:
        return None, "Only one exposure group is present"
    if m[cfg.primary.key].sum() == 0:
        return None, "No GA events in the selected cohort/window"
    rhs = "formula" + "".join(" + C(" + c + ")" for c in cfg.adjust_for)
    formula = "ga_fraction ~ " + rhs
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = smf.glm(formula=formula, data=m, family=sm.families.Binomial(),
                            freq_weights=m.n_children).fit()
        if not model.converged:
            return None, "GLM did not converge"
        if any("perfect separation" in str(x.message).lower() for x in caught):
            return None, "Model exhibited perfect separation"
        with_formula, without_formula = m.copy(), m.copy()
        with_formula["formula"] = 1
        without_formula["formula"] = 0
        # Build a consistent design matrix without relying on statsmodels internals.
        design = dmatrix(rhs, m, return_type="dataframe")
        if list(design.columns) != list(model.params.index):
            raise ValueError("Predictor columns differ from the fitted model")
        X1 = np.asarray(build_design_matrices([design.design_info], with_formula)[0])
        X0 = np.asarray(build_design_matrices([design.design_info], without_formula)[0])
        weights = m.n_children.to_numpy(dtype=float)
        weights /= weights.sum()
        p1 = float(weights @ expit(X1 @ model.params.to_numpy()))
        p0 = float(weights @ expit(X0 @ model.params.to_numpy()))
        rng = np.random.default_rng(cfg.seed)
        draws = rng.multivariate_normal(model.params.to_numpy(),
                                        model.cov_params().to_numpy(), size=cfg.ci_draws)
        d1 = weights @ expit(X1 @ draws.T)
        d0 = weights @ expit(X0 @ draws.T)
        def limits(x):
            return [float(z) for z in np.quantile(x, [0.025, 0.975])]
        beta, se = float(model.params["formula"]), float(model.bse["formula"])
        result = {
            "model_formula": formula,
            "children": int(m.n_children.sum()), "ga_cases": int(m[cfg.primary.key].sum()),
            "converged": bool(model.converged),
            "odds_ratio": float(np.exp(beta)),
            "odds_ratio_ci": [float(np.exp(beta-1.96*se)), float(np.exp(beta+1.96*se))],
            "p_value": float(model.pvalues["formula"]),
            "formula_pct": 100*p1,
            "formula_pct_ci": [100*z for z in limits(d1)],
            "other_pct": 100*p0,
            "other_pct_ci": [100*z for z in limits(d0)],
            "difference_pp": 100*(p1-p0),
            "difference_pp_ci": [100*z for z in limits(d1-d0)],
            "relative_difference_pct": 100*(p1/p0-1),
            "relative_difference_ci": [100*z for z in limits(d1/d0-1)],
        }
        return result, None
    except Exception as e:
        return None, f"Model cannot be fitted for these choices: {type(e).__name__}: {e}"


def analyse(data, cfg):
    cohort = validate_aggregates(data["cohort"], cfg)
    tables = {
        "cohort": cohort,
        "two_by_two": two_by_two(cohort, cfg),
        "by_birth_year": table_by_birth_year(cohort, cfg),
        "by_ethnicity_deprivation": table_by_ethnicity_deprivation(cohort, cfg),
        "prescriptions_by_year": data["prescriptions_by_year"],
        "ga_by_year": data["ga_by_year"], "first_ga_by_year": data["first_ga_by_year"],
        "prescription_frequency": data["prescription_frequency"],
        "products_by_name": data["products_by_name"],
    }
    model, reason = fit_adjusted(cohort, cfg)
    return tables, model, reason
