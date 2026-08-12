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
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.webapp.school_finder_exclusions import (
    create_school_report,
    exclude_school,
    is_school_excluded,
    list_excluded_schools,
    list_school_reports,
    review_school_report,
    restore_school as restore_excluded_school,
)

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
    """Return True unless public school tags clearly show a primary/early-years school.

    Many UK OSM records omit phase metadata.  We only reject schools with
    explicit primary signals; all other schools are treated as potential
    secondary/through candidates.  Administrators can exclude misclassified
    primary schools via the admin panel.
    """
    values = {str(k).lower(): str(v or "").strip().lower() for k, v in tags.items()}
    level = " ".join(values.get(k, "") for k in ("school:level", "isced:level", "education", "phase", "school:phase"))
    age_text = " ".join(values.get(k, "") for k in ("age", "grades", "min_age", "max_age", "start_age", "end_age"))
    name = values.get("name", "")

    # 显式标记为小学/低年级的学校才排除
    # Exclude only schools with explicit primary/early-years signals, including names.
    if re.search(r"\b(primary|infant|junior|nursery|reception|prep)\b", name):
        return False

    if any(x in level for x in ("primary", "infant", "junior", "first school")):
        return False
    if any(x in age_text for x in ("3-11", "3 – 11", "4-11", "4 – 11", "5-11", "5 – 11", "reception")) and not any(
        x in level for x in ("secondary", "isced:level=2", "isced:level=3")
    ):
        return False

    # 其余学校（包含缺乏阶段元数据的）默认视为中学候选，由管理员面板排除误判学校
    # Treat all remaining schools (including those without phase metadata)
    # as secondary-school candidates.  Admins can exclude misclassified
    # primary schools via the admin panel.
    return True


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


async def _fetch_overpass_elements(client: httpx.AsyncClient, lat: float, lon: float) -> list[dict[str, Any]]:
    """Fetch nearby school records from public Overpass mirrors.

    Cloud-hosted deployments can be rejected when sending large POST bodies to
    public Overpass instances.  Use the standard GET ``data=`` interface first,
    keep the query small, and rotate through current public mirrors.  A valid
    empty result is a successful lookup, not an outage.
    """
    endpoints = (
        "https://overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.osm.ch/api/interpreter",
    )
    # Keep the live request small enough for a normal web request.  The second
    # radius is only attempted when the first query succeeds but finds nothing.
    radii = (12000, 18000)
    last_error: str | None = None

    for radius in radii:
        # 仅使用 amenity=school 标签获取所有学校，避免昂贵的正则 nwr 查询。
        # 中学筛选在 Python 端 _is_secondary_school() 中完成。
        query = f"""
        [out:json][timeout:15];
        (
          nwr(around:{radius},{lat},{lon})[amenity=school];
        );
        out center tags;
        """
        for endpoint in endpoints:
            try:
                # GET is deliberately used here.  Some public Overpass mirrors
                # and cloud egress paths reject POST requests even for valid
                # OverpassQL, while GET is part of the documented interface.
                response = await client.get(endpoint, params={"data": query})
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code} from {endpoint}"
                    continue
                payload = response.json()
                elements = payload.get("elements") or []
                if elements:
                    return elements
                # Empty is a successful directory lookup.  Try the larger
                # radius before declaring that there are no nearby records.
                last_error = None
                break
            except (httpx.HTTPError, ValueError) as exc:
                last_error = f"{endpoint}: {exc}"

    if last_error:
        raise HTTPException(
            status_code=503,
            detail="The public school directory is temporarily unavailable. Please try again.",
        )
    return []


