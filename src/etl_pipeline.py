import logging
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
DB_URL = "postgresql+psycopg2://analyst:analyst_password@localhost:5433/fmcg_analytics"


def extract_raw_data(n_rows: int = 5000) -> pd.DataFrame:
    """Генерация сырых данных продаж с имитацией типичных дефектов (дубли, пропуски, выбросы)."""
    rng = np.random.default_rng(42)
    start_date = datetime(2025, 1, 1)

    products = [
        (101, "ChocoBar Classic 50g", "Confectionery", 65.0),
        (102, "ChocoBar Dark 50g", "Confectionery", 72.0),
        (103, "CrispyWafer Pack", "Confectionery", 110.0),
        (201, "PetCare Dry Mix 1kg", "Petcare", 420.0),
        (202, "PetCare Wet Pouch 85g", "Petcare", 48.0),
        (301, "MintGum Fresh", "Snacks & Gum", 45.0),
    ]
    regions = [
        (1, "Москва", "Центральный ФО"),
        (2, "Санкт-Петербург", "Северо-Западный ФО"),
        (3, "Казань", "Приволжский ФО"),
        (4, "Новосибирск", "Сибирский ФО"),
    ]

    prod_idx = rng.integers(0, len(products), size=n_rows)
    reg_idx = rng.integers(0, len(regions), size=n_rows)

    df = pd.DataFrame({
        "order_id": np.arange(10000, 10000 + n_rows),
        "sale_date": [start_date + timedelta(days=int(d)) for d in rng.integers(0, 650, size=n_rows)],
        "product_id": [products[i][0] for i in prod_idx],
        "product_name": [products[i][1] for i in prod_idx],
        "category": [products[i][2] for i in prod_idx],
        "unit_price": [products[i][3] for i in prod_idx],
        "region_id": [regions[i][0] for i in reg_idx],
        "city": [regions[i][1] for i in reg_idx],
        "federal_district": [regions[i][2] for i in reg_idx],
        "quantity": rng.integers(1, 25, size=n_rows).astype(float),
        "discount_pct": rng.choice([0.0, 0.05, 0.10, 0.15], size=n_rows, p=[0.6, 0.2, 0.15, 0.05]),
    })

    # Вносим дефекты для демонстрации работы модуля Data Quality
    df.loc[rng.choice(df.index, size=40, replace=False), "quantity"] = np.nan
    df.loc[rng.choice(df.index, size=15, replace=False), "quantity"] = -5.0
    df = pd.concat([df, df.iloc[:30]], ignore_index=True)
    return df


def transform_and_validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Очистка данных, контроль целостности и нормализация в Star Schema."""
    initial_count = len(df)

    df = df.drop_duplicates(subset=["order_id"], keep="first").copy()
    dups_removed = initial_count - len(df)

    invalid_qty = df["quantity"].isna() | (df["quantity"] <= 0)
    invalid_removed = int(invalid_qty.sum())
    df = df[~invalid_qty].copy()

    df["gross_revenue"] = (df["quantity"] * df["unit_price"]).round(2)
    df["net_revenue"] = (df["gross_revenue"] * (1 - df["discount_pct"])).round(2)
    df["sale_date"] = pd.to_datetime(df["sale_date"]).dt.date

    logging.info(
        f"DQ Report | Исходно: {initial_count} | Удалено дублей: {dups_removed} | "
        f"Удалено аномалий: {invalid_removed} | Итого валидных записей: {len(df)}"
    )

    dim_products = (
        df[["product_id", "product_name", "category", "unit_price"]]
        .drop_duplicates(subset=["product_id"])
        .sort_values("product_id")
    )
    dim_regions = (
        df[["region_id", "city", "federal_district"]]
        .drop_duplicates(subset=["region_id"])
        .sort_values("region_id")
    )
    fact_sales = df[[
        "order_id", "sale_date", "product_id", "region_id",
        "quantity", "discount_pct", "gross_revenue", "net_revenue"
    ]]

    return dim_products, dim_regions, fact_sales


def load_to_postgres(dim_products: pd.DataFrame, dim_regions: pd.DataFrame, fact_sales: pd.DataFrame) -> None:
    """Загрузка витрины в PostgreSQL и создание индексов."""
    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS v_monthly_category_kpi CASCADE;"))
        dim_products.to_sql("dim_products", conn, if_exists="replace", index=False)
        dim_regions.to_sql("dim_regions", conn, if_exists="replace", index=False)
        fact_sales.to_sql("fact_sales", conn, if_exists="replace", index=False)

        conn.execute(text("ALTER TABLE dim_products ADD PRIMARY KEY (product_id);"))
        conn.execute(text("ALTER TABLE dim_regions ADD PRIMARY KEY (region_id);"))
        conn.execute(text("ALTER TABLE fact_sales ADD PRIMARY KEY (order_id);"))
        conn.execute(text("CREATE INDEX idx_fact_sales_date ON fact_sales(sale_date);"))
        conn.execute(text("CREATE INDEX idx_fact_sales_product ON fact_sales(product_id);"))

    logging.info("Загрузка в PostgreSQL завершена успешно.")


if __name__ == "__main__":
    raw = extract_raw_data()
    products_df, regions_df, sales_df = transform_and_validate(raw)
    load_to_postgres(products_df, regions_df, sales_df)
