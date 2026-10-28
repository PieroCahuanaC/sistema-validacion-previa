# Guía de contribución

1. Crea una rama desde `calidad` con el formato `feat/<modulo>-<tema>`.
2. Aplica la [convención de codificación](docs/convenciones.md) y escribe commits pequeños con
   *Conventional Commits* en español: `<tipo>(<ámbito>): <descripción en imperativo>`.
3. Antes de hacer *push*, ejecuta en `backend/`:

   ```bash
   ruff check .
   pytest --cov
   ```

4. Abre un *pull request* hacia `calidad` y completa la plantilla. Cuando calidad esté validada,
   se abre otro *pull request* de `calidad` hacia `main`.

Las instrucciones para levantar el ambiente de desarrollo están en el [README](README.md).
