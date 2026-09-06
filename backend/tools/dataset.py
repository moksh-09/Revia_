"""
Deterministic synthetic sales dataset for REVIA analytics tools.

This dataset contains no real customer or financial data.
"""

from datetime import date, timedelta


REGIONS = [
    "North",
    "South",
    "East",
    "West",
]

PRODUCTS = [
    "Laptop",
    "Monitor",
    "Keyboard",
    "Mouse",
    "Headphones",
]


def get_dataset():
    """
    Return a deterministic synthetic sales dataset.

    Each record contains:
        date
        region
        product
        units
        unit_price
        sales
    """

    records = []

    start_date = date(2026, 1, 1)

    # Fixed deterministic multipliers.
    region_multiplier = {
        "North": 1.15,
        "South": 0.95,
        "East": 1.05,
        "West": 1.20,
    }

    product_price = {
        "Laptop": 75000,
        "Monitor": 18000,
        "Keyboard": 3500,
        "Mouse": 1800,
        "Headphones": 5000,
    }

    for day_index in range(30):
        current_date = start_date + timedelta(days=day_index)

        for region_index, region in enumerate(REGIONS):
            for product_index, product in enumerate(PRODUCTS):

                units = (
                    4
                    + ((day_index * 3 + region_index * 2 + product_index) % 9)
                )

                units = int(round(units * region_multiplier[region]))

                unit_price = product_price[product]

                # Deterministic sales calculation.
                sales = units * unit_price

                records.append(
                    {
                        "date": current_date.isoformat(),
                        "region": region,
                        "product": product,
                        "units": units,
                        "unit_price": unit_price,
                        "sales": sales,
                    }
                )

    return records


if __name__ == "__main__":
    data = get_dataset()

    print(f"Records: {len(data)}")
    print("First record:")
    print(data[0])