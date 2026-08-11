"""Parent-facing nearby secondary-school finder.

Postcodes are used transiently to geocode a search and are never persisted.
The service deliberately reports nearby schools rather than guaranteeing a place:
admission rules vary by school, year, catchment, testing and other criteria.
"""
from __future__ import annotations

import math
import os
import re
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

_UK_POSTCODE = re.compile(r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$", re.I)


class SchoolFinderRequest(BaseModel):
    postcode: str = Field(min_length=5, max_length=10)
    entry_year: str = Field(default="Year 7", max_length=20)
    child_gender: str = Field(default="any", max_length=20)


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _normalise_postcode(value: str) -> str:
    postcode = re.sub(r"\s+", "", value or "").upper()
    if not _UK_POSTCODE.fullmatch(postcode):
        raise HTTPException(status_code=400, detail="Please enter a valid UK postcode.")
    return f"{postcode[:-3]} {postcode[-3:]}"


def _school_level(tags: dict[str, Any]) -> str:
    raw = " ".join(str(tags.get(k, "")) for k in (
        "school:level", "isced:level", "education", "grades", "age", "min_age", "max_age",
        "start_age", "end_age", "phase", "school:phase"
    )).lower()
    if _is_secondary_school(tags):
        return "Secondary / all-through"
    return ""


def _is_secondary_school(tags: dict[str, Any]) -> bool:
    """Return True only when public school tags provide a secondary-age signal.

    We intentionally do not treat "academy" by itself as secondary: many UK
    primary schools are academies (for example Mossbourne Riverside Academy).
    If the public directory does not identify the phase clearly, we skip the
    school rather than guessing.
    """
    values = {str(k).lower(): str(v or "").strip().lower() for k, v in tags.items()}
    level = " ".join(values.get(k, "") for k in ("school:level", "isced:level", "education", "phase", "school:phase"))
    age_text = " ".join(values.get(k, "") for k in ("age", "grades", "min_age", "max_age", "start_age", "end_age"))
    name = values.get("name", "")

    # Explicit primary/early-years signals always win.
    if any(x in level for x in ("primary", "infant", "junior", "first school")):
        return False
    if any(x in age_text for x in ("3-11", "3 – 11", "4-11", "4 – 11", "5-11", "5 – 11", "reception")) and not any(
        x in level for x in ("secondary", "isced:level=2", "isced:level=3")
    ):
        return False

    # Prefer explicit phase/IS​​CED/level data.
    if any(x in level for x in ("secondary", "isced:level=2", "isced:level=3", "secondary;tertiary", "tertiary;secondary")):
        return True

    # Common OSM age/grade representations for Year 7+ schools.
    if re.search(r"(?:^|[^0-9])(?:11|12|13|14|15|16|17|18)(?:\s*(?:-|–|to)\s*(?:16|17|18|19))", age_text):
        return True
    if re.search(r"(?:^|[^0-9])(?:7|8|9|10|11|12|13)(?:\s*(?:-|–|to)\s*(?:11|12|13|14|15|16|17|18))", age_text):
        return True
    if any(re.search(rf"\b{g}\b", age_text) for g in ("year 7", "year 8", "year 9", "year 10", "year 11", "ks3", "ks4")):
        return True

    # Name-based fallback is deliberately narrow; "academy" and "college"
    # alone are not enough because both are used for primary/FE settings.
    if any(x in name for x in ("grammar school", "secondary school", "high school")):
        return True

    return False


def _admission_hint(tags: dict[str, Any], name: str) -> str:
    raw = " ".join(str(v) for v in tags.values()).lower()
    n = name.lower()
    if any(x in raw for x in ("private", "independent")) or "college" in n and "sixth" in n:
        return "Independent: apply directly; check fees and entrance requirements"
    if any(x in n for x in ("grammar", "selective")) or "selective" in raw:
        return "Selective: entrance test / published criteria may apply"
    return "State school: check the local authority and school's admission criteria"


def _route_label(tags: dict[str, Any], name: str) -> str:
    raw = " ".join(str(v) for v in tags.values()).lower()
    n = name.lower()
    if "selective" in raw or "grammar" in n:
        return "Selective / grammar"
    if any(x in raw for x in ("private", "independent")):
        return "Independent"
    if "academy" in n or "academy" in raw:
        return "State / academy"
    return "State / non-selective"


def _eligibility(tags: dict[str, Any], name: str, gender: str, entry_year: str) -> str:
    school_gender = str(tags.get("gender") or tags.get("school:gender") or "").lower()
    if gender == "boy" and any(x in school_gender for x in ("female", "girls")):
        return "Usually not suitable for a boy — check the school's policy"
    if gender == "girl" and any(x in school_gender for x in ("male", "boys")):
        return "Usually not suitable for a girl — check the school's policy"
    return f"Potential {entry_year} option — confirm catchment, admissions and entrance requirements"


def _website(tags: dict[str, Any]) -> str | None:
    for key in ("website", "contact:website"):
        value = str(tags.get(key) or "").strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
    return None


async def _fetch_nearby(postcode: str, entry_year: str = "Year 7", child_gender: str = "any") -> dict[str, Any]:
    headers = {"User-Agent": "HomeworkMagic/1.0 school-finder"}
    async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
        geo = await client.get(f"https://api.postcodes.io/postcodes/{postcode.replace(' ', '')}")
        if geo.status_code != 200:
            raise HTTPException(status_code=400, detail="We could not find that postcode. Please check it and try again.")
        payload = geo.json().get("result") or {}
        lat = float(payload["latitude"])
        lon = float(payload["longitude"])
        council = payload.get("admin_district") or payload.get("parliamentary_constituency")

        # OSM is used only as a public geographic directory.  The query asks for
        # secondary/all-through schools and returns no user data.
        query = f"""
        [out:json][timeout:8];
        (
          nwr(around:18000,{lat},{lon})[amenity=school][school:level~"secondary|primary;secondary|secondary;tertiary",i];
          nwr(around:18000,{lat},{lon})[amenity=school][isced:level~"2|3",i];
          nwr(around:18000,{lat},{lon})[amenity=school][grades~"7|8|9|10|11|12",i];
        );
        out center tags;
        """
        # Overpass instances can be busy and the more selective tag query is not
        # consistently supported across instances. Try a small pool of public
        # instances and use a broad school query, then filter locally.
        elements = []
        overpass_query = f"[out:json][timeout:15];nwr(around:18000,{lat},{lon})[amenity=school];out center tags;"
        endpoints = [
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
        ]
        last_error = None
        for endpoint in endpoints:
            try:
                osm = await client.post(endpoint, content=overpass_query)
                if osm.status_code == 200:
                    elements = osm.json().get("elements", [])
                    if elements:
                        break
                last_error = f"HTTP {osm.status_code}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
        if not elements and last_error:
            raise HTTPException(status_code=503, detail="The public school directory is temporarily unavailable. Please try again.")

    schools: list[dict[str, Any]] = []
    seen: set[str] = set()
    for el in elements:
        tags = el.get("tags") or {}
        name = str(tags.get("name") or "").strip()
        # Only include schools for which public directory data gives a
        # secondary-age signal. Do not infer secondary phase from generic words
        # such as "academy" or "college".
        if not _is_secondary_school(tags):
            continue
        if not name:
            continue
        centre = el.get("center") or {}
        slat, slon = el.get("lat", centre.get("lat")), el.get("lon", centre.get("lon"))
        if slat is None or slon is None:
            continue
        key = re.sub(r"[^a-z0-9]", "", name.lower())
        if key in seen:
            continue
        seen.add(key)
        distance = _distance_km(lat, lon, float(slat), float(slon))
        schools.append({
            "name": name,
            "distance_km": round(distance, 1),
            "type": tags.get("school:level") or tags.get("isced:level") or "Secondary school",
            "gender": tags.get("gender") or tags.get("school:gender") or "Not stated",
            "route": _route_label(tags, name),
            "eligibility": _eligibility(tags, name, "any", "Year 7"),
            "admission_hint": _admission_hint(tags, name),
            "level_note": _school_level(tags),
            "website": _website(tags),
            "address": ", ".join(x for x in (tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:town"), tags.get("addr:postcode")) if x),
            "source": "OpenStreetMap public school directory",
        })

    schools.sort(key=lambda x: x["distance_km"])
    for school in schools:
        school["eligibility"] = _eligibility({}, school["name"], child_gender, entry_year)
        if school.get("gender") and school["gender"] != "Not stated":
            school["eligibility"] = _eligibility({"gender": school["gender"]}, school["name"], child_gender, entry_year)
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    home_query = postcode.replace(" ", "+") + ", UK"
    for school in schools[:10]:
        school_query = ", ".join(x for x in (school.get("name"), school.get("address"), "UK") if x)
        school["google_maps_url"] = (
            "https://www.google.com/maps/dir/?api=1&origin=" + home_query +
            "&destination=" + quote(school_query)
        )
        if api_key:
            school["google_maps_embed_url"] = (
                "https://www.google.com/maps/embed/v1/directions?key=" + api_key +
                "&origin=" + quote(postcode + ", UK") +
                "&destination=" + quote(school_query)
            )

    return {
        "postcode": postcode,
        "area": council,
        "schools": schools[:10],
        "google_maps_enabled": bool(api_key),
        "notice": "These are the 10 nearest secondary/all-through schools found from public geographic data. A postcode alone cannot guarantee a place: check each school's current admission policy, catchment, entrance tests and application deadline.",
    }


def build_school_finder_router() -> APIRouter:
    router = APIRouter(prefix="/api/schools", tags=["school finder"])

    @router.post("/nearby")
    async def nearby(body: SchoolFinderRequest):
        postcode = _normalise_postcode(body.postcode)
        try:
            return await _fetch_nearby(postcode, body.entry_year, body.child_gender)
        except HTTPException:
            raise
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            raise HTTPException(status_code=503, detail="We could not look up schools right now. Please try again.")

    return router
