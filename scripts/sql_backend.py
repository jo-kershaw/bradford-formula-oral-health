"""SQL Server adapter. Every SELECT returns aggregate counts, not person IDs."""
from datetime import timedelta

import pandas as pd
from sqlalchemy import text


def sql_parts(cfg):
    """Safe parameterized query, matching the original BB_age_window_models3 schema."""
    params = {
        "birth_start": cfg.birth_start, "birth_end_next": cfg.birth_end + timedelta(days=1),
        "rx_age_start": cfg.exposure_age_start, "rx_age_end": cfg.exposure_age_end,
        "ga_calendar_start": cfg.ga_calendar_start,
        "ga_calendar_end_next": cfg.ga_calendar_end + timedelta(days=1),
        "min_rx": cfg.min_rx,
    }
    # Lookup product exclusions are bound parameters (not interpolated into SQL).
    exclusion_sql = ""
    for i, term in enumerate(cfg.excluded_terms):
        if not term or any(char in term for char in ['%', '_', '[']):
            raise ValueError("Excluded product terms must be nonempty literal fragments, without SQL wildcards")
        name = f"exclude_term_{i}"
        exclusion_sql += f"\n      AND UPPER(NameOfMedication) NOT LIKE :{name}"
        params[name] = "%" + term.upper() + "%"
    event_count = "COUNT(DISTINCT rx_date)" if cfg.rx_mode == "distinct_dates" else "COUNT(*)"
    ga_columns = ",\n        ".join(
        f"MAX(CASE WHEN e.ga_date >= DATEADD(month, {w.start_months}, c.dob) "
        f"AND e.ga_date < DATEADD(month, {w.end_months}, c.dob) "
        f"THEN 1 ELSE 0 END) AS {w.key}"
        for w in cfg.windows
    )
    ga_coalesced = ",\n        ".join(f"COALESCE(g.{w.key}, 0) AS {w.key}" for w in cfg.windows)
    ctes = f"""
WITH imd AS (
    SELECT UPPER(LTRIM(RTRIM(lsoa_code_2011))) COLLATE DATABASE_DEFAULT AS lsoa,
           MAX(TRY_CONVERT(int, index_of_multiple_deprivation_imd_decile_where_1_is_most_depr)) AS imd_decile
    FROM [ref_Lookups].[dbo].[lkp_IMD_2019]
    WHERE local_authority_district_name_2019 = 'Bradford'
    GROUP BY UPPER(LTRIM(RTRIM(lsoa_code_2011))) COLLATE DATABASE_DEFAULT
),
children AS (
    SELECT p.person_id, CAST(p.DOB AS date) AS dob, YEAR(p.DOB) AS birth_year,
           p.census_ethnicity, i.imd_decile
    FROM dbo.cb_Master_Population p
    JOIN imd i ON UPPER(LTRIM(RTRIM(p.LSOA))) COLLATE DATABASE_DEFAULT = i.lsoa
    WHERE p.DOB >= :birth_start AND p.DOB < :birth_end_next
      AND i.imd_decile BETWEEN 1 AND 10
),
formula_names AS (
    SELECT DISTINCT UPPER(LTRIM(RTRIM(NameOfMedication))) COLLATE DATABASE_DEFAULT AS med_name
    FROM dbo.medication_names_and_dmd_codes
    WHERE NameOfMedication IS NOT NULL {exclusion_sql}
),
rx_events AS (
    SELECT c.person_id, d.rx_date
    FROM children c
    JOIN dbo.tbl_SRPrimaryCareMedication m ON m.person_id = c.person_id
    JOIN formula_names f ON UPPER(LTRIM(RTRIM(m.NameOfMedication))) COLLATE DATABASE_DEFAULT = f.med_name
    CROSS APPLY (
        SELECT COALESCE(TRY_CONVERT(date, m.DateEvent, 103), TRY_CONVERT(date, m.DateEvent, 23)) AS rx_date
    ) d
    WHERE d.rx_date >= DATEADD(month, :rx_age_start, c.dob)
      AND d.rx_date < DATEADD(month, :rx_age_end, c.dob)
),
formula_ids AS (
    SELECT person_id
    FROM rx_events
    GROUP BY person_id
    HAVING {event_count} >= :min_rx
),
ga_events AS (
    SELECT c.person_id, d.ga_date
    FROM children c
    JOIN dbo.cb_Master_GA g ON g.person_id = c.person_id
    CROSS APPLY (
        SELECT COALESCE(TRY_CONVERT(date, g.Date_of_GA, 103), TRY_CONVERT(date, g.Date_of_GA, 23)) AS ga_date
    ) d
    WHERE d.ga_date >= :ga_calendar_start AND d.ga_date < :ga_calendar_end_next
),
ga_flags AS (
    SELECT c.person_id,
        {ga_columns}
    FROM children c
    LEFT JOIN ga_events e ON e.person_id = c.person_id
    GROUP BY c.person_id
),
classified AS (
    SELECT c.person_id, c.dob, c.birth_year,
        CASE
          WHEN c.census_ethnicity LIKE 'White: English or Welsh%' THEN 'White British'
          WHEN c.census_ethnicity LIKE 'Asian or Asian British: Pakistani%' THEN 'Pakistani'
          WHEN c.census_ethnicity IS NULL OR LTRIM(RTRIM(c.census_ethnicity)) = ''
            OR c.census_ethnicity = 'Unknown/Refuse to say' THEN 'Unknown'
          ELSE 'Other ethnicities'
        END AS ethnicity,
        CASE
          WHEN c.imd_decile BETWEEN 1 AND 3 THEN '1-3 More deprived'
          WHEN c.imd_decile BETWEEN 4 AND 6 THEN '4-6 Middle'
          ELSE '7-10 Less deprived'
        END AS deprivation,
        CASE WHEN f.person_id IS NULL THEN 0 ELSE 1 END AS formula,
        {ga_coalesced}
    FROM children c
    LEFT JOIN formula_ids f ON f.person_id = c.person_id
    LEFT JOIN ga_flags g ON g.person_id = c.person_id
)
"""
    return ctes, params


