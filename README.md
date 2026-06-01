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

Tras cambios locales, sincroniza también `C:\Hipopotamo\` con `.\sincronizar_a_hipopotamo.ps1` si usas `ejecutar.bat` en el PC.
