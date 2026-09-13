from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.wallet import MonitoringMode, Wallet, WalletCluster

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_attribution(**overrides: Any) -> Attribution:
    fields: dict[str, Any] = {
        "source": "nansen",
        "source_entity_id": None,
        "confidence": Decimal("0.6"),
        "evidence": "labeled smart-money wallet",
        "verification_status": VerificationStatus.UNVERIFIED,
        "observed_at": NOW,
    }
    fields.update(overrides)
    return Attribution(**fields)


def make_wallet(**overrides: Any) -> Wallet:
    fields: dict[str, Any] = {
        "address": "0xabc",
        "chain": "ethereum",
        "entity_id": None,
        "alias": None,
        "labels": ("smart_money",),
        "tags": (),
        "confidence": Decimal("0.7"),
        "trust_score": Decimal("0.6"),
        "risk_score": Decimal("0.1"),
        "enabled": True,
        "influence_weight": Decimal("0.3"),
        "max_signal_weight": Decimal("0.2"),
        "max_allocation": Decimal("1000"),
        "min_transaction_value": Decimal("100"),
        "attributions": (make_attribution(),),
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return Wallet(**fields)


def test_a_well_formed_wallet_is_accepted_and_defaults_to_observe() -> None:
    wallet = make_wallet()
    assert wallet.monitoring_mode is MonitoringMode.OBSERVE
    assert wallet.id == "ethereum:0xabc"


def test_wallet_can_be_explicitly_set_to_ai_evaluated() -> None:
    wallet = make_wallet(monitoring_mode=MonitoringMode.AI_EVALUATED)
    assert wallet.monitoring_mode is MonitoringMode.AI_EVALUATED


def test_wallet_requires_at_least_one_attribution() -> None:
    with pytest.raises(ValueError, match="attribution"):
        make_wallet(attributions=())


def test_wallet_requires_address_and_chain() -> None:
    with pytest.raises(ValueError, match="address is required"):
        make_wallet(address="")
    with pytest.raises(ValueError, match="chain is required"):
        make_wallet(chain="")


def test_wallet_max_allocation_must_be_positive_when_set() -> None:
    with pytest.raises(ValueError, match="max_allocation must be positive"):
        make_wallet(max_allocation=Decimal("0"))


def test_wallet_min_transaction_value_cannot_be_negative() -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        make_wallet(min_transaction_value=Decimal("-1"))


def test_wallet_scores_must_stay_within_the_unit_interval() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        make_wallet(risk_score=Decimal("2"))


def test_wallet_cluster_requires_at_least_two_wallets() -> None:
    with pytest.raises(ValueError, match="at least two wallets"):
        WalletCluster(
            id="cluster-1",
            entity_id=None,
            wallet_ids=("ethereum:0xabc",),
            confidence=Decimal("0.5"),
            evidence="single wallet, not a cluster",
            created_at=NOW,
        )


def test_wallet_cluster_rejects_duplicate_wallet_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        WalletCluster(
            id="cluster-1",
            entity_id=None,
            wallet_ids=("ethereum:0xabc", "ethereum:0xabc"),
            confidence=Decimal("0.5"),
            evidence="duplicate wallet id",
            created_at=NOW,
        )


def test_wallet_cluster_accepts_two_distinct_wallets() -> None:
    cluster = WalletCluster(
        id="cluster-1",
        entity_id="entity-1",
        wallet_ids=("ethereum:0xabc", "ethereum:0xdef"),
        confidence=Decimal("0.75"),
        evidence="both wallets bought the same token within 30 minutes",
        created_at=NOW,
    )
    assert len(cluster.wallet_ids) == 2