def build_queries(cfg):
    ctes, params = sql_parts(cfg)
    cols = ["birth_year", "ethnicity", "deprivation", "formula"]
    agg_ga = ",\n  ".join(f"SUM({w.key}) AS {w.key}" for w in cfg.windows)
    cohort = ctes + f"""
SELECT {', '.join(cols)}, COUNT(*) AS n_children,
  {agg_ga}
FROM classified
GROUP BY {', '.join(cols)}
ORDER BY {', '.join(cols)}
"""
    prescribing = ctes + """
SELECT YEAR(daily.rx_date) AS prescription_year,
       COUNT(*) AS n_prescribing_dates,
       COUNT(DISTINCT daily.person_id) AS n_children
FROM (SELECT DISTINCT person_id, rx_date FROM rx_events) daily
JOIN formula_ids f ON f.person_id = daily.person_id
GROUP BY YEAR(daily.rx_date)
ORDER BY prescription_year
"""
    w = cfg.primary
    ga_year = ctes + f"""
SELECT YEAR(e.ga_date) AS ga_year, c.formula,
       COUNT(*) AS n_ga_records,
       COUNT(DISTINCT e.person_id) AS n_children_with_ga
FROM ga_events e
JOIN classified c ON e.person_id = c.person_id
WHERE e.ga_date >= DATEADD(month, {w.start_months}, c.dob)
  AND e.ga_date < DATEADD(month, {w.end_months}, c.dob)
GROUP BY YEAR(e.ga_date), c.formula
ORDER BY ga_year, c.formula
"""

    # One child = one first GA within the selected primary age/calendar window.
    # Formula exposure and selected population come from analysis_settings.py.
    # The GA records are restricted to the same window used by ga_flags.
    first_ga_year = ctes + f"""
SELECT YEAR(first_ga_date) AS first_ga_year,
       COUNT(*) AS n_children
FROM (
    SELECT e.person_id, MIN(e.ga_date) AS first_ga_date
    FROM ga_events e
    JOIN classified c ON e.person_id = c.person_id
    WHERE c.formula = 1
      AND e.ga_date >= DATEADD(month, {w.start_months}, c.dob)
      AND e.ga_date < DATEADD(month, {w.end_months}, c.dob)
    GROUP BY e.person_id
) first_events
GROUP BY YEAR(first_ga_date)
ORDER BY first_ga_year
"""

    # One row for each formula-frequency category; all records remain in SQL.
    count_expr = "COUNT(DISTINCT rx_date)" if cfg.rx_mode == "distinct_dates" else "COUNT(*)"
    frequency = ctes + f"""
SELECT CASE
  WHEN rx.n_rx IS NULL THEN '0'
  WHEN rx.n_rx = 1 THEN '1'
  WHEN rx.n_rx BETWEEN 2 AND 4 THEN '2-4'
  WHEN rx.n_rx BETWEEN 5 AND 9 THEN '5-9'
  WHEN rx.n_rx BETWEEN 10 AND 19 THEN '10-19'
  WHEN rx.n_rx BETWEEN 20 AND 49 THEN '20-49'
  ELSE '50+'
END AS frequency_band, COUNT(*) AS n_children
FROM classified c
LEFT JOIN (
  SELECT person_id, {count_expr} AS n_rx
  FROM rx_events
  GROUP BY person_id
) rx ON c.person_id = rx.person_id
GROUP BY CASE
  WHEN rx.n_rx IS NULL THEN '0'
  WHEN rx.n_rx = 1 THEN '1'
  WHEN rx.n_rx BETWEEN 2 AND 4 THEN '2-4'
  WHEN rx.n_rx BETWEEN 5 AND 9 THEN '5-9'
  WHEN rx.n_rx BETWEEN 10 AND 19 THEN '10-19'
  WHEN rx.n_rx BETWEEN 20 AND 49 THEN '20-49'
  ELSE '50+'
END
"""
    products = ctes + """
SELECT UPPER(LTRIM(RTRIM(m.NameOfMedication))) AS product,
       COUNT(DISTINCT c.person_id) AS n_children,
       COUNT(*) AS n_records
FROM children c
JOIN dbo.tbl_SRPrimaryCareMedication m ON m.person_id = c.person_id
JOIN formula_names f ON UPPER(LTRIM(RTRIM(m.NameOfMedication))) COLLATE DATABASE_DEFAULT = f.med_name
CROSS APPLY (
    SELECT COALESCE(TRY_CONVERT(date, m.DateEvent, 103), TRY_CONVERT(date, m.DateEvent, 23)) AS rx_date
) d
WHERE d.rx_date >= DATEADD(month, :rx_age_start, c.dob)
  AND d.rx_date < DATEADD(month, :rx_age_end, c.dob)
GROUP BY UPPER(LTRIM(RTRIM(m.NameOfMedication)))
ORDER BY n_children DESC, n_records DESC
"""
    return {"cohort": cohort, "prescriptions_by_year": prescribing,
            "ga_by_year": ga_year, "first_ga_by_year": first_ga_year, "prescription_frequency": frequency,
            "products_by_name": products}, params


