from uuid import uuid4


class InMemoryPrivateStorage:
    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    async def put_private(self, content: bytes, mime_type: str) -> str:
        extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[mime_type]
        key = f"meal-images/{uuid4()}.{extension}"
        self._objects[key] = (content, mime_type)
        return key

    async def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    async def get_private(self, key: str) -> tuple[bytes, str] | None:
        return self._objects.get(key)

    def contains(self, key: str) -> bool:
        return key in self._objects
