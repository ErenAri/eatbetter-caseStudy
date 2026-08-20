from uuid import UUID

from app.domain.entities import CanonicalFood, CanonicalFoodCandidate, NutritionPer100g


class DemoNutritionProvider:
    """TEST/DEMO DATA — NOT USDA RESULTS."""

    source = "TEST_DEMO_DATA"
    uses_lexical_search = True
    _foods = {
        "fixture-chicken": ("Chicken breast, grilled", NutritionPer100g(165, 31, 0, 3.6)),
        "fixture-rice": ("Rice, white, cooked", NutritionPer100g(130, 2.7, 28.2, 0.3)),
        "fixture-broccoli": ("Broccoli, cooked", NutritionPer100g(35, 2.4, 7.2, 0.4)),
        "fixture-oil": ("Olive oil", NutritionPer100g(884, 0, 0, 100)),
        "fixture-cream-sauce": ("Cream sauce", NutritionPer100g(190, 3, 8, 16)),
        "fixture-cheese-sauce": ("Cheese sauce", NutritionPer100g(174, 6, 9, 13)),
    }

    async def search_foods(
        self, query: str, *, meal_item_id: UUID, limit: int = 5
    ) -> list[CanonicalFoodCandidate]:
        words = set(query.lower().split())
        matches = [
            (source_id, name, nutrition)
            for source_id, (name, nutrition) in self._foods.items()
            if words & set(name.lower().replace(",", "").split())
        ][:limit]
        return [
            CanonicalFoodCandidate(
                meal_item_id=meal_item_id,
                rank=rank,
                source=self.source,
                source_food_id=source_id,
                name=name,
                data={"data_type": "TEST/DEMO DATA — NOT USDA RESULTS"},
                nutrition_per_100g=nutrition,
            )
            for rank, (source_id, name, nutrition) in enumerate(matches, start=1)
        ]

    async def get_food(self, source_food_id: str) -> CanonicalFood | None:
        value = self._foods.get(source_food_id)
        if value is None:
            return None
        name, nutrition = value
        return CanonicalFood(
            source=self.source,
            source_food_id=source_food_id,
            name=name,
            nutrition_per_100g=nutrition,
            data={"data_type": "TEST/DEMO DATA — NOT USDA RESULTS"},
        )