def load_aggregates(engine, cfg):
    queries, params = build_queries(cfg)
    results = {}
    with engine.connect() as conn:
        for key, query in queries.items():
            results[key] = pd.read_sql(text(query), conn, params=params)
    return results


def load_source_coverage(engine):
    """Get the actual date ranges of the principal source tables, as 3 summary rows.

    The formula bar includes only specialist-formula names from the lookup;
    observation-period and GA bars are unfiltered source-table ranges. All
    three are independent of analysis_settings.py.
    Verify dbo.observation_period is the name of the observation table in your
    Bradford database. No person identifiers or individual dates are returned.
    """
    query = text("""
WITH formula_names AS (
    SELECT DISTINCT
        UPPER(LTRIM(RTRIM(NameOfMedication)))
            COLLATE DATABASE_DEFAULT AS med_name
    FROM dbo.medication_names_and_dmd_codes
    WHERE NameOfMedication IS NOT NULL
)
SELECT 'Formula prescriptions' AS dataset,
       MIN(COALESCE(TRY_CONVERT(date, m.DateEvent, 103),
                    TRY_CONVERT(date, m.DateEvent, 23))) AS start_date,
       MAX(COALESCE(TRY_CONVERT(date, m.DateEvent, 103),
                    TRY_CONVERT(date, m.DateEvent, 23))) AS end_date
FROM dbo.tbl_SRPrimaryCareMedication m
JOIN formula_names f
  ON UPPER(LTRIM(RTRIM(m.NameOfMedication)))
     COLLATE DATABASE_DEFAULT = f.med_name
UNION ALL
SELECT 'Observation period' AS dataset,
       MIN(TRY_CONVERT(date, observation_period_start_date)) AS start_date,
       MAX(TRY_CONVERT(date, observation_period_end_date)) AS end_date
FROM dbo.observation_period
UNION ALL
SELECT 'Dental GA' AS dataset,
       MIN(COALESCE(TRY_CONVERT(date, Date_of_GA, 103),
                    TRY_CONVERT(date, Date_of_GA, 23))) AS start_date,
       MAX(COALESCE(TRY_CONVERT(date, Date_of_GA, 103),
                    TRY_CONVERT(date, Date_of_GA, 23))) AS end_date
FROM dbo.cb_Master_GA
""")
    with engine.connect() as conn:
        return pd.read_sql(query, conn)


# ============================================================
# STANDARD DATA OVERVIEW: CALENDAR-YEAR ACTIVITY
# These describe ALL records in the two project source extracts.
# They are NOT restricted by the chosen study population.
# SQL returns annual totals only (no person-level records).
# ============================================================

