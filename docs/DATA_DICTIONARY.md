# Data Dictionary & ETL Specification

## 1. Архитектура хранилища (Star Schema)

Витрина данных построена в PostgreSQL по схеме «Звезда» для оптимизации аналитических запросов и работы BI-инструментов.

### Таблица фактов: `fact_sales`
Содержит очищенные транзакционные данные о продажах.
* `order_id` (BIGINT, PK) — уникальный идентификатор заказа.
* `sale_date` (DATE, Indexed) — дата совершения продажи.
* `product_id` (INT, FK → `dim_products`) — идентификатор товара.
* `region_id` (INT, FK → `dim_regions`) — идентификатор региона.
* `quantity` (NUMERIC) — количество проданных единиц (строго `> 0`).
* `discount_pct` (NUMERIC) — размер применённой скидки (от `0.00` до `0.15`).
* `gross_revenue` (NUMERIC) — валовая выручка до учёта скидки (`quantity * unit_price`).
* `net_revenue` (NUMERIC) — чистая выручка с учётом скидки (`gross_revenue * (1 - discount_pct)`).

### Таблица измерений: `dim_products`
* `product_id` (INT, PK) — идентификатор SKU.
* `product_name` (TEXT) — наименование товарной позиции.
* `category` (TEXT) — продуктовая категория (`Confectionery`, `Petcare`, `Snacks & Gum`).
* `unit_price` (NUMERIC) — базовая отпускная цена за единицу.

### Таблица измерений: `dim_regions`
* `region_id` (INT, PK) — идентификатор региона.
* `city` (TEXT) — город реализации.
* `federal_district` (TEXT) — федеральный округ.

## 2. Правила контроля качества данных (Data Quality)

На этапе Transform в `src/etl_pipeline.py` применяются следующие проверки:
1. **Дедупликация:** удаление повторных записей с идентичным `order_id` (`keep='first'`).
2. **Валидация доменов:** фильтрация записей с пропущенными (`NaN`) или неположительными (`<= 0`) значениями `quantity`.
3. **Контроль целостности:** формирование первичных ключей (`PRIMARY KEY`) и B-Tree индексов по полям фильтрации и соединения (`sale_date`, `product_id`).

## 3. Аналитические витрины и DAX-метрики

* **`v_monthly_category_kpi`** — SQL-представление с использованием `CTE`, оконной функции `LAG()` для расчёта помесячной динамики выручки (`mom_growth_pct`) и `RANK()` для ранжирования связок «город — категория».
* **`Выручка (Net)`** — `SUM(fact_sales[net_revenue])`.
* **`Продано единиц`** — `SUM(fact_sales[quantity])`.
* **`Средний чек`** — `DIVIDE([Выручка (Net)], COUNT(fact_sales[order_id]), 0)`.
