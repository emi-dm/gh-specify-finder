"""
Paquete gh-specify-finder: búsqueda de repositorios con Spec Kit mediante GitHub CLI.

Expone el modelo `MatchRecord` y la versión del paquete. La entrada habitual es el comando
`gh-specify-finder` definido en `pyproject.toml` → `cli:main`.
"""

from .models import MatchRecord

__all__ = ["MatchRecord"]
__version__ = "0.1.0"
