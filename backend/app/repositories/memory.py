import asyncio
from datetime import date
from uuid import UUID

from app.domain.entities import Meal


class InMemoryMealRepository:
    """Deterministic P2 adapter; mirrors ownership and uniqueness database constraints."""

    def __init__(self) -> None:
        self._meals: dict[UUID, Meal] = {}
        self._request_index: dict[tuple[UUID, UUID], UUID] = {}
        self._lock = asyncio.Lock()

    async def create(self, meal: Meal) -> tuple[Meal, bool]:
        async with self._lock:
            key = (meal.user_id, meal.meal_request_id)
            existing_id = self._request_index.get(key)
            if existing_id:
                return self._meals[existing_id], True
            self._meals[meal.id] = meal
            self._request_index[key] = meal.id
            return meal, False

    async def save(self, meal: Meal) -> None:
        self._meals[meal.id] = meal

    async def get_owned(self, meal_id: UUID, user_id: UUID) -> Meal | None:
        meal = self._meals.get(meal_id)
        return meal if meal and meal.user_id == user_id else None

    async def get_by_request_id(self, meal_request_id: UUID, user_id: UUID) -> Meal | None:
        meal_id = self._request_index.get((user_id, meal_request_id))
        return self._meals.get(meal_id) if meal_id else None

    async def list_owned(
        self,
        user_id: UUID,
        *,
        on_date: date | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Meal], str | None]:
        values = [
            meal
            for meal in self._meals.values()
            if meal.user_id == user_id and (on_date is None or meal.logged_at.date() == on_date)
        ]
        values.sort(key=lambda value: (value.logged_at, value.id), reverse=True)
        if cursor:
            try:
                cursor_time, cursor_id = cursor.rsplit("|", 1)
                values = [
                    meal
                    for meal in values
                    if (meal.logged_at.isoformat(), str(meal.id)) < (cursor_time, cursor_id)
                ]
            except ValueError:
                values = []
        page = values[:limit]
        next_cursor = None
        if len(values) > limit and page:
            last = page[-1]
            next_cursor = f"{last.logged_at.isoformat()}|{last.id}"
        return page, next_cursor

    async def delete_owned(self, meal_id: UUID, user_id: UUID) -> Meal | None:
        meal = await self.get_owned(meal_id, user_id)
        if meal is None:
            return None
        self._meals.pop(meal_id, None)
        self._request_index.pop((user_id, meal.meal_request_id), None)
        return meal

    # Compatibility methods for preserved pre-P2 experimental tests.
    async def add(self, meal):
        created, _ = await self.create(meal)
        return created

    async def get_for_user(self, meal_id, user_id):
        return await self.get_owned(meal_id, user_id)

    async def list_for_user(self, user_id):
        return sorted(
            (meal for meal in self._meals.values() if meal.user_id == user_id),
            key=lambda meal: meal.created_at,
            reverse=True,
        )

    async def update_state(self, meal) -> None:
        await self.save(meal)

    async def persist_items(self, meal) -> None:
        await self.save(meal)

    async def persist_corrections(self, meal) -> None:
        await self.save(meal)

    async def get_meal(self, meal_id, user_id):
        return await self.get_owned(meal_id, user_id)
