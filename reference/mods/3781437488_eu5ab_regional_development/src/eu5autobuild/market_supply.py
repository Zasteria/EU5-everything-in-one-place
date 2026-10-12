"""Market supplementation routes and production-forecast renderer entrypoint."""
import math
from .rgo_pending import DEMAND_BUFFER_RATIO


BUFFER = DEMAND_BUFFER_RATIO
LOCATION = "scope:eu5ab_candidate_location"


def uncovered(demand, supply, pending, *, unknown=False):
    if unknown or any(not math.isfinite(x) or x < 0 for x in (demand, supply, pending)):
        return 0.0
    return max(0.0, max(0.0, demand - supply) + demand * BUFFER - pending)


def render(models, rules, upgrades=None):
    from .production_forecast import render as render_forecast
    return render_forecast(models, rules, upgrades)


def render_route_trigger():
    return '''eu5ab_candidate_route_allowed = {
    scope:eu5ab_candidate_location = { has_variable = eu5ab_policy_id eu5ab_location_template_not_paused = yes }
    eu5ab_current_special_building_allowed = yes
    OR = {
        AND = {
            scope:eu5ab_candidate_location.owner.var:eu5ab_q_phase <= 8
            eu5ab_current_building_allowed = yes
        }
        AND = {
            scope:eu5ab_candidate_location.owner.var:eu5ab_q_phase > 8
            OR = {
                scope:eu5ab_candidate_location.owner.var:eu5ab_global_fill_market_shortages_when_idle > 0
                scope:eu5ab_candidate_location.owner.var:eu5ab_global_auto_build_input_sources > 0
            }
            eu5ab_current_input_source_building_allowed = yes
            eu5ab_upstream_output_shortage = yes
        }
    }
}
'''
