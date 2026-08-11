import pathlib

JS = pathlib.Path("static/js/school-finder.js").read_text(encoding="utf-8")

def test_gender_filter_normalises_public_gender_values_and_unambiguous_names():
    assert "female" in JS and "girls" in JS
    assert "male" in JS and "boys" in JS
    assert "for girls" in JS
    assert "for boys" in JS
    assert "normaliseGender(s.gender, s.name)" in JS
