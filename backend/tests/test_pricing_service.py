"""Tests for the pricing calculation service."""
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.pricing import PricingRule
from app.models.supplier import Supplier
from app.models.user import User

# Use isolated in-memory DB for service tests
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = Session()
    yield session
    session.close()


@pytest.fixture
def supplier(db):
    user = User(id=uuid.uuid4(), email="s@test.com", hashed_password="x")
    db.add(user)
    db.flush()
    s = Supplier(id=uuid.uuid4(), user_id=user.id, name="Test Supplier")
    db.add(s)
    db.commit()
    return s


def test_always_rule(db, supplier):
    from app.services.pricing_service import calculate_retail_price

    rule = PricingRule(
        supplier_id=supplier.id,
        priority=1,
        condition_type="always",
        condition_value={},
        markup_type="percent",
        markup_value="50",
        round_to=None,
    )
    db.add(rule)
    db.commit()

    result = calculate_retail_price(
        cost="10.00",
        supplier_id=supplier.id,
        product_type=None,
        tags=[],
        db=db,
    )
    assert float(result["price"]) == pytest.approx(15.00)


def test_cost_range_rule(db, supplier):
    from app.services.pricing_service import calculate_retail_price

    rule = PricingRule(
        supplier_id=supplier.id,
        priority=10,
        condition_type="cost_range",
        condition_value={"min": 5, "max": 50},
        markup_type="percent",
        markup_value="30",
        round_to=None,
    )
    db.add(rule)
    db.commit()

    result = calculate_retail_price(
        cost="20.00",
        supplier_id=supplier.id,
        product_type=None,
        tags=[],
        db=db,
    )
    assert float(result["price"]) == pytest.approx(26.00)


def test_product_type_rule(db, supplier):
    from app.services.pricing_service import calculate_retail_price

    rule = PricingRule(
        supplier_id=supplier.id,
        priority=5,
        condition_type="product_type",
        condition_value={"type": "Widget"},
        markup_type="fixed",
        markup_value="5",
        round_to=None,
    )
    db.add(rule)
    db.commit()

    result = calculate_retail_price(
        cost="20.00",
        supplier_id=supplier.id,
        product_type="Widget",
        tags=[],
        db=db,
    )
    assert float(result["price"]) == pytest.approx(25.00)


def test_rounding(db, supplier):
    from app.services.pricing_service import calculate_retail_price

    rule = PricingRule(
        supplier_id=supplier.id,
        priority=1,
        condition_type="always",
        condition_value={},
        markup_type="percent",
        markup_value="40",
        round_to="0.99",
    )
    db.add(rule)
    db.commit()

    result = calculate_retail_price(
        cost="10.00",
        supplier_id=supplier.id,
        product_type=None,
        tags=[],
        db=db,
    )
    # 10 * 1.4 = 14.00 → rounded to .99 → 13.99
    assert float(result["price"]) == pytest.approx(13.99)


def test_no_matching_rule_returns_cost(db, supplier):
    from app.services.pricing_service import calculate_retail_price

    # Cost range rule that doesn't match our cost
    rule = PricingRule(
        supplier_id=supplier.id,
        priority=1,
        condition_type="cost_range",
        condition_value={"min": 100, "max": 500},
        markup_type="percent",
        markup_value="20",
        round_to=None,
    )
    db.add(rule)
    db.commit()

    result = calculate_retail_price(
        cost="10.00",
        supplier_id=supplier.id,
        product_type=None,
        tags=[],
        db=db,
    )
    # No rule matches → returns cost unchanged
    assert float(result["price"]) == pytest.approx(10.00)
    assert result["rule_name"] is None
