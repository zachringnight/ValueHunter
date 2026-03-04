"""Tests for the release-candidate validation pack modules."""

import pytest

from nba_props.validation.walk_forward import (
    LINE_BUCKETS,
    SPREAD_BUCKETS,
    REST_BUCKETS,
    TIME_BUCKETS,
    ARCHETYPES,
    WalkForwardResults,
)
from nba_props.validation.metrics_tables import MetricsTableGenerator
from nba_props.validation.ablation import (
    AblationReport,
    AblationResults,
    FEATURE_BLOCKS,
    METRIC_NAMES,
)
from nba_props.validation.tracking_comparison import (
    TrackingComparison,
    TrackingComparisonResults,
    SIGNIFICANCE_ALPHA,
)
from nba_props.validation.execution_audit import (
    ExecutionRealismAudit,
    ExecutionAuditResults,
)
from nba_props.validation.paper_ledger import (
    PaperBetLedger,
    PaperLedgerResults,
    CRITICAL_FIELDS,
)
from nba_props.validation.stability_report import (
    StabilityReport,
    StabilityResults,
    DailyHealth,
)
from nba_props.validation.failure_cases import (
    FailureCaseReview,
    FailureCaseResults,
)
from nba_props.validation.promotion_gates import (
    PromotionGates,
    PromotionGateResults,
    GateResult,
    MINUTES_MAE_STARTERS,
    MINUTES_MAE_ROTATION,
    THREE_PA_MAE_HIGH_VOL,
    THREE_PA_MAE_STANDARD,
    MIN_PAPER_BETS,
    MIN_CONSECUTIVE_CLEAN_DAYS,
)
from nba_props.validation.runner import ValidationRunner, ValidationReport


# ── Slicing constants tests ──────────────────────────────────────────────────


class TestSlicingConstants:
    def test_line_buckets_cover_common_lines(self):
        assert LINE_BUCKETS["0.5"](0.5)
        assert LINE_BUCKETS["1.5"](1.5)
        assert LINE_BUCKETS["2.5"](2.5)
        assert LINE_BUCKETS["3.5+"](3.5)
        assert LINE_BUCKETS["3.5+"](4.5)
        assert not LINE_BUCKETS["0.5"](1.5)

    def test_spread_buckets(self):
        assert SPREAD_BUCKETS["blowout_fav"](-12)
        assert SPREAD_BUCKETS["moderate_fav"](-5)
        assert SPREAD_BUCKETS["tossup"](0)
        assert SPREAD_BUCKETS["moderate_dog"](5)
        assert SPREAD_BUCKETS["blowout_dog"](12)

    def test_rest_buckets(self):
        assert REST_BUCKETS["b2b"](0)
        assert REST_BUCKETS["1_day"](1)
        assert REST_BUCKETS["2_days"](2)
        assert REST_BUCKETS["3plus"](3)
        assert REST_BUCKETS["3plus"](5)

    def test_time_buckets_defined(self):
        assert len(TIME_BUCKETS) == 6
        assert "T-90" in TIME_BUCKETS

    def test_archetypes_defined(self):
        assert len(ARCHETYPES) == 5
        assert "movement_wing_shooter" in ARCHETYPES
        assert "bench_microwave" in ARCHETYPES


# ── WalkForwardResults tests ─────────────────────────────────────────────────


class TestWalkForwardResults:
    def test_default_init(self):
        r = WalkForwardResults()
        assert r.predictions == []
        assert r.folds == []
        assert r.production_metrics == {}
        assert r.baseline_metrics == {}
        assert r.sliced_metrics == {}

    def test_fields_populated(self):
        r = WalkForwardResults(
            predictions=[{"p_over": 0.6}],
            folds=[{"train_start": "2024-01-01"}],
            production_metrics={"clv_mean": 0.02},
            baseline_metrics={"rolling_avg": {"clv_mean": 0.01}},
        )
        assert len(r.predictions) == 1
        assert r.production_metrics["clv_mean"] == 0.02


# ── MetricsTableGenerator tests ─────────────────────────────────────────────


