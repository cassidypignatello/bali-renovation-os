"""Tests for BoQ Pydantic schema validators."""

from app.schemas.boq import BoQItemBase, BoQItemExtracted


class TestItemNumberCap:
    """item_number must fit the boq_items.item_number VARCHAR(20) column.

    GPT-4o occasionally emits an item_number longer than 20 chars (e.g. a
    description fragment). Without capping, the batch insert fails with
    Postgres 22001 and aborts the whole job before pricing.
    """

    def test_long_item_number_capped_to_20(self):
        raw = "A.1.2.3.4.5.6.7.8.9.10.11.12"
        item = BoQItemBase(item_number=raw, description="x")
        assert item.item_number == raw[:20]

    def test_short_item_number_unchanged(self):
        item = BoQItemBase(item_number="A.1", description="x")
        assert item.item_number == "A.1"

    def test_none_item_number_stays_none(self):
        item = BoQItemBase(item_number=None, description="x")
        assert item.item_number is None

    def test_cap_applies_through_extracted_subclass(self):
        # The extracted subclass is what the persistence path constructs.
        raw = "X" * 50
        item = BoQItemExtracted(item_number=raw, description="x")
        assert item.item_number == raw[:20]
