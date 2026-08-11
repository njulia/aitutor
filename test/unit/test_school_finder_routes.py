from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.webapp.school_finder_routes import build_school_finder_router, _normalise_postcode, _gender_category, _route_category, _eligibility_label


def test_normalise_postcode():
    assert _normalise_postcode("n22 8aa") == "N22 8AA"


def test_invalid_postcode_rejected():
    app = FastAPI(); app.include_router(build_school_finder_router())
    client = TestClient(app)
    response = client.post('/api/schools/nearby', json={'postcode':'ZZZZ 9ZZ'})
    assert response.status_code == 400


def test_gender_and_route_classification():
    assert _gender_category({'gender':'girls'}, 'Example School') == 'Girls'
    assert _gender_category({}, "Example Boys School") == 'Boys'
    assert _route_category({'selective':'yes'}, 'Example School') == 'Selective / grammar'


def test_child_gender_screening_is_not_guarantee():
    assert _eligibility_label('Girls', 'boy', 'Year 7').startswith('Usually not')
    assert _eligibility_label('Girls', 'girl', 'Year 7').startswith('Potential option')


def test_nearby_endpoint_passes_child_context_without_storage():
    app = FastAPI(); app.include_router(build_school_finder_router())
    payload = {'postcode':'N22 8AA','area':'Test','schools':[{'name':'Girls School','distance_km':1.2,'gender':'Girls','route':'Selective / grammar','eligibility':'Potential option'}]}
    with patch('src.webapp.school_finder_routes._fetch_nearby', new=AsyncMock(return_value=payload)) as mocked:
        client = TestClient(app)
        response = client.post('/api/schools/nearby', json={'postcode':'N22 8AA','entry_year':'Year 7','child_gender':'girl'})
        assert response.status_code == 200
        mocked.assert_awaited_once_with('N22 8AA','Year 7','girl')
