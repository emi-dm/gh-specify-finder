from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MatchRecord:
    nombre_repo: str
    url_repo: str = ""
    estrellas: int | None = None
    ruta_coincidente: str = ""
    rutas_coincidentes: list[str] = field(default_factory=list)
    origen: str = ""
    metadatos: dict[str, Any] = field(default_factory=dict)

    def add_path(self, path: str) -> None:
        path = (path or "").strip()
        if not path:
            return
        if path not in self.rutas_coincidentes:
            self.rutas_coincidentes.append(path)
        if not self.ruta_coincidente:
            self.ruta_coincidente = path

