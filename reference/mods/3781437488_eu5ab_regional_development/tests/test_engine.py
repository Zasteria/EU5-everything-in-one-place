from pathlib import Path
from dataclasses import replace
import unittest

from src.eu5autobuild.engine import (
    AutomationContext,
    BuildingCandidate,
    CountryState,
    GoodsMarketState,
    LocationState,
    MarketState,
    NativeInputMethod,
    PauseReason,
    PromotionSource,
    WorkforceRequirement,
    WorkforceState,
    apply_province_template,
    assess_native_input_fit,
    assess_workforce,
    calculate_monthly_quota,
    choose_building,
    execute_ranked_candidates,
    first_blocking_reason,
    rank_building_candidates,
    score_candidate_components,
    select_locations_for_deep_scoring,
    workforce_risk_penalty,
)
from src.eu5autobuild.policy import BuildingCatalog, Policy, RgoPolicy
from src.eu5autobuild.rules import load_automation_rules


ROOT = Path(__file__).resolve().parents[1]
_RULES = load_automation_rules(ROOT / "policies" / "automation_rules.json")
_TEST_BUILDING_IDS = {
    "arms_factory",
    "farm",
    "fishery",
    "lumber_camp",
    "palace",
    "textile_mill",
    "third",
    "workshop",
}
RULES = replace(
    _RULES,
    building_priorities=replace(
        _RULES.building_priorities,
        overrides={
            **_RULES.building_priorities.overrides,
            **{building_id: 1.0 for building_id in _TEST_BUILDING_IDS},
        },
    ),
)


def policy(**overrides):
    """Build a strategy plus explicit shared-runtime values for planner tests."""
    overrides = dict(overrides)
    budget = overrides.pop("budget", {"annual_gold": 100, "min_cash_reserve": 1000})
    price_band = overrides.pop("price_band", {"min_ratio": 0.8, "max_ratio": 1.3})
    allow_special_buildings = overrides.pop("allow_special_buildings", False)
    pause_on_labor_shortage = overrides.pop("pause_on_labor_shortage", True)
    pause_on_input_shortage = overrides.pop("pause_on_input_shortage", True)
    input_shortage_strategy = overrides.pop(
        "input_shortage_strategy", {"auto_build_sources": True}
    )
    job_fill_deadline_months = overrides.pop("job_fill_deadline_months", 3)
    native_input_priority = overrides.pop("native_input_priority", 5)
    rgo = RgoPolicy.from_mapping(overrides.pop("rgo", None))
    base = {
        "id": "test",
        "name_key": "test",
        "description_key": "test_desc",
        "role": "food",
        "priority_goods": ["wheat", "fish"],
        "allowed_buildings": ["farm", "fishery"],
        "banned_buildings": ["arms_factory"],
        "prediction": {"display_name": "Test", "summary": "Test"},
    }
    base.update(overrides)
    strategy = Policy.from_mapping(base)
    return replace(
        strategy,
        annual_budget=budget["annual_gold"],
        min_cash_reserve=budget["min_cash_reserve"],
        min_price_ratio=price_band["min_ratio"],
        max_price_ratio=price_band["max_ratio"],
        allow_special_buildings=allow_special_buildings,
        pause_on_labor_shortage=pause_on_labor_shortage,
        pause_on_input_shortage=pause_on_input_shortage,
        auto_build_input_sources=input_shortage_strategy["auto_build_sources"],
        job_fill_deadline_months=job_fill_deadline_months,
        native_input_priority=native_input_priority,
        rgo=rgo,
    )


