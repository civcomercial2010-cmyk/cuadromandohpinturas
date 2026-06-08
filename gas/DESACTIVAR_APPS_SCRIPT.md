# Apps Script legacy — error «User rate limit exceeded»

El correo de error **«No se pudo convertir el Excel»** (`leerExcel` / `actualizarDesdeGmail`) **no viene de GitHub Actions**. Lo genera un **Google Apps Script** antiguo que convierte el Excel con la API de Drive (`Drive.Files.insert` + `convert: true`). Esa API tiene **límite estricto por usuario** y falla con `403 userRateLimitExceeded` si se dispara varias veces al día o en paralelo con otros scripts.

## Canal oficial (desde 2026)

La actualización del cuadro público la hace **solo**:

- Workflow **Actualizar Cuadro de Mando** en este repo (`actualizar_gha.py` + `openpyxl`, sin Google Drive).
- Publicación: https://civcomercial2010-cmyk.github.io/cuadromandohpinturas/cuadro_mando.html

## Qué hacer en Google Apps Script (obligatorio)

1. Abre https://script.google.com y el proyecto que contiene `actualizarDesdeGmail` / `leerExcel`.
2. **Activadores** (reloj izquierda) → elimina los disparos diarios de `actualizarDesdeGmail`.
3. Opcional: en el cuerpo de `actualizarDesdeGmail`, deja solo:

```javascript
function actualizarDesdeGmail() {
  // Desactivado: el cuadro se actualiza vía GitHub Actions (cuadromandohpinturas).
  // No usar Drive.Files.insert(convert) — provoca rate limit 403.
  return;
}
```

4. Guarda y **no** vuelvas a crear activadores en ese script.

Con eso dejan de llegar los correos de error y se evita competir con el pipeline de GitHub por la misma cuenta Google.

## Si necesitas seguir escribiendo en Google Sheets

No reutilices la conversión Drive en bucle. Alternativas:

- Exportar el Excel a CSV desde el ERP y leer CSV en Apps Script, o
- Mantener solo el dashboard en GitHub Pages y usar Sheets como copia manual.
