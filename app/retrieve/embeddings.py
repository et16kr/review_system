from __future__ import annotations

import hashlib
import math

from app.text_utils import tokenize


class HashingEmbedder:
    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        return [self._embed(document) for document in documents]

    def embed_query(self, document: str) -> list[float]:
        return self._embed(document)

    def _embed(self, document: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(document):
            index = self._index_for_token(token)
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    def _index_for_token(self, token: str) -> int:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, byteorder="big") % self.dimensions