async def _fetch_nearby(postcode: str, entry_year: str = "Year 7", child_gender: str = "any", include_admin_fields: bool = False) -> dict[str, Any]:
    headers = {"User-Agent": "HomeworkMagic/1.0 (school-finder; public-directory)"}
    timeout = httpx.Timeout(12.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        try:
            geo = await client.get(f"https://api.postcodes.io/postcodes/{postcode.replace(' ', '')}")
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="The postcode service is temporarily unavailable. Please try again.")
        if geo.status_code != 200:
            raise HTTPException(status_code=400, detail="We could not find that postcode. Please check it and try again.")
        try:
            payload = geo.json().get("result") or {}
            lat = float(payload["latitude"])
            lon = float(payload["longitude"])
        except (ValueError, TypeError, KeyError):
            raise HTTPException(status_code=503, detail="The postcode service returned an invalid result. Please try again.")
        council = payload.get("admin_district") or payload.get("parliamentary_constituency")

        elements = await _fetch_overpass_elements(client, lat, lon)

    schools: list[dict[str, Any]] = []
    seen: set[str] = set()
    for el in elements:
        tags = el.get("tags") or {}
        name = str(tags.get("name") or "").strip()
        if not name or not _is_secondary_school(tags):
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
        source_type = str(el.get("type") or "").strip().lower()
        source_osm_id = str(el.get("id") or "").strip()
        source_id = f"osm:{source_type}:{source_osm_id}" if source_type and source_osm_id else ""
        schools.append({
            "name": name,
            "source_id": source_id,
            "latitude": float(slat),
            "longitude": float(slon),
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

    schools = [
        school for school in schools
        if not is_school_excluded(
            source_id=school.get("source_id", ""),
            name=school.get("name", ""),
            latitude=school.get("latitude"),
            longitude=school.get("longitude"),
        )
    ]
    schools.sort(key=lambda x: x["distance_km"])
    for school in schools:
        school["eligibility"] = _eligibility({}, school["name"], child_gender, entry_year)
        if school.get("gender") and school["gender"] != "Not stated":
            school["eligibility"] = _eligibility({"gender": school["gender"]}, school["name"], child_gender, entry_year)
    if not include_admin_fields:
        for school in schools:
            school.pop("latitude", None)
            school.pop("longitude", None)

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


def build_school_finder_admin_router(require_admin) -> APIRouter:
    """Protected administrator controls for persistent school exclusions."""
    router = APIRouter(prefix="/api/admin/schools", tags=["admin school finder"])

    @router.post("/nearby")
    async def admin_nearby(req: Request, body: dict):
        require_admin(req)
        postcode = _normalise_postcode(str(body.get("postcode") or ""))
        return await _fetch_nearby(
            postcode,
            str(body.get("entry_year") or "Year 7"),
            str(body.get("child_gender") or "any"),
            include_admin_fields=True,
        )

    @router.get("/excluded")
    async def excluded_schools(req: Request):
        require_admin(req)
        return {"success": True, "schools": list_excluded_schools()}

    @router.get("/reports")
    async def school_reports(req: Request, status: str = "pending"):
        require_admin(req)
        return {"success": True, "reports": list_school_reports(status if status != "all" else None)}

    @router.post("/reports/{report_id}/review")
    async def review_school_report_endpoint(req: Request, report_id: str, body: dict):
        admin_email = require_admin(req)
        action = str(body.get("action") or "").strip().lower()
        note = str(body.get("note") or "").strip()[:500]
        try:
            row = review_school_report(report_id=report_id, action=action, reviewed_by=str(admin_email), review_note=note)
        except KeyError:
            raise HTTPException(status_code=404, detail="School report not found.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"success": True, "report": row}

    @router.post("/exclude")
    async def exclude_school_endpoint(req: Request, body: dict):
        admin_email = require_admin(req)
        name = str(body.get("name") or "").strip()
        source_id = str(body.get("source_id") or "").strip()
        if not name or not source_id:
            raise HTTPException(status_code=400, detail="School name and source ID are required.")
        try:
            latitude = float(body["latitude"]) if body.get("latitude") is not None else None
            longitude = float(body["longitude"]) if body.get("longitude") is not None else None
        except (TypeError, ValueError):
            latitude = longitude = None
        row = exclude_school(
            source_id=source_id,
            name=name,
            latitude=latitude,
            longitude=longitude,
            reason=str(body.get("reason") or "Marked not a secondary school").strip()[:500],
            excluded_by=str(admin_email),
        )
        return {"success": True, "school": row}

    @router.delete("/exclude/{source_id:path}")
    async def restore_school_endpoint(req: Request, source_id: str):
        require_admin(req)
        restore_excluded_school(source_id)
        return {"success": True}

    return router


def build_school_finder_router() -> APIRouter:
    router = APIRouter(prefix="/api/schools", tags=["school finder"])

    @router.post("/report")
    async def report_school_endpoint(body: dict):
        # Reporting is intentionally lightweight: no postcode or child data is stored.
        name = str(body.get("name") or "").strip()
        source_id = str(body.get("source_id") or "").strip()
        if not name or not source_id:
            raise HTTPException(status_code=400, detail="School name and source ID are required.")
        try:
            latitude = float(body["latitude"]) if body.get("latitude") is not None else None
            longitude = float(body["longitude"]) if body.get("longitude") is not None else None
        except (TypeError, ValueError):
            latitude = longitude = None
        row = create_school_report(
            source_id=source_id, name=name, latitude=latitude, longitude=longitude,
            reason=str(body.get("reason") or "This school is not a secondary school").strip()[:500],
        )
        return {"success": True, "report": row}

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
