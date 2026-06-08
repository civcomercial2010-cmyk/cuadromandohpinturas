# cuadromandohpinturas

Cuadro de mando **V2** Hipopotamo Pinturas (Vista CEO, Centros, Comercial, Histórico).

## URLs

- **Producción (GitHub Pages):** https://civcomercial2010-cmyk.github.io/cuadromandohpinturas/cuadro_mando.html
- **Mismo cuadro (archivo fuente V2):** `cuadro_mando_v2.html` en este repo

## Archivos

| Archivo | Uso |
|---------|-----|
| `cuadro_mando_v2.html` | Plantilla y desarrollo |
| `cuadro_mando.html` | Publicado en Pages (debe estar sincronizado con V2) |
| `cuadro_mando_base.html` | Base para el actualizador automático |
| `actualizar_gha.py` | Workflow nocturno (Gmail → ERP → HTML) |
| `gas/DESACTIVAR_APPS_SCRIPT.md` | Cómo apagar el Apps Script legacy que provoca rate limit en Drive |

**Actualización automática:** GitHub Actions ~20:05 (Madrid), con reintentos hasta ~20:50. Ejecución manual: Actions → *Actualizar Cuadro de Mando* → *Run workflow*.

**Importante:** Si recibes correos «Error al actualizar Google Sheets», desactiva el Apps Script según `gas/DESACTIVAR_APPS_SCRIPT.md`. Ese flujo ya no alimenta el cuadro público.

Tras cambios locales, sincroniza también `C:\Hipopotamo\` con `.\sincronizar_a_hipopotamo.ps1` si usas `ejecutar.bat` en el PC.
