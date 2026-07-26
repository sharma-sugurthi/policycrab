from app.tools.cpt_icd_lookup import lookup_cpt_code


def test_generic_mri_does_not_default_to_brain_mri():
    result = lookup_cpt_code.invoke({"procedure_description": "MRI"})

    assert "too broad" in result
    assert "CPT 70551" in result
    assert "CPT 73721" in result
    assert "CPT Code: 70553" not in result


def test_specific_knee_mri_returns_lower_extremity_joint_code():
    result = lookup_cpt_code.invoke({"procedure_description": "right knee MRI"})

    assert "CPT 73721" in result
    assert "MRI Lower Extremity Joint Without Contrast" in result
