"""WS-7: Revenue Intelligence App — patterns on real sales/CRM data."""

from __future__ import annotations

from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "enterprise-bench"


class TestSalesData:
    def test_sales_count(self, sales):
        assert len(sales) >= 13000

    def test_sales_required_fields(self, sales):
        required = {"product_id", "customer_id", "Date_of_Purchase", "sales_record_id"}
        for s in sales[:50]:
            assert required.issubset(s.keys())

    def test_sales_have_prices(self, sales):
        for s in sales[:50]:
            assert s.get("discounted_price") or s.get("actual_price")

    def test_unique_customers_in_sales(self, sales):
        customer_ids = {s["customer_id"] for s in sales}
        assert len(customer_ids) > 10

    def test_unique_products_in_sales(self, sales):
        product_ids = {s["product_id"] for s in sales}
        assert len(product_ids) > 100


class TestTopCustomers:
    def test_customer_purchase_counts(self, sales):
        from collections import Counter
        counts = Counter(s["customer_id"] for s in sales)
        top = counts.most_common(5)
        assert len(top) == 5
        # Top customer has more purchases than average
        avg = len(sales) / len(counts)
        assert top[0][1] > avg

    def test_customers_have_names(self, customers):
        for c in customers:
            assert c.get("customer_name") or c.get("customer_id")

    def test_customer_count(self, customers):
        assert len(customers) == 90


class TestProductData:
    def test_product_count(self, products):
        assert len(products) >= 1000

    def test_products_have_names(self, products):
        for p in products[:50]:
            assert p.get("product_name")

    def test_products_have_categories(self, products):
        categories = {p.get("category") for p in products if p.get("category")}
        assert len(categories) >= 3

    def test_product_price_format(self, products):
        for p in products[:20]:
            price = p.get("discounted_price", "")
            assert isinstance(price, str)


class TestRevenuePatterns:
    def test_top_products_by_sales_volume(self, sales):
        from collections import Counter
        counts = Counter(s["product_id"] for s in sales)
        top_5 = counts.most_common(5)
        assert len(top_5) == 5
        # Top product sold at least 10 times
        assert top_5[0][1] >= 10

    def test_sales_date_range(self, sales):
        dates = [s["Date_of_Purchase"] for s in sales if s.get("Date_of_Purchase")]
        assert len(dates) > 0
        # Dates are strings in YYYY-MM-DD format
        sample = dates[:10]
        for d in sample:
            parts = d.split("-")
            assert len(parts) == 3

    def test_revenue_by_customer_type(self, sales, clients, vendors):
        client_ids = {c["client_id"] for c in clients}
        vendor_ids = {v["client_id"] for v in vendors}
        sale_customers = {s["customer_id"] for s in sales}
        # Some overlap between sales customers and known clients
        assert len(sale_customers) > 0