def load_source_yearly_overview(engine):
    """Return yearly GA, prescribing-date and prescribing-child counts.

    Dental GA: records of any age in cb_Master_GA.
    Formula: distinct person + calendar date in the project medication extract.
    One child may appear in several years, so yearly child totals cannot be added
    to find a count of unique children across the entire dataset.
    """
    ga_sql = text("""
WITH dated_ga AS (
    SELECT COALESCE(
        TRY_CONVERT(date, Date_of_GA, 103),
        TRY_CONVERT(date, Date_of_GA, 23)
    ) AS ga_date
    FROM dbo.cb_Master_GA
)
SELECT YEAR(ga_date) AS ga_year,
       COUNT(*) AS n_ga
FROM dated_ga
WHERE ga_date IS NOT NULL
GROUP BY YEAR(ga_date)
ORDER BY ga_year;
""")

    medication_sql = text("""
WITH formula_names AS (
    SELECT DISTINCT UPPER(LTRIM(RTRIM(NameOfMedication)))
        COLLATE DATABASE_DEFAULT AS med_name
    FROM dbo.medication_names_and_dmd_codes
    WHERE NameOfMedication IS NOT NULL
),
dated_medication AS (
    SELECT m.person_id,
           COALESCE(
               TRY_CONVERT(date, m.DateEvent, 103),
               TRY_CONVERT(date, m.DateEvent, 23)
           ) AS prescription_date
    FROM dbo.tbl_SRPrimaryCareMedication m
    JOIN formula_names f
      ON UPPER(LTRIM(RTRIM(m.NameOfMedication)))
         COLLATE DATABASE_DEFAULT = f.med_name
),
unique_prescribing_dates AS (
    SELECT DISTINCT person_id, prescription_date
    FROM dated_medication
    WHERE person_id IS NOT NULL AND prescription_date IS NOT NULL
)
SELECT YEAR(prescription_date) AS year,
       COUNT(*) AS n_prescriptions,
       COUNT(DISTINCT person_id) AS n_children
FROM unique_prescribing_dates
GROUP BY YEAR(prescription_date)
ORDER BY year;
""")

    with engine.connect() as conn:
        ga_by_year = pd.read_sql(ga_sql, conn)
        medication_by_year = pd.read_sql(medication_sql, conn)

    return {
        "dental_ga_by_year": ga_by_year,
        "formula_prescriptions_by_year": medication_by_year[
            ["year", "n_prescriptions"]
        ].copy(),
        "children_prescribed_formula_by_year": medication_by_year[
            ["year", "n_children"]
        ].copy(),
    }

def load_formula_by_ethnicity_overview(engine):
    import pandas as pd

    query = """
-- MATCHED_POPULATION_DENOMINATOR_V12: ethnicity, all birth years
WITH bradford_lsoa AS (
    SELECT DISTINCT UPPER(LTRIM(RTRIM(lsoa_code_2011)))
        COLLATE DATABASE_DEFAULT AS lsoa
    FROM [ref_Lookups].[dbo].[lkp_IMD_2019]
    WHERE local_authority_district_name_2019 = 'Bradford'
),
-- Original formula extract, identified by person_id, NOT added to population.
formula_ids AS (
    SELECT DISTINCT f.person_id
    FROM dbo.person f
    WHERE f.birth_datetime >= '2012-01-01'
      AND f.birth_datetime < '2019-01-01'
      AND EXISTS (
          SELECT 1
          FROM dbo.personLSOA l
          JOIN bradford_lsoa b
            ON UPPER(LTRIM(RTRIM(l.LSOA)))
               COLLATE DATABASE_DEFAULT = b.lsoa
          WHERE l.person_id = f.person_id
      )
),
-- Classify BOTH formula and non-formula children using the same field.
-- One row per person, even if the source contains repeated records.
population_ranked AS (
    SELECT p.person_id,
           YEAR(p.DOB) AS birth_year,
           p.census_ethnicity AS ethnicity,
           ROW_NUMBER() OVER (
               PARTITION BY p.person_id
               ORDER BY CASE WHEN p.census_ethnicity IS NULL
                                 OR LTRIM(RTRIM(p.census_ethnicity)) = ''
                             THEN 1 ELSE 0 END,
                        p.DOB, p.census_ethnicity, p.LSOA
           ) AS person_row
    FROM dbo.cb_Master_Population p
    JOIN bradford_lsoa b
      ON UPPER(LTRIM(RTRIM(p.LSOA)))
         COLLATE DATABASE_DEFAULT = b.lsoa
    WHERE p.DOB >= '2012-01-01'
      AND p.DOB < '2019-01-01'
      AND p.person_id IS NOT NULL
),
classified AS (
    SELECT p.person_id, p.birth_year,
           CASE WHEN f.person_id IS NOT NULL THEN 1 ELSE 0 END AS formula_flag,
           CASE
               WHEN p.ethnicity LIKE 'White: English or Welsh%'
                   THEN 'White British'
               WHEN p.ethnicity LIKE 'Asian or Asian British: Pakistani%'
                   THEN 'Pakistani'
               WHEN p.ethnicity LIKE 'White:Any other White%'
                   THEN 'Other White'
               WHEN p.ethnicity LIKE 'Mixed multiple ethnic groups: White and Asian%'
                   THEN 'White and Asian'
               WHEN p.ethnicity IS NULL
                   OR LTRIM(RTRIM(p.ethnicity)) = ''
                   OR p.ethnicity = 'Unknown/Refuse to say'
                   THEN 'Unknown / missing'
               ELSE 'Other ethnicities'
           END AS ethnic_group
    FROM population_ranked p
    LEFT JOIN formula_ids f ON f.person_id = p.person_id
    WHERE p.person_row = 1
),
counts AS (
    SELECT ethnic_group,
           COUNT(*) AS population_children,
           SUM(formula_flag) AS formula_children
    FROM classified
    GROUP BY ethnic_group
)
SELECT ethnic_group,
       formula_children,
       population_children,
       population_children - formula_children AS non_formula_children,
       population_children AS total_children,
       ROUND(100.0 * formula_children /
             NULLIF(SUM(formula_children) OVER (), 0), 2) AS pct_of_formula_cohort,
       ROUND(100.0 * population_children /
             NULLIF(SUM(population_children) OVER (), 0), 2) AS pct_of_new_population,
       ROUND(100.0 * formula_children /
             NULLIF(population_children, 0), 2) AS provisional_formula_pct
FROM counts
ORDER BY population_children DESC;
"""

    with engine.connect() as conn:
        ethnicity_comparison = pd.read_sql(query, conn)


