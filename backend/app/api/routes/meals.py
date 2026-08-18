from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status

from app.application.services.meal_contract_service import MealContractService
from app.domain.entities import Meal, MealItem, NutritionTotals
from app.fixtures import build_canonical_review_fixture, build_review_fixture

from ..dependencies import authenticated_user
from ..schemas import (
    AddMealItemRequest,
    AnswerClarificationRequest,
    CandidateResponse,
    CanonicalResponse,
    ClarificationResponse,
    ConfidenceResponse,
    CorrectionResponse,
    CreateMealRequest,
    DailySummaryResponse,
    ImageAttachedResponse,
    MealEnvelope,
    MealItemResponse,
    MealListResponse,
    MealResponse,
    NutritionTotalsResponse,
    PortionResponse,
    ReplaceMealItemRequest,
    UpdateMealItemRequest,
)


def _number(value: Decimal | None) -> float | None:
    return float(round(value, 3)) if value is not None else None


def nutrition_response(value: NutritionTotals | None) -> NutritionTotalsResponse | None:
    if value is None:
        return None
    return NutritionTotalsResponse(
        calories_kcal=_number(value.calories_kcal) or 0,
        protein_g=_number(value.protein_g) or 0,
        carbs_g=_number(value.carbs_g) or 0,
        fat_g=_number(value.fat_g) or 0,
    )


def item_response(item: MealItem) -> MealItemResponse:
    canonical = None
    if item.canonical_food_id and item.canonical_source and item.canonical_food_name:
        canonical = CanonicalResponse(
            source=item.canonical_source,
            food_id=item.canonical_food_id,
            name=item.canonical_food_name,
        )
    return MealItemResponse(
        id=item.id,
        position=item.position,
        observed_name=item.observed_name,
        normalized_name=item.normalized_name,
        preparation_method=item.preparation_method,
        canonical=canonical,
        candidates=[
            CandidateResponse(
                rank=value.rank,
                source=value.source,
                food_id=value.source_food_id,
                name=value.name,
                display_name=value.display_name(),
            )
            for value in sorted(item.candidates, key=lambda candidate: candidate.rank)
        ],
        portion=PortionResponse(
            min_g=_number(item.portion_estimate.min_g),
            max_g=_number(item.portion_estimate.max_g),
            confirmed_g=_number(item.confirmed_portion_g),
            resolution_source=item.portion_resolution_source,
        ),
        confidence=ConfidenceResponse(canonical=_number(item.canonical_confidence)),
        requires_clarification=item.requires_clarification,
        clarification_resolved=item.clarification_resolved,
        is_removed=item.is_removed,
        is_user_added=item.is_user_added,
        nutrition=nutrition_response(item.final_nutrition),
        review_status=(
            "REMOVED"
            if item.is_removed
            else "NEEDS_IDENTITY"
            if item.canonical_food_id is None
            else "NEEDS_REVIEW"
            if item.requires_clarification
            else "NEEDS_PORTION"
            if item.confirmed_portion_g is None
            else "READY"
        ),
    )


def meal_response(meal: Meal) -> MealResponse:
    blocking_types = {
        value.type
        for value in meal.clarifications
        if value.blocking and not value.resolution_satisfied
    }
    if str(meal.status) not in {"NEEDS_REVIEW", "CONFIRMED"}:
        review_status = "NOT_READY"
    elif {"CANONICAL_SELECTION", "FOOD_IDENTITY"} & blocking_types:
        review_status = "NEEDS_IDENTITY"
    elif "HIDDEN_INGREDIENT" in blocking_types:
        review_status = "NEEDS_HIDDEN_INGREDIENT"
    elif "PORTION" in blocking_types:
        review_status = "NEEDS_PORTION"
    else:
        review_status = "READY"
    return MealResponse(
        id=meal.id,
        meal_request_id=meal.meal_request_id,
        status=meal.status,
        image_attached=meal.image_path is not None,
        user_context=meal.user_context,
        logged_at=meal.logged_at,
        created_at=meal.created_at,
        updated_at=meal.updated_at,
        confirmed_at=meal.confirmed_at,
        failure_code=meal.failure_code,
        items=[item_response(value) for value in sorted(meal.items, key=lambda item: item.position)],
        clarifications=[
            ClarificationResponse(
                id=value.id,
                meal_item_id=value.meal_item_id,
                type=value.type,
                question=value.question,
                options=list(value.options),
                reason_codes=list(value.reason_codes),
                status=value.status,
                answer=value.answer,
                created_at=value.created_at,
                answered_at=value.answered_at,
                blocking=value.blocking,
                resolution_satisfied=value.resolution_satisfied,
            )
            for value in meal.clarifications
        ],
        corrections=[
            CorrectionResponse(
                id=value.id,
                meal_item_id=value.meal_item_id,
                field_name=value.field_name,
                predicted_value=value.predicted_value,
                corrected_value=value.corrected_value,
                correction_source=value.correction_source,
                created_at=value.created_at,
            )
            for value in meal.corrections
        ],
        totals=nutrition_response(meal.totals()) or NutritionTotalsResponse(
            calories_kcal=0, protein_g=0, carbs_g=0, fat_g=0
        ),
        review_status=review_status,
    )


