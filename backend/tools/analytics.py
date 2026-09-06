"""
Deterministic analytics functions for the REVIA synthetic sales dataset.
"""

from collections import defaultdict

from .dataset import get_dataset


def total_sales(data):
    """Return total sales across the dataset."""
    return sum(record["sales"] for record in data)


def sales_by_region(data):
    """Return total sales grouped by region."""
    totals = defaultdict(int)

    for record in data:
        totals[record["region"]] += record["sales"]

    return dict(sorted(totals.items()))


def sales_by_product(data):
    """Return total sales grouped by product."""
    totals = defaultdict(int)

    for record in data:
        totals[record["product"]] += record["sales"]

    return dict(sorted(totals.items()))


def top_products(data, limit=5):
    """Return products ranked by total sales."""
    totals = sales_by_product(data)

    ranked = sorted(
        totals.items(),
        key=lambda item: (-item[1], item[0]),
    )

    return [
        {
            "product": product,
            "sales": sales,
        }
        for product, sales in ranked[:limit]
    ]


def sales_trend(data):
    """Return total sales grouped by date."""
    totals = defaultdict(int)

    for record in data:
        totals[record["date"]] += record["sales"]

    return dict(sorted(totals.items()))


if __name__ == "__main__":
    data = get_dataset()

    print("Total sales:")
    print(total_sales(data))

    print("\nSales by region:")
    print(sales_by_region(data))

    print("\nSales by product:")
    print(sales_by_product(data))

    print("\nTop products:")
    print(top_products(data))

    print("\nSales trend:")
    trend = sales_trend(data)
    print(f"Days: {len(trend)}")
    print(f"First day: {next(iter(trend.items()))}")