class TestMetricsTableGenerator:
    def test_init_with_empty_results(self):
        wf = WalkForwardResults()
        gen = MetricsTableGenerator(wf)
        assert gen._predictions == []

    def test_generate_all_returns_expected_keys(self):
        wf = WalkForwardResults()
        gen = MetricsTableGenerator(wf)
        tables = gen.generate_all()
        expected_keys = {
            "minutes", "three_pa", "three_pm",
            "betting", "vs_baselines", "calibration_curve",
        }
        assert set(tables.keys()) == expected_keys

    def test_format_as_text_empty(self):
        table = []
        text = MetricsTableGenerator.format_as_text(table, title="Test")
        assert isinstance(text, str)


# ── AblationReport tests ────────────────────────────────────────────────────


class TestAblationConstants:
    def test_feature_blocks_defined(self):
        assert len(FEATURE_BLOCKS) == 9
        assert "tracking_shot_mix" in FEATURE_BLOCKS
        assert "empirical_bayes_shrinkage" in FEATURE_BLOCKS

    def test_metric_names(self):
        assert "log_loss" in METRIC_NAMES
        assert "clv" in METRIC_NAMES
        assert "3pa_mae" in METRIC_NAMES


class TestAblationResults:
    def test_default_init(self):
        r = AblationResults()
        assert r.full_model_metrics == {}
        assert r.ablation_deltas == {}
        assert r.feature_importance_rank == []


# ── TrackingComparison tests ─────────────────────────────────────────────────


class TestTrackingComparisonResults:
    def test_default_init(self):
        r = TrackingComparisonResults()
        assert r.n_tracking == 0
        assert r.n_fallback == 0
        assert r.tracking_pct == 0.0
        assert r.significant_differences == []

    def test_significance_alpha(self):
        assert SIGNIFICANCE_ALPHA == 0.05


# ── ExecutionAuditResults tests ──────────────────────────────────────────────


class TestExecutionAuditResults:
    def test_default_init(self):
        r = ExecutionAuditResults()
        assert r.total_decisions_audited == 0
        assert r.total_leakage_violations == 0
        assert r.passed is True

    def test_violations_set(self):
        r = ExecutionAuditResults(total_leakage_violations=3, passed=False)
        assert r.total_leakage_violations == 3
        assert r.passed is False


# ── PaperLedger tests ────────────────────────────────────────────────────────


class TestPaperLedgerResults:
    def test_default_init(self):
        r = PaperLedgerResults()
        assert r.n_bets == 0
        assert r.meets_minimum is False
        assert r.all_fields_complete is True
        assert r.missing_fields_count == 0

    def test_critical_fields_defined(self):
        assert "model_version" in CRITICAL_FIELDS
        assert "tracking_available" in CRITICAL_FIELDS
        assert "feature_snapshot_id" in CRITICAL_FIELDS
        assert len(CRITICAL_FIELDS) == 5


# ── StabilityReport tests ───────────────────────────────────────────────────


class TestDailyHealth:
    def test_default_status(self):
        h = DailyHealth(
            date="2024-03-01",
            is_game_day=True,
            n_games=5,
            n_players_scored=50,
            n_decisions=100,
            n_bets=10,
            ingestion_complete=True,
            predictions_complete=True,
            no_null_fields=True,
            timing_ok=True,
        )
        assert h.status == "PASS"
        assert h.issues == []


class TestStabilityResults:
    def test_default_init(self):
        r = StabilityResults()
        assert r.n_days == 0
        assert r.meets_7day_requirement is False
        assert r.no_manual_intervention is True

    def test_populated(self):
        r = StabilityResults(
            n_days=7,
            n_pass=7,
            consecutive_clean_days=7,
            meets_7day_requirement=True,
        )
        assert r.meets_7day_requirement is True
        assert r.consecutive_clean_days == 7


# ── FailureCaseReview tests ──────────────────────────────────────────────────


