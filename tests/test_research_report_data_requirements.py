from rq_platform.research.report_data_requirements import (
    FIELD_TYPES,
    PRIORITY_ORDER,
    derived_requirements,
    load_research_report_requirements,
    raw_probe_requirements,
)


def test_requirements_list_loads_and_prioritizes():
    requirements = load_research_report_requirements()

    assert requirements
    assert requirements[0].priority == "P0"
    assert all(item.priority in PRIORITY_ORDER for item in requirements)


def test_field_type_classification_and_mixed_frequency():
    requirements = load_research_report_requirements()
    field_types = {item.field_type for item in requirements}
    frequencies = {item.required_frequency for item in requirements}

    assert field_types <= FIELD_TYPES
    assert "raw" in field_types
    assert "derived" in field_types
    assert frequencies != {"daily"}


def test_derived_fields_are_not_in_rqdata_probe_list():
    requirements = load_research_report_requirements()
    probe_fields = {item.canonical_field for item in raw_probe_requirements(requirements)}
    derived_fields = {item.canonical_field for item in derived_requirements(requirements)}

    assert derived_fields
    assert probe_fields.isdisjoint(derived_fields)