class EngineSelectionTests(unittest.TestCase):
    def test_selects_highest_scoring_allowed_candidate(self):
        decision = choose_building(
            policy(),
            [
                BuildingCandidate("fishery", ("fish",), 50, 1.0),
                BuildingCandidate("farm", ("wheat",), 50, 1.0),
            ],
            budget_remaining=100,
            cash_available=1200,
         context=AutomationContext(location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)))
        self.assertTrue(decision.should_build)
        self.assertEqual(decision.building_id, "farm")

    def test_banned_beats_high_score(self):
        decision = choose_building(
            policy(allowed_buildings=["farm", "arms_factory"]),
            [BuildingCandidate("arms_factory", ("wheat",), 10, 1.0, base_score=1000)],
            budget_remaining=100,
            cash_available=1200,
         context=AutomationContext(location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)))
        self.assertEqual(decision.reason, PauseReason.BANNED_BUILDING)

    def test_allowlist_filters_candidates(self):
        decision = choose_building(
            policy(),
            [BuildingCandidate("textile_mill", ("wheat",), 10, 1.0)],
            budget_remaining=100,
            cash_available=1200,
         context=AutomationContext(location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)))
        self.assertEqual(decision.reason, PauseReason.NOT_ALLOWED)

    def test_positive_budget_allows_final_project_and_exhaustion_blocks(self):
        for remaining in (100, 0, -50):
            with self.subTest(remaining=remaining):
                decision = choose_building(
                    policy(), [BuildingCandidate("farm", ("wheat",), 150, 1.0)],
                    budget_remaining=remaining, cash_available=1200,
                    context=AutomationContext(location=LocationState(
                        fully_staffed_building_levels=0, supported_building_levels=100)))
                self.assertEqual(decision.reason, PauseReason.NONE if remaining > 0 else PauseReason.BUDGET_EXHAUSTED)

    def test_low_output_price_blocks_oversupplied_building(self):
        decision = choose_building(
            policy(),
            [BuildingCandidate("farm", ("wheat",), 50, 0.7)],
            budget_remaining=100,
            cash_available=1200,
         context=AutomationContext(location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)))
        self.assertEqual(decision.reason, PauseReason.PRICE_OUT_OF_RANGE)

    def test_labor_shortage_blocks_when_enabled(self):
        decision = choose_building(
            policy(),
            [BuildingCandidate("farm", ("wheat",), 50, 1.0, labor_available=False)],
            budget_remaining=100,
            cash_available=1200,
         context=AutomationContext(location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)))
        self.assertEqual(decision.reason, PauseReason.LABOR_SHORTAGE)

    def test_input_shortage_blocks_when_enabled(self):
        decision = choose_building(
            policy(),
            [BuildingCandidate("farm", ("wheat",), 50, 1.0, inputs_available=False)],
            budget_remaining=100,
            cash_available=1200,
         context=AutomationContext(location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)))
        self.assertEqual(decision.reason, PauseReason.INPUT_SHORTAGE)

    def test_local_pop_shortage_blocks_building(self):
        decision = choose_building(
            policy(),
            [BuildingCandidate("farm", ("wheat",), 50, 1.0, local_pop_available=False)],
            budget_remaining=100,
            cash_available=1200,
         context=AutomationContext(location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)))
        self.assertEqual(decision.reason, PauseReason.POPULATION_SHORTAGE)

    def test_cash_reserve_blocks_building(self):
        decision = choose_building(
            policy(),
            [BuildingCandidate("farm", ("wheat",), 50, 1.0)],
            budget_remaining=100,
            cash_available=1025,
         context=AutomationContext(location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)))
        self.assertEqual(decision.reason, PauseReason.CASH_RESERVE)

    def test_special_building_blocked_by_default(self):
        decision = choose_building(
            policy(allowed_buildings=["farm", "palace"]),
            [BuildingCandidate("palace", ("wheat",), 50, 1.0, is_special=True)],
            budget_remaining=100,
            cash_available=1200,
         context=AutomationContext(location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)))
        self.assertEqual(decision.reason, PauseReason.SPECIAL_BUILDING_DISABLED)

    def test_input_shortage_can_build_source_building(self):
        catalog = BuildingCatalog.from_mapping(
            {
                "buildings": [
                    {"id": "farm", "output_goods": ["wheat"], "workforce_pop_types": ["peasants"]},
                    {"id": "lumber_camp", "output_goods": ["lumber"], "workforce_pop_types": ["peasants"]},
                ]
            }
        )
        decision = choose_building(
            policy(allowed_buildings=["farm"]),
            [
                BuildingCandidate(
                    "farm",
                    ("wheat",),
                    50,
                    1.0,
                    inputs_available=False,
                    input_shortages=("lumber",),
                ),
                BuildingCandidate("lumber_camp", ("lumber",), 40, 1.0),
            ],
            budget_remaining=100,
            cash_available=1200,
            catalog=catalog,
         context=AutomationContext(location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)))
        self.assertTrue(decision.should_build)
        self.assertEqual(decision.building_id, "lumber_camp")

    def test_decoupled_location_keeps_existing_policy(self):
        updated = apply_province_template(
            {"a": "old", "b": "old"},
            ["a", "b"],
            "granary",
            {"b"},
        )
        self.assertEqual(updated, {"a": "granary", "b": "old"})