class TestFailureCaseResults:
    def test_default_init(self):
        r = FailureCaseResults()
        assert r.half_lines == {}
        assert r.bench_shooters == {}
        assert r.critical_warnings == []

    def test_all_categories_exist(self):
        r = FailureCaseResults()
        for attr in ["half_lines", "bench_shooters", "creator_out",
                      "blowout_favorites", "b2b_road", "late_injury_flips"]:
            assert hasattr(r, attr)


class TestFailureCaseReview:
    def test_init_with_empty_predictions(self):
        review = FailureCaseReview({"predictions": []})
        assert review.predictions == []

    def test_run_empty_predictions(self):
        review = FailureCaseReview({"predictions": []})
        results = review.run()
        assert isinstance(results, FailureCaseResults)


# ── PromotionGates tests ────────────────────────────────────────────────────


class TestGateResult:
    def test_passed_gate(self):
        g = GateResult("test_gate", True, "OK", 0.5, 1.0)
        assert g.passed is True
        assert g.name == "test_gate"

    def test_failed_gate(self):
        g = GateResult("test_gate", False, "Not OK", 1.5, 1.0)
        assert g.passed is False


class TestPromotionGateResults:
    def test_all_passed(self):
        gates = [
            GateResult("g1", True, "ok"),
            GateResult("g2", True, "ok"),
        ]
        r = PromotionGateResults(gates=gates)
        assert r.all_passed is True
        assert len(r.summary_table) == 2
        assert r.summary_table[0]["status"] == "PASS"

    def test_not_all_passed(self):
        gates = [
            GateResult("g1", True, "ok"),
            GateResult("g2", False, "fail", 1.5, 1.0),
        ]
        r = PromotionGateResults(gates=gates)
        assert r.all_passed is False
        assert r.summary_table[1]["status"] == "FAIL"


class TestPromotionGatesThresholds:
    def test_threshold_values(self):
        assert MINUTES_MAE_STARTERS == 2.8
        assert MINUTES_MAE_ROTATION == 3.5
        assert THREE_PA_MAE_HIGH_VOL == 1.25
        assert THREE_PA_MAE_STANDARD == 1.00
        assert MIN_PAPER_BETS == 100
        assert MIN_CONSECUTIVE_CLEAN_DAYS == 7


