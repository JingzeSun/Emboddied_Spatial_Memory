"""Version adapter to the unchanged D-089 nominal solver; no new physics."""
from . import r4_control_proxy as solver
from . import r4_observed_map_v2 as maps
from .pair_contract import require


def predict_control(observed_map, controls, public_domain, control_parameters):
    require(observed_map.get("schema_version") == maps.VERSION, "v2 observed map required")
    # The field meaning and units are unchanged. A fresh top-level value makes
    # compatibility explicit without changing the saved public v2 map.
    compatible = dict(observed_map, schema_version=solver.MAP_VERSION)
    result = solver.predict_control(compatible,controls,public_domain,control_parameters)
    result["source_map_version"] = maps.VERSION
    result["schema_version"] = "spatial-history-r4-control-proxy-map-v2"
    return result
