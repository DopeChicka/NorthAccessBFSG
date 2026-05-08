from fastapi import APIRouter, HTTPException, status

from app.discovery.keywords import get_keyword_groups
from app.discovery.place_resolver import PlaceDataError, PlaceNotFoundError, resolve_city

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/places/{city}")
def get_places(city: str) -> dict[str, object]:
    try:
        matches = resolve_city(city)
    except PlaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PlaceDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {"city": city, "matches": [match.to_dict() for match in matches]}


@router.get("/keywords")
def get_keywords() -> dict[str, object]:
    return {"groups": get_keyword_groups()}
