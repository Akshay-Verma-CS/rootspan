"""Load validated replay fixtures from package resources."""

from importlib.resources import files

from rootspan.domain import ScenarioFixture


def load_scenario(name: str) -> ScenarioFixture:
    """Load one allow-listed scenario by its stable name."""
    if name != "inventory-cohort-timeout":
        msg = f"unknown scenario: {name}"
        raise ValueError(msg)
    resource = files("rootspan.fixtures").joinpath(f"{name}.json")
    return ScenarioFixture.model_validate_json(resource.read_text(encoding="utf-8"))