class TestPromotionGatesEvaluation:
    """Test individual gate checks with mock result objects."""

    def _make_wf(self, **overrides):
        """Create a minimal WalkForwardResults-like object."""
        defaults = {
            "clv_mean": 0.02,
            "brier_score": 0.23,
            "log_loss": 0.65,
            "minutes_mae_starters": 2.5,
            "minutes_mae_rotation": 3.0,
            "three_pa_mae_high_vol": 1.1,
            "three_pa_mae_standard": 0.9,
        }
        defaults.update(overrides)

        class MockWF:
            production_metrics = defaults
            baseline_metrics = {
                "rolling_avg": {"log_loss": 0.70, "brier_score": 0.25, "clv_mean": 0.01},
                "direct_3pm": {"log_loss": 0.68, "brier_score": 0.24, "clv_mean": 0.005},
                "bookmaker": {"log_loss": 0.67, "brier_score": 0.24, "clv_mean": 0.0},
            }
        return MockWF()

    def _make_pl(self, n_bets=150, missing=0):
        class MockPL:
            pass
        pl = MockPL()
        pl.n_bets = n_bets
        pl.missing_fields_count = missing
        return pl

    def _make_sr(self, days=7, no_fail=True):
        class MockSR:
            pass
        sr = MockSR()
        sr.consecutive_clean_days = days
        sr.no_manual_intervention = no_fail
        return sr

    def _make_ea(self, violations=0):
        class MockEA:
            pass
        ea = MockEA()
        ea.total_leakage_violations = violations
        return ea

    def test_all_gates_pass(self):
        gates = PromotionGates()
        result = gates.evaluate(
            walk_forward_results=self._make_wf(),
            paper_ledger_results=self._make_pl(),
            stability_results=self._make_sr(),
            execution_audit_results=self._make_ea(),
        )
        assert isinstance(result, PromotionGateResults)
        assert result.all_passed is True
        assert len(result.gates) == 12

    def test_positive_clv_gate_fails_on_negative(self):
        gates = PromotionGates()
        result = gates.evaluate(
            walk_forward_results=self._make_wf(clv_mean=-0.01),
            paper_ledger_results=self._make_pl(),
            stability_results=self._make_sr(),
            execution_audit_results=self._make_ea(),
        )
        clv_gate = next(g for g in result.gates if g.name == "Positive OOS CLV")
        assert clv_gate.passed is False

    def test_minutes_mae_gate_fails_on_high(self):
        gates = PromotionGates()
        result = gates.evaluate(
            walk_forward_results=self._make_wf(minutes_mae_starters=3.5),
            paper_ledger_results=self._make_pl(),
            stability_results=self._make_sr(),
            execution_audit_results=self._make_ea(),
        )
        mae_gate = next(g for g in result.gates if g.name == "Minutes MAE starters")
        assert mae_gate.passed is False

    def test_min_paper_bets_gate_fails(self):
        gates = PromotionGates()
        result = gates.evaluate(
            walk_forward_results=self._make_wf(),
            paper_ledger_results=self._make_pl(n_bets=50),
            stability_results=self._make_sr(),
            execution_audit_results=self._make_ea(),
        )
        bet_gate = next(g for g in result.gates if g.name == "Minimum paper bets")
        assert bet_gate.passed is False

    def test_leakage_gate_fails(self):
        gates = PromotionGates()
        result = gates.evaluate(
            walk_forward_results=self._make_wf(),
            paper_ledger_results=self._make_pl(),
            stability_results=self._make_sr(),
            execution_audit_results=self._make_ea(violations=5),
        )
        leak_gate = next(g for g in result.gates if g.name == "No leakage failures")
        assert leak_gate.passed is False

    def test_stability_gate_fails(self):
        gates = PromotionGates()
        result = gates.evaluate(
            walk_forward_results=self._make_wf(),
            paper_ledger_results=self._make_pl(),
            stability_results=self._make_sr(days=4),
            execution_audit_results=self._make_ea(),
        )
        stab_gate = next(g for g in result.gates if g.name == "7 consecutive clean days")
        assert stab_gate.passed is False

    def test_missing_fields_gate_fails(self):
        gates = PromotionGates()
        result = gates.evaluate(
            walk_forward_results=self._make_wf(),
            paper_ledger_results=self._make_pl(missing=3),
            stability_results=self._make_sr(),
            execution_audit_results=self._make_ea(),
        )
        field_gate = next(g for g in result.gates
                          if g.name == "Zero missing critical fields")
        assert field_gate.passed is False

    def test_format_report(self):
        gates_list = [
            GateResult("Gate A", True, "ok", 0.5, 1.0),
            GateResult("Gate B", False, "fail", 1.5, 1.0),
        ]
        result = PromotionGateResults(gates=gates_list)
        text = PromotionGates.format_report(result)
        assert "BLOCKED" in text
        assert "Gate A" in text
        assert "Gate B" in text

    def test_format_report_promoted(self):
        gates_list = [GateResult("Gate A", True, "ok", 0.5, 1.0)]
        result = PromotionGateResults(gates=gates_list)
        text = PromotionGates.format_report(result)
        assert "PROMOTED" in text


# ── ValidationReport tests ──────────────────────────────────────────────────


class TestValidationReport:
    def test_default_init(self):
        r = ValidationReport()
        assert r.engine_version == "1.1.0"
        assert r.promoted is False
        assert r.gates_passed == 0


# ── ValidationRunner tests ──────────────────────────────────────────────────


class TestValidationRunner:
    def test_init(self):
        runner = ValidationRunner(
            repository=None,
            feature_builder=None,
            minutes_model=None,
            three_pa_model=None,
            make_rate_model=None,
            simulator=None,
            decision_engine=None,
        )
        assert runner.baselines == {}
        assert runner.leakage_detector is None

    def test_format_full_report_with_minimal_report(self):
        report = ValidationReport()
        text = ValidationRunner.format_full_report(report)
        assert isinstance(text, str)
        assert "v1.1" in text