# ============================================================
# FORMULA PRESCRIBING BY ETHNICITY AND BIRTH YEAR
# Bradford LSOAs, 2012–2018
# ============================================================

    query_by_year = """
-- MATCHED_POPULATION_DENOMINATOR_V12: ethnicity, by birth year
WITH bradford_lsoa AS (
    SELECT DISTINCT UPPER(LTRIM(RTRIM(lsoa_code_2011)))
        COLLATE DATABASE_DEFAULT AS lsoa
    FROM [ref_Lookups].[dbo].[lkp_IMD_2019]
    WHERE local_authority_district_name_2019 = 'Bradford'
),
-- Original formula extract, identified by person_id, NOT added to population.
formula_ids AS (
    SELECT DISTINCT f.person_id
    FROM dbo.person f
    WHERE f.birth_datetime >= '2012-01-01'
      AND f.birth_datetime < '2019-01-01'
      AND EXISTS (
          SELECT 1
          FROM dbo.personLSOA l
          JOIN bradford_lsoa b
            ON UPPER(LTRIM(RTRIM(l.LSOA)))
               COLLATE DATABASE_DEFAULT = b.lsoa
          WHERE l.person_id = f.person_id
      )
),
-- Classify BOTH formula and non-formula children using the same field.
-- One row per person, even if the source contains repeated records.
population_ranked AS (
    SELECT p.person_id,
           YEAR(p.DOB) AS birth_year,
           p.census_ethnicity AS ethnicity,
           ROW_NUMBER() OVER (
               PARTITION BY p.person_id
               ORDER BY CASE WHEN p.census_ethnicity IS NULL
                                 OR LTRIM(RTRIM(p.census_ethnicity)) = ''
                             THEN 1 ELSE 0 END,
                        p.DOB, p.census_ethnicity, p.LSOA
           ) AS person_row
    FROM dbo.cb_Master_Population p
    JOIN bradford_lsoa b
      ON UPPER(LTRIM(RTRIM(p.LSOA)))
         COLLATE DATABASE_DEFAULT = b.lsoa
    WHERE p.DOB >= '2012-01-01'
      AND p.DOB < '2019-01-01'
      AND p.person_id IS NOT NULL
),
classified AS (
    SELECT p.person_id, p.birth_year,
           CASE WHEN f.person_id IS NOT NULL THEN 1 ELSE 0 END AS formula_flag,
           CASE
               WHEN p.ethnicity LIKE 'White: English or Welsh%'
                   THEN 'White British'
               WHEN p.ethnicity LIKE 'Asian or Asian British: Pakistani%'
                   THEN 'Pakistani'
               WHEN p.ethnicity LIKE 'White:Any other White%'
                   THEN 'Other White'
               WHEN p.ethnicity LIKE 'Mixed multiple ethnic groups: White and Asian%'
                   THEN 'White and Asian'
               WHEN p.ethnicity IS NULL
                   OR LTRIM(RTRIM(p.ethnicity)) = ''
                   OR p.ethnicity = 'Unknown/Refuse to say'
                   THEN 'Unknown / missing'
               ELSE 'Other ethnicities'
           END AS ethnic_group
    FROM population_ranked p
    LEFT JOIN formula_ids f ON f.person_id = p.person_id
    WHERE p.person_row = 1
),
counts AS (
    SELECT birth_year, ethnic_group,
           COUNT(*) AS total_children,
           SUM(formula_flag) AS formula_children
    FROM classified
    WHERE ethnic_group IN ('White British', 'Pakistani')
    GROUP BY birth_year, ethnic_group
)
SELECT birth_year, ethnic_group,
       formula_children,
       total_children - formula_children AS other_children,
       total_children,
       ROUND(100.0 * formula_children / NULLIF(total_children, 0), 2)
           AS provisional_formula_pct
FROM counts
ORDER BY birth_year, ethnic_group;
"""

    with engine.connect() as conn:
        ethnicity_by_year = pd.read_sql(query_by_year, conn)

    return {
        "formula_by_ethnicity": ethnicity_comparison,
        "formula_by_ethnicity_year": ethnicity_by_year
    }