class NeedsFirstEngineTests(unittest.TestCase):
    def test_economic_term_uses_native_profit_and_cost_with_existing_scale(self):
        candidate = BuildingCandidate('farm', ('wheat',), 50, 1.0, potential_profit=10,
            construction_cost=100, expected_output_value=500, expected_input_cost=1)
        context = AutomationContext(market=MarketState(goods={'wheat': GoodsMarketState(supply=100, demand=100)}))
        components = score_candidate_components(policy(), candidate, context, RULES)
        self.assertEqual(components['economic_efficiency'], round(0.1 * RULES.thresholds.economic_score_scale))
        # The existing recipe-based profit signal remains a separate component.
        self.assertEqual(components['profit_signal'], RULES.scores.high_profit)

    def test_food_emergency_beats_highly_profitable_luxury(self):
        context = AutomationContext(
            market=MarketState(
                food_stockpile_ratio=0.2,
                monthly_food_balance=-20,
                projected_food_exhaustion=True,
                goods={"wheat": GoodsMarketState(supply=30, demand=100, price_ratio=1.8)},
            ),
            location=LocationState(raw_material="wheat", raw_material_output=10,
                                   rgo_monthly_revenue=100, rgo_output_factor=1, fully_staffed_building_levels=0, supported_building_levels=100),
        )
        decision = choose_building(
            policy(allowed_buildings=["windmill", "jewelry_guild"]),
            [
                BuildingCandidate("jewelry_guild", ("jewelry",), 50, 1.8, potential_profit=100),
                BuildingCandidate("windmill", (), 50, 1.8, potential_profit=-5),
            ],
            100,
            1200,
            context=context,
            rules=RULES,
        )
        self.assertEqual(decision.building_id, "windmill")
        self.assertGreater(decision.score, 10000)

    def test_construction_bottleneck_beats_generic_profit(self):
        context = AutomationContext(
            market=MarketState(
                goods={
                    "tools": GoodsMarketState(supply=40, demand=100, price_ratio=1.7),
                    "jewelry": GoodsMarketState(supply=100, demand=100, price_ratio=1.0),
                }
            )
        , location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100))
        decision = choose_building(
            policy(
                role="industry",
                priority_goods=["jewelry"],
                allowed_buildings=["tools_workshop", "jewelry_guild"],
            ),
            [
                BuildingCandidate("jewelry_guild", ("jewelry",), 50, 1.0, potential_profit=100),
                BuildingCandidate("tools_workshop", ("tools",), 50, 1.7, potential_profit=-1),
            ],
            100,
            1200,
            context=context,
            rules=RULES,
        )
        self.assertEqual(decision.building_id, "tools_workshop")

    def test_video_quality_priority_breaks_equal_need_candidates(self):
        decision = choose_building(
            policy(
                role="test",
                priority_goods=[],
                allowed_buildings=["granary", "porcelain_manufactory"],
            ),
            [
                BuildingCandidate("porcelain_manufactory", (), 50, 1.0),
                BuildingCandidate("granary", (), 50, 1.0),
            ],
            100,
            1200,
            context=AutomationContext(location=LocationState(
                province_food_capacity=1000, province_food_ratio=.95,
                province_monthly_food_production=10, province_food_balance=10,
                province_monthly_food_consumption=300,
             fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertEqual(decision.building_id, "granary")
        self.assertEqual(decision.score, 590)

    def test_zero_quality_priority_disables_building(self):
        decision = choose_building(
            policy(
                role="test",
                priority_goods=[],
                allowed_buildings=[],
            ),
            [BuildingCandidate("city_walls", (), 50, 1.0)],
            100,
            1200,
            context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertEqual(decision.reason, PauseReason.PRIORITY_DISABLED)

    def test_explicit_preset_allowlist_overrides_zero_quality_priority(self):
        decision = choose_building(
            policy(
                role="test",
                priority_goods=[],
                allowed_buildings=["city_walls"],
            ),
            [BuildingCandidate("city_walls", (), 50, 1.0)],
            100,
            1200,
            context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertTrue(decision.should_build)
        self.assertEqual(
            score_candidate_components(
                policy(
                    role="test",
                    priority_goods=[],
                    allowed_buildings=["city_walls"],
                ),
                BuildingCandidate("city_walls", (), 50, 1.0),
                AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
                RULES,
            )["building_priority"],
            RULES.building_priorities.score_per_point,
        )

    def test_locked_and_superseded_buildings_are_filtered_before_scoring(self):
        locked = choose_building(
            policy(),
            [BuildingCandidate("farm", ("wheat",), 50, 1.0, unlocked=False)],
            100,
            1200,
            context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertEqual(locked.reason, PauseReason.NOT_UNLOCKED)

        superseded = choose_building(
            policy(),
            [
                BuildingCandidate(
                    "farm",
                    ("wheat",),
                    50,
                    1.0,
                    newer_replacement_unlocked=True,
                )
            ],
            100,
            1200,
            context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertEqual(superseded.reason, PauseReason.SUPERSEDED_BUILDING)

    def test_upgrade_opportunity_is_preferred_over_normal_construction(self):
        decision = choose_building(
            policy(),
            [
                BuildingCandidate("farm", ("wheat",), 50, 1.0, base_score=1000),
                BuildingCandidate(
                    "fishery",
                    ("fish",),
                    50,
                    1.0,
                    upgradeable_predecessor_levels=1,
                ),
            ],
            100,
            1200,
            context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertEqual(decision.building_id, "fishery")

    def test_high_output_price_is_encouraged_not_blocked(self):
        context = AutomationContext(
            market=MarketState(goods={"wheat": GoodsMarketState(supply=80, demand=100, price_ratio=1.6)})
        , location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100))
        decision = choose_building(
            policy(),
            [BuildingCandidate("farm", ("wheat",), 50, 1.6, potential_profit=1)],
            100,
            1200,
            context=context,
            rules=RULES,
        )
        self.assertTrue(decision.should_build)
        self.assertEqual(
            score_candidate_components(
                policy(),
                BuildingCandidate("farm", ("wheat",), 50, 1.6, potential_profit=1),
                context,
                RULES,
            )["price_above_max"],
            RULES.rgo_scores.high_price,
        )

    def test_food_emergency_overrides_low_price_floor(self):
        context = AutomationContext(
            market=MarketState(food_stockpile_ratio=0.2, monthly_food_balance=-1)
        , location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100))
        decision = choose_building(
            policy(),
            [BuildingCandidate("farm", ("wheat",), 50, 0.7, potential_profit=-5)],
            100,
            1200,
            context=context,
            rules=RULES,
        )
        self.assertTrue(decision.should_build)

    def test_real_unemployed_worker_floor_blocks_empty_building(self):
        decision = choose_building(
            policy(),
            [BuildingCandidate("farm", ("wheat",), 50, 1.0, available_workers=50)],
            100,
            1200,
            context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertEqual(decision.reason, PauseReason.LABOR_SHORTAGE)

    def test_existing_construction_blocks_stacking(self):
        decision = choose_building(
            policy(),
            [BuildingCandidate("farm", ("wheat",), 50, 1.0)],
            100,
            1200,
            context=AutomationContext(location=LocationState(civil_constructions=1, fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertEqual(decision.reason, PauseReason.CONSTRUCTION_QUEUE)

    def test_location_cooldown_blocks_repeated_builds(self):
        decision = choose_building(
            policy(),
            [BuildingCandidate("farm", ("wheat",), 50, 1.0)],
            100,
            1200,
            context=AutomationContext(location=LocationState(cooldown_months=1, fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertEqual(decision.reason, PauseReason.COOLDOWN)

    def test_expansion_scale_prefers_existing_building(self):
        decision = choose_building(
            policy(allowed_buildings=["farm", "fishery"], priority_goods=[]),
            [
                BuildingCandidate("farm", ("wheat",), 50, 1.0, existing_levels=5),
                BuildingCandidate("fishery", ("fish",), 50, 1.0, existing_levels=0),
            ],
            100,
            1200,
            context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertEqual(decision.building_id, "farm")

    def test_wartime_military_shortage_gets_strategic_bonus(self):
        context = AutomationContext(
            market=MarketState(
                goods={
                    "weaponry": GoodsMarketState(supply=80, demand=100, price_ratio=1.3),
                    "jewelry": GoodsMarketState(supply=80, demand=100, price_ratio=1.3),
                }
            ),
            country=CountryState(at_war=True),
         location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100))
        decision = choose_building(
            policy(
                role="military",
                priority_goods=[],
                allowed_buildings=["weapon_factory", "jewelry_guild"],
            ),
            [
                BuildingCandidate("jewelry_guild", ("jewelry",), 50, 1.3, potential_profit=20),
                BuildingCandidate("weapon_factory", ("weaponry",), 50, 1.3, potential_profit=0),
            ],
            100,
            1200,
            context=context,
            rules=RULES,
        )
        self.assertEqual(decision.building_id, "weapon_factory")


class WorkforceForecastTests(unittest.TestCase):
    @staticmethod
    def requirement(**overrides):
        values = {
            "pop_type": "burghers",
            "new_jobs": 300,
        }
        values.update(overrides)
        return WorkforceRequirement(**values)

    @staticmethod
    def source(**overrides):
        values = {
            "id": "peasants",
            "pop_type": "peasants",
            "population": 1000,
            "monthly_amount": 100,
            "promote_to": ("burghers",),
        }
        values.update(overrides)
        return PromotionSource(**values)

    def test_exact_deadline_is_allowed_and_one_month_over_is_rejected(self):
        exact = assess_workforce(
            (self.requirement(),),
            (self.source(),),
            3,
        )
        late = assess_workforce(
            (self.requirement(),),
            (self.source(),),
            2,
        )
        self.assertEqual(exact.state, WorkforceState.WITHIN_DEADLINE)
        self.assertEqual(exact.months_to_fill, 3)
        self.assertTrue(exact.within_deadline)
        self.assertEqual(late.state, WorkforceState.BEYOND_DEADLINE)
        self.assertEqual(late.months_to_fill, 3)
        self.assertEqual(
            first_blocking_reason(
                policy(),
                BuildingCandidate(
                    "farm",
                    ("wheat",),
                    50,
                    1.0,
                    workforce_assessment=late,
                ),
                100,
                1200,
                context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
                rules=RULES,
            ),
            PauseReason.LABOR_SHORTAGE,
        )

    def test_zero_deadline_is_strict_but_current_workers_still_pass(self):
        gap = assess_workforce(
            (self.requirement(),),
            (self.source(),),
            0,
        )
        current = assess_workforce(
            (self.requirement(immediately_employable=300),),
            (),
            0,
        )
        self.assertEqual(gap.state, WorkforceState.BEYOND_DEADLINE)
        self.assertEqual(current.state, WorkforceState.CURRENT_SUFFICIENT)

    def test_vacancies_new_jobs_and_queued_reservations_all_consume_workers(self):
        assessment = assess_workforce(
            (
                self.requirement(
                    current_unfilled_jobs=50,
                    new_jobs=100,
                    queued_reserved_jobs=75,
                    immediately_employable=25,
                ),
            ),
            (self.source(monthly_amount=50),),
            4,
        )
        self.assertEqual(assessment.total_demand, 225)
        self.assertEqual(assessment.total_gap, 200)
        self.assertEqual(assessment.months_to_fill, 4)

    def test_shared_source_population_is_not_double_counted_across_pop_types(self):
        assessment = assess_workforce(
            (
                WorkforceRequirement(pop_type="burghers", new_jobs=100),
                WorkforceRequirement(pop_type="soldiers", new_jobs=100),
            ),
            (
                self.source(
                    population=200,
                    monthly_amount=100,
                    promote_to=("burghers", "soldiers"),
                ),
            ),
            2,
        )
        self.assertEqual(assessment.months_to_fill, 2)
        self.assertEqual(assessment.state, WorkforceState.WITHIN_DEADLINE)

    def test_repeated_requirements_for_one_pop_type_are_added_together(self):
        assessment = assess_workforce(
            (
                self.requirement(new_jobs=100),
                self.requirement(new_jobs=100),
            ),
            (self.source(population=500, monthly_amount=100),),
            1,
        )
        self.assertEqual(assessment.total_gap, 200)
        self.assertEqual(assessment.months_to_fill, 2)
        self.assertEqual(assessment.state, WorkforceState.BEYOND_DEADLINE)

    def test_distinct_direct_sources_combine_but_indirect_paths_do_not(self):
        combined = assess_workforce(
            (self.requirement(new_jobs=150),),
            (
                self.source(id="peasants", monthly_amount=50),
                self.source(
                    id="laborers",
                    pop_type="laborers",
                    monthly_amount=100,
                ),
            ),
            1,
        )
        indirect = assess_workforce(
            (self.requirement(new_jobs=100),),
            (
                self.source(
                    promote_to=("laborers",),
                    monthly_amount=100,
                ),
            ),
            12,
        )
        self.assertEqual(combined.months_to_fill, 1)
        self.assertEqual(indirect.state, WorkforceState.NO_PROMOTION_PATH)

    def test_zero_rate_target_cap_and_unreliable_prediction_have_distinct_states(self):
        zero = assess_workforce(
            (self.requirement(new_jobs=100),),
            (self.source(monthly_amount=0),),
            3,
        )
        capped = assess_workforce(
            (self.requirement(new_jobs=100, promotion_capacity=99),),
            (self.source(),),
            3,
        )
        unavailable = assess_workforce(
            (self.requirement(new_jobs=100),),
            (self.source(),),
            3,
            prediction_reliable=False,
        )
        self.assertEqual(zero.state, WorkforceState.ZERO_PROMOTION_RATE)
        self.assertEqual(capped.state, WorkforceState.TARGET_CAP)
        self.assertEqual(
            unavailable.state,
            WorkforceState.PREDICTION_UNAVAILABLE,
        )
        self.assertFalse(unavailable.reliable)

    def test_negative_population_rate_and_capacity_inputs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "negative populations"):
            assess_workforce(
                (self.requirement(new_jobs=-1),),
                (),
                3,
            )
        with self.assertRaisesRegex(ValueError, "negative populations or rates"):
            assess_workforce(
                (self.requirement(new_jobs=1),),
                (self.source(monthly_amount=-1),),
                3,
            )
        with self.assertRaisesRegex(ValueError, "capacity cannot be negative"):
            assess_workforce(
                (self.requirement(new_jobs=1, promotion_capacity=-1),),
                (self.source(),),
                3,
            )

    def test_nonfinite_and_invalid_horizon_inputs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "deadline must be an integer"):
            assess_workforce((self.requirement(),), (self.source(),), True)
        accepted = assess_workforce(
            (self.requirement(new_jobs=2400),),
            (self.source(population=2400, monthly_amount=10),),
            240,
        )
        self.assertEqual(accepted.months_to_fill, 240)
        with self.assertRaisesRegex(ValueError, "between 0 and 240"):
            assess_workforce((self.requirement(),), (self.source(),), 241)
        with self.assertRaisesRegex(ValueError, "horizon must be an integer"):
            assess_workforce(
                (self.requirement(),),
                (self.source(),),
                3,
                diagnostic_horizon_months=True,
            )
        with self.assertRaisesRegex(ValueError, "horizon cannot be below"):
            assess_workforce(
                (self.requirement(),),
                (self.source(),),
                3,
                diagnostic_horizon_months=2,
            )
        with self.assertRaisesRegex(ValueError, "finite populations"):
            assess_workforce(
                (self.requirement(new_jobs=float("nan")),),
                (self.source(),),
                3,
            )
        with self.assertRaisesRegex(ValueError, "capacity must be finite"):
            assess_workforce(
                (self.requirement(promotion_capacity=float("inf")),),
                (self.source(),),
                3,
            )
        with self.assertRaisesRegex(ValueError, "finite populations and rates"):
            assess_workforce(
                (self.requirement(),),
                (self.source(monthly_amount=float("inf")),),
                3,
            )

    def test_workforce_penalty_rejects_invalid_limits(self):
        current = assess_workforce(
            (self.requirement(immediately_employable=300),),
            (),
            3,
        )
        self.assertEqual(workforce_risk_penalty(current, max_penalty=100), 0)
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            workforce_risk_penalty(current, max_penalty=-1)
        with self.assertRaisesRegex(ValueError, r"in \(0, 1\]"):
            workforce_risk_penalty(current, max_penalty=100, strategic_relief=0)

    def test_pause_off_allows_unsafe_gap_but_never_makes_it_risk_free(self):
        late = assess_workforce(
            (self.requirement(),),
            (self.source(),),
            2,
        )
        candidate = BuildingCandidate(
            "farm",
            ("wheat",),
            50,
            1.0,
            workforce_assessment=late,
        )
        relaxed = policy(pause_on_labor_shortage=False)
        self.assertEqual(
            first_blocking_reason(
                relaxed,
                candidate,
                100,
                1200,
                context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
                rules=RULES,
            ),
            PauseReason.NONE,
        )
        components = score_candidate_components(
            relaxed,
            candidate,
            AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            RULES,
        )
        before = sum(v for k, v in components.items() if k != "labor_risk")
        self.assertEqual(sum(components.values()), round(before * 0.4))

    def test_strict_mode_keeps_forecast_gate_without_soft_shortage_penalty(self):
        within = assess_workforce(
            (self.requirement(),),
            (self.source(),),
            3,
        )
        candidate = BuildingCandidate(
            "farm",
            ("wheat",),
            50,
            1.0,
            workforce_assessment=within,
        )
        emergency = AutomationContext(
            market=MarketState(
                food_stockpile_ratio=0.2,
                monthly_food_balance=-1,
            )
        , location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100))
        relieved = score_candidate_components(policy(), candidate, emergency, RULES)
        full = workforce_risk_penalty(
            within,
            max_penalty=RULES.workforce_model.max_penalty,
        )
        self.assertNotIn("labor_risk", relieved)

        late = assess_workforce(
            (self.requirement(),),
            (self.source(),),
            2,
        )
        blocked = BuildingCandidate(
            "farm",
            ("wheat",),
            50,
            1.0,
            workforce_assessment=late,
        )
        self.assertEqual(
            first_blocking_reason(
                policy(),
                blocked,
                100,
                1200,
                context=emergency,
                rules=RULES,
            ),
            PauseReason.LABOR_SHORTAGE,
        )


class NativeInputFitTests(unittest.TestCase):
    def fit(self, **overrides):
        values = {
            "input_quantities": {"iron": 3.0, "coal": 1.0, "tools": 1.0},
            "raw_input_goods": frozenset({"iron", "coal"}),
            "province_raw_goods": frozenset({"iron"}),
            "priority": 5,
            "max_bonus": RULES.native_input_fit.max_bonus,
            "shortage_discount": RULES.native_input_fit.shortage_discount,
            "high_utilization_discount": (
                RULES.native_input_fit.high_utilization_discount
            ),
            "low_output_floor": RULES.native_input_fit.low_output_floor,
            "access_control_floor": RULES.native_input_fit.access_control_floor,
        }
        values.update(overrides)
        return assess_native_input_fit(**values)

    def test_weighted_main_input_beats_minor_input_and_all_beats_partial(self):
        main = self.fit(province_raw_goods=frozenset({"iron"}))
        minor = self.fit(province_raw_goods=frozenset({"coal"}))
        all_inputs = self.fit(province_raw_goods=frozenset({"iron", "coal"}))
        none = self.fit(province_raw_goods=frozenset())
        self.assertGreater(main.score, minor.score)
        self.assertGreater(all_inputs.score, main.score)
        self.assertEqual(none.score, 0)
        self.assertEqual(main.coverage, 0.75)

    def test_priority_zero_disables_and_priority_ten_is_stronger_than_five(self):
        off = self.fit(priority=0)
        normal = self.fit(priority=5)
        high = self.fit(priority=10)
        self.assertEqual(off.score, 0)
        self.assertEqual(off.method, NativeInputMethod.NONE)
        self.assertGreater(high.score, normal.score)

    def test_shortage_low_output_high_utilization_access_and_control_reduce_score(self):
        baseline = self.fit()
        reduced = self.fit(
            shortage_goods=frozenset({"iron"}),
            output_ratio=0.2,
            raw_input_utilization=1.0,
            market_access=0.2,
            control=0.2,
        )
        self.assertGreater(baseline.score, reduced.score)
        self.assertLess(reduced.shortage_factor, 1)
        self.assertEqual(
            reduced.output_factor,
            RULES.native_input_fit.low_output_floor,
        )

    def test_exact_vanilla_value_replaces_proxy_instead_of_double_counting(self):
        exact = self.fit(
            province_raw_goods=frozenset(),
            exact_vanilla_coverage=0.8,
        )
        self.assertEqual(exact.method, NativeInputMethod.EXACT)
        self.assertEqual(exact.coverage, 0.8)
        self.assertLessEqual(exact.score, RULES.native_input_fit.max_bonus)

    def test_rgo_never_receives_self_input_fit(self):
        rgo = self.fit(
            is_rgo=True,
            province_raw_goods=frozenset({"iron", "coal"}),
            priority=10,
        )
        self.assertEqual(rgo.method, NativeInputMethod.NONE)
        self.assertEqual(rgo.score, 0)

    def test_invalid_native_input_values_are_rejected(self):
        cases = (
            ({"priority": True}, "priority must be an integer"),
            ({"priority": 11}, "between 0 and 10"),
            ({"max_bonus": True}, "maximum bonus must be an integer"),
            ({"max_bonus": -1}, "cannot be negative"),
            ({"input_quantities": {"iron": -1}}, "cannot be negative"),
            (
                {"input_quantities": {"iron": float("nan")}},
                "finite numbers",
            ),
            ({"output_ratio": float("inf")}, "finite number"),
            ({"shortage_discount": -0.1}, "between 0 and 1"),
            ({"exact_vanilla_coverage": float("nan")}, "finite number"),
        )
        for overrides, message in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, message):
                    self.fit(**overrides)


class BoundedAutomationTests(unittest.TestCase):
    def test_concurrent_slider_maps_zero_to_one_and_599_to_600(self):
        common = dict(
            covered_locations=1000,
            budget_remaining=100,
            cash_available=1200,
            min_cash_reserve=1000,
            rules=RULES,
        )
        self.assertEqual(
            calculate_monthly_quota(
                **common, user_hard_cap=0, active_mod_constructions=0
            ),
            1,
        )
        self.assertEqual(
            calculate_monthly_quota(
                **common, user_hard_cap=599, active_mod_constructions=0
            ),
            600,
        )
        self.assertEqual(
            calculate_monthly_quota(
                **common, user_hard_cap=599, active_mod_constructions=1
            ),
            599,
        )
        self.assertEqual(
            calculate_monthly_quota(
                **common, user_hard_cap=599, active_mod_constructions=600
            ),
            0,
        )
        self.assertEqual(
            calculate_monthly_quota(
                **(common | {"covered_locations": 50}),
                user_hard_cap=599,
                active_mod_constructions=0,
            ),
            600,
        )

    def test_concurrent_quota_obeys_mod_budget_and_cash_limits(self):
        common = dict(
            covered_locations=1000,
            user_hard_cap=3,
            budget_remaining=100,
            cash_available=1200,
            min_cash_reserve=1000,
            active_mod_constructions=0,
            rules=RULES,
        )
        self.assertEqual(calculate_monthly_quota(**common), 4)
        self.assertEqual(calculate_monthly_quota(**(common | {"budget_remaining": 0})), 0)
        self.assertEqual(calculate_monthly_quota(**(common | {"cash_available": 1000})), 0)

    def test_full_scoring_is_bounded_for_large_countries(self):
        for size in (50, 200, 500, 1000):
            locations = [
                LocationState(
                    id=f"location_{index:04d}",
                    population=index * 100,
                    development=index % 50,
                 fully_staffed_building_levels=0, supported_building_levels=100)
                for index in range(size)
            ]
            selected, _ = select_locations_for_deep_scoring(locations, RULES)
            self.assertEqual(len(selected), min(size, 600))

    def test_scoring_pool_scales_with_remaining_concurrent_slots(self):
        locations = [LocationState(id=f"location_{index:04d}", fully_staffed_building_levels=0, supported_building_levels=100) for index in range(1000)]
        for remaining_slots, expected in ((0, 0), (1, 8), (10, 80), (100, 600)):
            with self.subTest(remaining_slots=remaining_slots):
                selected, _ = select_locations_for_deep_scoring(
                    locations,
                    RULES,
                    remaining_slots=remaining_slots,
                )
                self.assertEqual(len(selected), expected)

    def test_low_cost_location_filter_reports_each_pause_reason(self):
        locations = [
            LocationState(id="not_covered", covered=False, fully_staffed_building_levels=0, supported_building_levels=100),
            LocationState(
                id="busy",
                civil_constructions=1,
             fully_staffed_building_levels=0, supported_building_levels=100),
            LocationState(id="cooldown", cooldown_months=1, fully_staffed_building_levels=0, supported_building_levels=100),
            LocationState(id="failed_recently", failure_cooldown_months=1, fully_staffed_building_levels=0, supported_building_levels=100),
            LocationState(id="eligible", unemployed_workers=1000, fully_staffed_building_levels=0, supported_building_levels=100),
        ]
        selected, failures = select_locations_for_deep_scoring(locations, RULES)
        self.assertEqual([item.location_id for item in selected], ["eligible"])
        self.assertEqual(
            failures,
            {
                PauseReason.NOT_ALLOWED: 1,
                PauseReason.CONSTRUCTION_QUEUE: 1,
                PauseReason.COOLDOWN: 1,
                PauseReason.FAILURE_COOLDOWN: 1,
            },
        )

    def test_composite_scoring_covers_market_workforce_native_input_and_rgo_signals(self):
        native = assess_native_input_fit(
            {"iron": 1.0},
            frozenset({"iron"}),
            frozenset({"iron"}),
            priority=5,
            max_bonus=RULES.native_input_fit.max_bonus,
        )
        candidate = BuildingCandidate(
            "farm",
            ("wheat",),
            50,
            1.4,
            labor_available=False,
            inputs_available=False,
            input_goods=("iron",),
            is_rgo=True,
            rgo_utilization=0.9,
            rgo_expansion_space=2,
            expected_output_value=80,
            expected_input_cost=20,
            construction_cost=50,
            native_input_assessment=native,
        )
        context = AutomationContext(
            market=MarketState(
                food_stockpile_ratio=0.2,
                projected_food_exhaustion=True,
                goods={
                    "wheat": GoodsMarketState(supply=20, demand=100, price_ratio=1.4),
                    "iron": GoodsMarketState(supply=20, demand=100),
                },
            )
        , location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100))
        components = score_candidate_components(
            policy(
                pause_on_labor_shortage=False,
                rgo={
                    "allowed": True,
                    "minimum_utilization": 0.5,
                },
            ),
            candidate,
            context,
            RULES,
        )
        for component in (
            "rgo_shortage",
            "labor_risk",
            "rgo_cost",
            "rgo_food_emergency",
        ):
            self.assertIn(component, components)

        low_food = score_candidate_components(
            policy(),
            BuildingCandidate("farm", ("wheat",), 50, 1.0),
            AutomationContext(
                market=MarketState(
                    food_stockpile_ratio=RULES.thresholds.food_low_ratio,
                    goods={"wheat": GoodsMarketState(supply=100, demand=100)},
                )
            , location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            RULES,
        )
        self.assertEqual(low_food["market_need"], RULES.scores.food_low)

    def test_critical_population_good_does_not_override_low_price_floor(self):
        population_goods = set(RULES.goods_groups["population_basic"])
        population_good = next(iter(population_goods - set(RULES.food_goods)))
        context = AutomationContext(
            market=MarketState(
                goods={
                    population_good: GoodsMarketState(
                        supply=0,
                        demand=100,
                        price_ratio=0.5,
                    )
                }
            )
        , location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100))
        reason = first_blocking_reason(
            policy(priority_goods=[], allowed_buildings=["farm"]),
            BuildingCandidate("farm", (population_good,), 50, 0.5),
            100,
            1200,
            context=context,
            rules=RULES,
        )
        self.assertEqual(reason, PauseReason.PRICE_OUT_OF_RANGE)

    def test_rgo_gates_and_rank_rejection_counts_are_reported(self):
        candidate = BuildingCandidate(
            "farm",
            ("wheat",),
            50,
            1.0,
            is_rgo=True,
            rgo_utilization=0.4,
        )
        self.assertEqual(
            first_blocking_reason(
                policy(rgo={"allowed": False}),
                candidate,
                100,
                1200,
                rules=RULES,
             context=AutomationContext(location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100))),
            PauseReason.RGO_DISABLED,
        )
        rgo_policy = policy(
            rgo={
                "allowed": True,
                "minimum_utilization": 0.5,
            }
        )
        self.assertEqual(
            first_blocking_reason(rgo_policy, candidate, 100, 1200, rules=RULES, context=AutomationContext(location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100))),
            PauseReason.RGO_UTILIZATION,
        )

        ranked, rejected = rank_building_candidates(
            policy(allowed_buildings=["farm", "arms_factory"]),
            [
                BuildingCandidate("arms_factory", ("weaponry",), 50, 1.0),
                BuildingCandidate("farm", ("wheat",), 50, 1.0),
            ],
            100,
            1200,
            context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertEqual([item.candidate.id for item in ranked], ["farm"])
        self.assertEqual(rejected, {PauseReason.BANNED_BUILDING: 1})

    def test_zero_demand_has_infinite_supply_ratio(self):
        self.assertEqual(
            GoodsMarketState(supply=1, demand=0).supply_ratio,
            float("inf"),
        )

    def test_waiting_compensation_eventually_prevents_starvation(self):
        locations = [
            LocationState(id=f"favored_{index:03d}", population=100_000, development=50, fully_staffed_building_levels=0, supported_building_levels=100)
            for index in range(600)
        ]
        locations.append(LocationState(id="waiting", waiting_months=30, fully_staffed_building_levels=0, supported_building_levels=100))
        selected, _ = select_locations_for_deep_scoring(locations, RULES)
        self.assertIn("waiting", {item.location_id for item in selected})

    def test_emergency_location_leads_the_shared_pool(self):
        locations = [LocationState(id=f"normal_{index:02d}", fully_staffed_building_levels=0, supported_building_levels=100) for index in range(40)]
        locations.append(LocationState(id="food_emergency", emergency=True, fully_staffed_building_levels=0, supported_building_levels=100))
        selected, _ = select_locations_for_deep_scoring(locations, RULES)
        self.assertEqual(len(selected), 41)
        self.assertEqual(selected[0].location_id, "food_emergency")

    def test_emergency_bypass_is_still_strictly_bounded(self):
        locations = [
            LocationState(id=f"food_emergency_{index:03d}", emergency=True, fully_staffed_building_levels=0, supported_building_levels=100)
            for index in range(1000)
        ]
        selected, _ = select_locations_for_deep_scoring(locations, RULES)
        self.assertEqual(len(selected), RULES.cadence.deep_score_location_limit)

    def test_hidden_rejection_falls_through_to_second_candidate(self):
        candidates = [
            BuildingCandidate("farm", ("wheat",), 40, 1.2, base_score=100),
            BuildingCandidate("fishery", ("fish",), 35, 1.2, base_score=50),
            BuildingCandidate("third", ("fish",), 30, 1.2),
        ]

        def attempt(candidate):
            return 0 if candidate.id == "farm" else 1

        result = execute_ranked_candidates(
            policy(allowed_buildings=["farm", "fishery", "third"]),
            candidates,
            100,
            1200,
            0,
            attempt,
            context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertTrue(result.succeeded)
        self.assertEqual(result.building_id, "fishery")
        self.assertEqual(result.attempted_buildings, ("farm", "fishery"))
        self.assertEqual(result.rejected_buildings, ("farm",))
        self.assertEqual(result.budget_spent, 35)
        self.assertEqual(result.quota_used, 1)
        self.assertEqual(result.cooldown_months, RULES.cadence.location_cooldown_months)

    def test_failed_construction_has_no_side_effects(self):
        result = execute_ranked_candidates(
            policy(),
            [
                BuildingCandidate("farm", ("wheat",), 40, 1.2, base_score=100),
                BuildingCandidate("fishery", ("fish",), 35, 1.2, base_score=50),
            ],
            100,
            1200,
            0,
            lambda candidate: 0,
            context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.reason, PauseReason.VANILLA_REJECTED)
        self.assertEqual(result.budget_spent, 0)
        self.assertEqual(result.quota_used, 0)
        self.assertEqual(result.cooldown_months, 0)

    def test_custom_policy_can_select_rgo(self):
        context = AutomationContext(
            market=MarketState(
                goods={"wheat": GoodsMarketState(supply=40, demand=100, price_ratio=1.6)}
            )
        , location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100))
        result = execute_ranked_candidates(
            policy(
                allowed_buildings=["farm", "workshop"],
                rgo={
                    "allowed": True,
                    "minimum_utilization": 0.5,
                },
            ),
            [
                BuildingCandidate(
                    "farm",
                    ("wheat",),
                    40,
                    1.6,
                    is_rgo=True,
                    rgo_utilization=1.0,
                    rgo_expansion_space=5,
                ),
                BuildingCandidate("workshop", ("jewelry",), 40, 1.0),
            ],
            100,
            1200,
            0,
            lambda candidate: 1,
            context=context,
            rules=RULES,
        )
        self.assertEqual(result.building_id, "farm")
        self.assertEqual(result.rgo_quota_used, 1)

    def test_rgo_has_no_separate_monthly_quota(self):
        result = execute_ranked_candidates(
            policy(
                allowed_buildings=["farm", "tools_workshop"],
                rgo={"allowed": True},
            ),
            [
                BuildingCandidate("farm", ("wheat",), 40, 1.2, base_score=1000, is_rgo=True),
                BuildingCandidate("tools_workshop", ("tools",), 40, 1.2, base_score=500),
            ],
            100,
            1200,
            0,
            lambda candidate: 1,
            rgo_quota_used=1,
            context=AutomationContext( location=LocationState(fully_staffed_building_levels=0, supported_building_levels=100)),
            rules=RULES,
        )
        self.assertEqual(result.building_id, "farm")
        self.assertEqual(result.rgo_quota_used, 1)


if __name__ == "__main__":
    unittest.main()
