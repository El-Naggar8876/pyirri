"""
Modules for PyIrri — sprinkler system design application.

Each submodule is imported defensively so that an environment-specific failure
in one component (e.g. missing optional GIS dependency) does not prevent the
rest of the application from loading.
"""

home = None
crop_water_requirements = None
sprinkler_selection = None
operational_design = None
hydraulic_design = None
pipe_network_design = None
pipe_network_layout = None
pump_selection = None
system_layout = None
cost_estimation = None
reports = None
documentation = None
field_layout_manager = None
gee_project_manager = None

_import_errors = []

for _name in (
    "home",
    "crop_water_requirements",
    "sprinkler_selection",
    "operational_design",
    "hydraulic_design",
    "pipe_network_design",
    "pipe_network_layout",
    "pump_selection",
    "system_layout",
    "cost_estimation",
    "reports",
    "documentation",
    "field_layout_manager",
    "gee_project_manager",
):
    try:
        globals()[_name] = __import__(f"modules.{_name}", fromlist=[_name])
    except Exception as exc:  # noqa: BLE001
        _import_errors.append(f"{_name}: {type(exc).__name__}: {exc}")


def get_import_errors():
    """Return list of import errors for debugging in UI."""
    return list(_import_errors)


__all__ = [
    "home",
    "crop_water_requirements",
    "sprinkler_selection",
    "operational_design",
    "hydraulic_design",
    "pipe_network_design",
    "pipe_network_layout",
    "pump_selection",
    "system_layout",
    "cost_estimation",
    "reports",
    "documentation",
    "field_layout_manager",
    "gee_project_manager",
    "get_import_errors",
]