def load_ga_by_ethnicity_formula_overview(engine):

    query = """
    WITH bradford_lsoa AS (
        SELECT DISTINCT
            UPPER(LTRIM(RTRIM(lsoa_code_2011)))
                COLLATE DATABASE_DEFAULT AS lsoa
        FROM [ref_Lookups].[dbo].[lkp_IMD_2019]
        WHERE local_authority_district_name_2019 = 'Bradford'
    ),

    formula_names AS (
        SELECT DISTINCT
            UPPER(LTRIM(RTRIM(NameOfMedication)))
                COLLATE DATABASE_DEFAULT AS med_name
        FROM dbo.medication_names_and_dmd_codes
    ),

    -- Children prescribed specialist formula before age 1
    formula_in_infancy AS (
        SELECT DISTINCT p.person_id
        FROM dbo.person p

        JOIN dbo.tbl_SRPrimaryCareMedication m
            ON p.person_id = m.person_id

        JOIN formula_names f
            ON UPPER(LTRIM(RTRIM(m.NameOfMedication)))
                COLLATE DATABASE_DEFAULT = f.med_name

        WHERE COALESCE(
            TRY_CONVERT(date, m.DateEvent, 103),
            TRY_CONVERT(date, m.DateEvent, 23)
        ) >= CAST(p.birth_datetime AS date)

        AND COALESCE(
            TRY_CONVERT(date, m.DateEvent, 103),
            TRY_CONVERT(date, m.DateEvent, 23)
        ) < DATEADD(year, 1, CAST(p.birth_datetime AS date))
    ),

    -- Dental GA occurring between ages 1 and under 6
    ga_children AS (
        SELECT DISTINCT p.person_id
        FROM dbo.person p

        JOIN dbo.cb_Master_GA g
            ON p.person_id = g.person_id

        WHERE COALESCE(
            TRY_CONVERT(date, g.Date_of_GA, 103),
            TRY_CONVERT(date, g.Date_of_GA, 23)
        ) >= DATEADD(year, 1, CAST(p.birth_datetime AS date))

        AND COALESCE(
            TRY_CONVERT(date, g.Date_of_GA, 103),
            TRY_CONVERT(date, g.Date_of_GA, 23)
        ) < DATEADD(year, 6, CAST(p.birth_datetime AS date))
    ),

    eligible_children AS (
        SELECT
            p.person_id,
            p.ethnicity_source_value AS ethnicity,

            CASE WHEN g.person_id IS NOT NULL
                THEN 1 ELSE 0 END AS has_ga

        FROM dbo.person p

        JOIN formula_in_infancy f
            ON p.person_id = f.person_id

        LEFT JOIN ga_children g
            ON p.person_id = g.person_id

        WHERE p.birth_datetime >= '2015-01-01'
          AND p.birth_datetime < '2019-01-01'

          AND EXISTS (
              SELECT 1
              FROM dbo.personLSOA l
              JOIN bradford_lsoa b
                ON UPPER(LTRIM(RTRIM(l.LSOA)))
                    COLLATE DATABASE_DEFAULT = b.lsoa
              WHERE l.person_id = p.person_id
          )
    ),

    classified AS (
        SELECT
            person_id,
            has_ga,

            CASE
                WHEN ethnicity LIKE 'White: English or Welsh%'
                    THEN 'White British'

                WHEN ethnicity LIKE 'Asian or Asian British: Pakistani%'
                    THEN 'Pakistani'

                WHEN ethnicity LIKE 'White:Any other White%'
                    THEN 'Other White'

                WHEN ethnicity LIKE
                    'Mixed multiple ethnic groups: White and Asian%'
                    THEN 'White and Asian'

                WHEN ethnicity IS NULL
                  OR ethnicity = ''
                  OR ethnicity = 'Unknown/Refuse to say'
                    THEN 'Unknown / missing'

                ELSE 'Other ethnicities'
            END AS ethnic_group

        FROM eligible_children
    )

    SELECT
        ethnic_group,

        COUNT(*) AS formula_children,

        SUM(has_ga) AS formula_with_ga,

        COUNT(*) - SUM(has_ga) AS formula_without_ga,

        ROUND(
            100.0 * SUM(has_ga) / NULLIF(COUNT(*), 0),
            2
        ) AS ga_pct

    FROM classified

    GROUP BY ethnic_group
    ORDER BY formula_children DESC;
    """

    with engine.connect() as conn:
        ga_ethnicity = pd.read_sql(query, conn)

    return {
        "ga_by_ethnicity_formula": ga_ethnicity
    }