def create_router(service: MealContractService, *, enable_dev_fixtures: bool) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["meals"])

    @router.post(
        "/meals",
        response_model=MealEnvelope,
        status_code=status.HTTP_201_CREATED,
        summary="Create an idempotent meal shell",
    )
    async def create_meal(
        request: CreateMealRequest,
        response: Response,
        user_id: UUID = Depends(authenticated_user),
    ) -> MealEnvelope:
        meal, replay = await service.create_meal(
            user_id=user_id,
            meal_request_id=request.meal_request_id,
            logged_at=request.logged_at,
            user_context=request.user_context,
        )
        response.status_code = status.HTTP_200_OK if replay else status.HTTP_201_CREATED
        return MealEnvelope(meal=meal_response(meal))

    @router.get("/meals", response_model=MealListResponse, summary="List owned meals")
    async def list_meals(
        on_date: date | None = Query(default=None, alias="date"),
        limit: int = Query(default=20, ge=1, le=100),
        cursor: str | None = Query(default=None, max_length=200),
        user_id: UUID = Depends(authenticated_user),
    ) -> MealListResponse:
        meals, next_cursor = await service.list_meals(
            user_id=user_id, on_date=on_date, limit=limit, cursor=cursor
        )
        return MealListResponse(
            items=[meal_response(value) for value in meals], next_cursor=next_cursor
        )

    @router.get(
        "/daily-summary",
        response_model=DailySummaryResponse,
        summary="Get a confirmed daily summary in an explicit timezone",
    )
    async def daily_summary(
        on_date: date = Query(alias="date"),
        timezone_name: str = Query(default="UTC", alias="timezone", max_length=100),
        user_id: UUID = Depends(authenticated_user),
    ) -> DailySummaryResponse:
        meals, totals = await service.today_summary(
            user_id=user_id, on_date=on_date, timezone_name=timezone_name
        )
        return DailySummaryResponse(
            date=on_date,
            timezone=timezone_name,
            totals=nutrition_response(totals),
            meals=[meal_response(value) for value in meals],
        )

    @router.get("/meals/{meal_id}", response_model=MealEnvelope, summary="Get an owned meal")
    async def get_meal(
        meal_id: UUID, user_id: UUID = Depends(authenticated_user)
    ) -> MealEnvelope:
        return MealEnvelope(meal=meal_response(await service.get_meal(meal_id, user_id)))

    @router.post(
        "/meals/{meal_id}/image",
        response_model=ImageAttachedResponse,
        summary="Attach a validated private meal image",
    )
    async def upload_image(
        meal_id: UUID,
        image: UploadFile = File(),
        user_id: UUID = Depends(authenticated_user),
    ) -> ImageAttachedResponse:
        content = await image.read(service.max_upload_bytes + 1)
        meal = await service.attach_image(
            meal_id=meal_id,
            user_id=user_id,
            content=content,
            mime_type=image.content_type or "",
        )
        return ImageAttachedResponse(meal_id=meal.id, image_attached=True)

    @router.post(
        "/meals/{meal_id}/analysis",
        response_model=MealEnvelope,
        summary="Start or inspect idempotent meal analysis",
    )
    async def start_analysis(
        meal_id: UUID,
        request: Request,
        user_id: UUID = Depends(authenticated_user),
    ) -> MealEnvelope:
        request_id = UUID(request.state.request_id)
        return MealEnvelope(
            meal=meal_response(await service.start_analysis(meal_id, user_id, request_id))
        )

    @router.patch(
        "/meals/{meal_id}/items/{item_id}",
        response_model=MealEnvelope,
        summary="Apply a controlled item correction",
    )
    async def update_item(
        meal_id: UUID,
        item_id: UUID,
        request: UpdateMealItemRequest,
        user_id: UUID = Depends(authenticated_user),
    ) -> MealEnvelope:
        changes: dict[str, Any] = {
            field: getattr(request, field) for field in request.model_fields_set
        }
        meal = await service.update_item(
            meal_id=meal_id,
            item_id=item_id,
            user_id=user_id,
            changes=changes,
        )
        return MealEnvelope(meal=meal_response(meal))

    @router.delete(
        "/meals/{meal_id}/items/{item_id}",
        response_model=MealEnvelope,
        summary="Logically remove a predicted item",
    )
    async def remove_item(
        meal_id: UUID,
        item_id: UUID,
        user_id: UUID = Depends(authenticated_user),
    ) -> MealEnvelope:
        meal = await service.remove_item(meal_id=meal_id, item_id=item_id, user_id=user_id)
        return MealEnvelope(meal=meal_response(meal))

    @router.post(
        "/meals/{meal_id}/items",
        response_model=MealEnvelope,
        status_code=status.HTTP_201_CREATED,
        summary="Record a missing-food correction pending canonical grounding",
    )
    async def add_item(
        meal_id: UUID,
        request: AddMealItemRequest,
        http_request: Request,
        user_id: UUID = Depends(authenticated_user),
    ) -> MealEnvelope:
        meal = await service.add_missing_item(
            meal_id=meal_id,
            user_id=user_id,
            query=request.query,
            portion_g=request.portion_g,
            request_id=UUID(http_request.state.request_id),
        )
        return MealEnvelope(meal=meal_response(meal))

    @router.post(
        "/meals/{meal_id}/items/{item_id}/replacement",
        response_model=MealEnvelope,
        summary="Atomically replace an unresolved predicted food",
    )
    async def replace_item(
        meal_id: UUID,
        item_id: UUID,
        request: ReplaceMealItemRequest,
        http_request: Request,
        user_id: UUID = Depends(authenticated_user),
    ) -> MealEnvelope:
        meal = await service.replace_item(
            meal_id=meal_id,
            item_id=item_id,
            user_id=user_id,
            query=request.query,
            portion_g=request.portion_g,
            request_id=UUID(http_request.state.request_id),
        )
        return MealEnvelope(meal=meal_response(meal))

    @router.post(
        "/meals/{meal_id}/clarifications/{clarification_id}/answer",
        response_model=MealEnvelope,
        summary="Answer a validated clarification",
    )
    async def answer_clarification(
        meal_id: UUID,
        clarification_id: UUID,
        request: AnswerClarificationRequest,
        user_id: UUID = Depends(authenticated_user),
    ) -> MealEnvelope:
        meal = await service.answer_clarification(
            meal_id=meal_id,
            clarification_id=clarification_id,
            user_id=user_id,
            option_id=request.option_id,
            custom_grams=request.custom_grams,
        )
        return MealEnvelope(meal=meal_response(meal))

    @router.post(
        "/meals/{meal_id}/confirm",
        response_model=MealEnvelope,
        summary="Confirm a fully grounded meal",
    )
    async def confirm_meal(
        meal_id: UUID, user_id: UUID = Depends(authenticated_user)
    ) -> MealEnvelope:
        return MealEnvelope(meal=meal_response(await service.confirm_meal(meal_id, user_id)))

    @router.delete(
        "/meals/{meal_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete an owned meal and its private image",
    )
    async def delete_meal(
        meal_id: UUID, user_id: UUID = Depends(authenticated_user)
    ) -> Response:
        await service.delete_meal(meal_id, user_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if enable_dev_fixtures:
        @router.post(
            "/dev/fixtures/review-meal",
            response_model=MealEnvelope,
            status_code=status.HTTP_201_CREATED,
            tags=["development"],
            summary="Create the deterministic P2 review fixture",
        )
        async def create_review_fixture(
            user_id: UUID = Depends(authenticated_user),
        ) -> MealEnvelope:
            fixture = build_review_fixture(user_id)
            meal, _ = await service.repository.create(fixture)
            return MealEnvelope(meal=meal_response(meal))

        @router.post(
            "/dev/fixtures/canonical-review-meal",
            response_model=MealEnvelope,
            status_code=status.HTTP_201_CREATED,
            tags=["development"],
            summary="Create a deterministic canonical ambiguity fixture",
        )
        async def create_canonical_review_fixture(
            user_id: UUID = Depends(authenticated_user),
        ) -> MealEnvelope:
            fixture = build_canonical_review_fixture(user_id)
            meal, _ = await service.repository.create(fixture)
            return MealEnvelope(meal=meal_response(meal))

    return router