def load_ga_by_imd_group_overview(engine):
    import pandas as pd

    query = """
    WITH imd AS (
        SELECT
            UPPER(LTRIM(RTRIM(lsoa_code_2011)))
                COLLATE DATABASE_DEFAULT AS lsoa,
            MAX(TRY_CONVERT(
                int,
                index_of_multiple_deprivation_imd_decile_where_1_is_most_depr
            )) AS imd_decile
        FROM [ref_Lookups].[dbo].[lkp_IMD_2019]
        WHERE local_authority_district_name_2019 = 'Bradford'
        GROUP BY
            UPPER(LTRIM(RTRIM(lsoa_code_2011)))
                COLLATE DATABASE_DEFAULT
    ),

    formula_names AS (
        SELECT DISTINCT
            UPPER(LTRIM(RTRIM(NameOfMedication)))
                COLLATE DATABASE_DEFAULT AS med_name
        FROM dbo.medication_names_and_dmd_codes
    ),

    formula_ids AS (
        SELECT DISTINCT p.person_id
        FROM dbo.person p
        JOIN dbo.tbl_SRPrimaryCareMedication m
            ON p.person_id = m.person_id
        JOIN formula_names f
            ON UPPER(LTRIM(RTRIM(m.NameOfMedication)))
                COLLATE DATABASE_DEFAULT = f.med_name
        WHERE COALESCE(
            TRY_CONVERT(date, m.DateEvent, 103),
            TRY_CONVERT(date, m.DateEvent, 23)
        ) >= CAST(p.birth_datetime AS date)
        AND COALESCE(
            TRY_CONVERT(date, m.DateEvent, 103),
            TRY_CONVERT(date, m.DateEvent, 23)
        ) < DATEADD(year, 1, CAST(p.birth_datetime AS date))
    ),

    ga_ids AS (
        SELECT DISTINCT p.person_id
        FROM dbo.person p
        JOIN dbo.cb_Master_GA g
            ON p.person_id = g.person_id
        WHERE COALESCE(
            TRY_CONVERT(date, g.Date_of_GA, 103),
            TRY_CONVERT(date, g.Date_of_GA, 23)
        ) >= DATEADD(year, 1, CAST(p.birth_datetime AS date))
        AND COALESCE(
            TRY_CONVERT(date, g.Date_of_GA, 103),
            TRY_CONVERT(date, g.Date_of_GA, 23)
        ) < DATEADD(year, 6, CAST(p.birth_datetime AS date))
    ),

    children AS (
        SELECT DISTINCT
            p.person_id,
            i.imd_decile,
            CASE WHEN g.person_id IS NOT NULL
                THEN 1 ELSE 0 END AS has_ga

        FROM dbo.person p
        JOIN formula_ids f
            ON p.person_id = f.person_id
        JOIN dbo.personLSOA l
            ON p.person_id = l.person_id
        JOIN imd i
            ON UPPER(LTRIM(RTRIM(l.LSOA)))
                COLLATE DATABASE_DEFAULT = i.lsoa
        LEFT JOIN ga_ids g
            ON p.person_id = g.person_id

        WHERE p.birth_datetime >= '2015-01-01'
        AND p.birth_datetime < '2019-01-01'
    ),

    grouped AS (
        SELECT
            CASE
                WHEN imd_decile BETWEEN 1 AND 3
                    THEN '1–3 More deprived'
                WHEN imd_decile BETWEEN 4 AND 6
                    THEN '4–6 Middle'
                WHEN imd_decile BETWEEN 7 AND 10
                    THEN '7–10 Less deprived'
                ELSE 'Unknown'
            END AS deprivation_group,
            has_ga
        FROM children
    )

    SELECT
        deprivation_group,
        COUNT(*) AS formula_children,
        SUM(has_ga) AS formula_with_ga,
        COUNT(*) - SUM(has_ga) AS formula_without_ga,
        ROUND(
            100.0 * SUM(has_ga) / NULLIF(COUNT(*), 0),
            2
        ) AS ga_pct
    FROM grouped
    GROUP BY deprivation_group
    ORDER BY deprivation_group;
    """

    with engine.connect() as conn:
        ga_by_imd = pd.read_sql(query, conn)

    return {
        "ga_by_imd_group": ga_by_imd
    }

def load_formula_by_imd_decile_overview(engine):

    query = """
-- MATCHED_POPULATION_DENOMINATOR_V12: deprivation decile
WITH imd AS (
    SELECT UPPER(LTRIM(RTRIM(lsoa_code_2011)))
               COLLATE DATABASE_DEFAULT AS lsoa,
           MAX(TRY_CONVERT(int,
               index_of_multiple_deprivation_imd_decile_where_1_is_most_depr))
               AS imd_decile
    FROM [ref_Lookups].[dbo].[lkp_IMD_2019]
    WHERE local_authority_district_name_2019 = 'Bradford'
    GROUP BY UPPER(LTRIM(RTRIM(lsoa_code_2011)))
             COLLATE DATABASE_DEFAULT
),
formula_ids AS (
    SELECT DISTINCT f.person_id
    FROM dbo.person f
    WHERE f.birth_datetime >= '2012-01-01'
      AND f.birth_datetime < '2019-01-01'
      AND EXISTS (
          SELECT 1 FROM dbo.personLSOA l
          JOIN imd i
            ON UPPER(LTRIM(RTRIM(l.LSOA)))
               COLLATE DATABASE_DEFAULT = i.lsoa
          WHERE l.person_id = f.person_id
      )
),
population_ranked AS (
    SELECT p.person_id, i.imd_decile,
           ROW_NUMBER() OVER (
               PARTITION BY p.person_id
               ORDER BY CASE WHEN i.imd_decile IS NULL THEN 1 ELSE 0 END,
                        i.imd_decile, p.DOB, p.LSOA
           ) AS person_row
    FROM dbo.cb_Master_Population p
    JOIN imd i
      ON UPPER(LTRIM(RTRIM(p.LSOA)))
         COLLATE DATABASE_DEFAULT = i.lsoa
    WHERE p.DOB >= '2012-01-01'
      AND p.DOB < '2019-01-01'
      AND p.person_id IS NOT NULL
),
classified AS (
    SELECT p.person_id, p.imd_decile,
           CASE WHEN f.person_id IS NOT NULL THEN 1 ELSE 0 END AS formula_flag
    FROM population_ranked p
    LEFT JOIN formula_ids f ON f.person_id = p.person_id
    WHERE p.person_row = 1
),
counts AS (
    SELECT imd_decile,
           COUNT(*) AS population_children,
           SUM(formula_flag) AS formula_children
    FROM classified
    GROUP BY imd_decile
)
SELECT imd_decile,
       formula_children,
       population_children,
       population_children - formula_children AS non_formula_children,
       ROUND(100.0 * formula_children /
             NULLIF(SUM(formula_children) OVER (), 0), 2) AS pct_formula_cohort,
       ROUND(100.0 * population_children /
             NULLIF(SUM(population_children) OVER (), 0), 2) AS pct_new_population,
       ROUND(100.0 * formula_children /
             NULLIF(population_children, 0), 2) AS provisional_formula_pct
FROM counts
ORDER BY imd_decile;
"""

    with engine.connect() as conn:
        imd_comparison = pd.read_sql(query, conn)

    return {
        "formula_by_imd_decile": imd_comparison
    }

def load_source_ga_children_yearly_overview(engine):
    """Annual unique formula prescribing dates and children with any GA.

    Returns yearly counts only; never exports person IDs from SQL.
    GA membership means at least one dated dental GA at any age, before
    or after prescribing. A child can appear in multiple calendar years.
    """
    query = text("""
WITH formula_names AS (
    SELECT DISTINCT UPPER(LTRIM(RTRIM(NameOfMedication)))
        COLLATE DATABASE_DEFAULT AS med_name
    FROM dbo.medication_names_and_dmd_codes
    WHERE NameOfMedication IS NOT NULL
),
ga_child_ids AS (
    SELECT DISTINCT g.person_id
    FROM dbo.cb_Master_GA g
    WHERE g.person_id IS NOT NULL
      AND COALESCE(TRY_CONVERT(date, g.Date_of_GA, 103),
                   TRY_CONVERT(date, g.Date_of_GA, 23)) IS NOT NULL
),
formula_prescribing_dates AS (
    SELECT DISTINCT m.person_id, d.rx_date
    FROM dbo.tbl_SRPrimaryCareMedication m
    JOIN formula_names f
      ON UPPER(LTRIM(RTRIM(m.NameOfMedication)))
         COLLATE DATABASE_DEFAULT = f.med_name
    JOIN ga_child_ids g ON g.person_id = m.person_id
    CROSS APPLY (
        SELECT COALESCE(TRY_CONVERT(date, m.DateEvent, 103),
                        TRY_CONVERT(date, m.DateEvent, 23)) AS rx_date
    ) d
    WHERE m.person_id IS NOT NULL AND d.rx_date IS NOT NULL
)
SELECT YEAR(rx_date) AS year,
       COUNT(*) AS n_prescriptions,
       COUNT(DISTINCT person_id) AS n_children
FROM formula_prescribing_dates
GROUP BY YEAR(rx_date)
ORDER BY year;
""")
    with engine.connect() as conn:
        by_year = pd.read_sql(query, conn)
    return {
        "formula_prescriptions_by_year_ga_children": by_year[
            ["year", "n_prescriptions"]
        ].copy(),
        "children_prescribed_formula_by_year_ga_children": by_year[
            ["year", "n_children"]
        ].copy(),
    }