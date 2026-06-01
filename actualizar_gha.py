#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HIPOPOTAMO PINTURAS — Actualizador automático (GitHub Actions)
Lee configuración desde variables de entorno en lugar de config.json.
"""

import imaplib, email, email.header, os, sys, json, logging, re
import datetime, time, base64
import urllib.request, urllib.parse
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("ERROR: openpyxl no instalado. Ejecuta: pip install openpyxl")
    sys.exit(1)

# ─── CONFIG DESDE VARIABLES DE ENTORNO ───────────────────────────────────────

def cargar_config():
    cfg = {
        "gmail": {
            "email":               os.environ["GMAIL_EMAIL"],
            "password_app":        os.environ["GMAIL_PASSWORD"],
            "imap_server":         "imap.gmail.com",
            "imap_port":           993,
            "carpeta_busqueda":    "INBOX",
            "asunto_contiene":     "Ventas por caja",
            "remitente_contiene":  "reportes@hipopotamo.com",
            "nombre_adjunto":      "Ventas por caja",
            "buscar_ultimas_horas": 26,
        },
        "rutas": {
            "excel_descargado": "/tmp/ventas_por_caja.xlsx",
            "html_salida":      "/tmp/cuadro_mando.html",
            "html_plantilla":   "cuadro_mando_v2.html",
        },
        "github": {
            "token":           os.environ["GITHUB_TOKEN_HP"],
            "usuario":         os.environ.get("GITHUB_USUARIO", "civcomercial2010-cmyk"),
            "repositorio":     os.environ.get("GITHUB_REPO", "cuadromandohpinturas"),
            "archivo_destino": "cuadro_mando.html",
        },
        "telegram": {
            "bot_token": os.environ.get("TELEGRAM_TOKEN", ""),
            "chat_id":   os.environ.get("TELEGRAM_CHAT_ID", ""),
        },
        "opciones": {
            "reintentos_gmail":         1,
            "minutos_entre_reintentos": 5,
        },
    }
    return cfg

# ─── LOGGING ─────────────────────────────────────────────────────────────────

def setup_log():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

# ─── TELEGRAM ────────────────────────────────────────────────────────────────

def enviar_telegram(cfg, texto):
    bot  = cfg["telegram"].get("bot_token", "")
    chat = cfg["telegram"].get("chat_id", "")
    if not bot or not chat:
        return
    try:
        url  = f"https://api.telegram.org/bot{bot}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10):
            pass
        logging.info("OK Telegram enviado")
    except Exception as e:
        logging.warning(f"Telegram error: {e}")

# ─── MES COMERCIAL ───────────────────────────────────────────────────────────

def mes_comercial_actual():
    hoy = datetime.date.today()
    if hoy.day >= 26:
        return (1, hoy.year + 1) if hoy.month == 12 else (hoy.month + 1, hoy.year)
    return hoy.month, hoy.year

FESTIVOS_ZGZ = {
    2025: ["2025-01-01","2025-01-06","2025-03-05","2025-04-17","2025-04-18",
           "2025-04-23","2025-05-01","2025-10-12","2025-11-01","2025-12-06",
           "2025-12-08","2025-12-25"],
    2026: ["2026-01-01","2026-01-06","2026-03-05","2026-04-02","2026-04-03",
           "2026-04-23","2026-05-01","2026-10-12","2026-11-02","2026-12-07",
           "2026-12-08","2026-12-25"],
    2027: ["2027-01-01","2027-01-06","2027-03-05","2027-03-26","2027-03-29",
           "2027-04-23","2027-05-01","2027-10-12","2027-11-01","2027-12-06",
           "2027-12-08","2027-12-25"],
}

def dias_laborables_zgz(inicio, fin, ano):
    festivos = set(FESTIVOS_ZGZ.get(ano, []))
    count, d = 0, inicio
    while d <= fin:
        if d.weekday() < 5 and d.isoformat() not in festivos:
            count += 1
        d += datetime.timedelta(days=1)
    return count

def dias_mes_comercial(mes, ano, fecha_ref=None):
    mes_ant = 12 if mes == 1 else mes - 1
    ano_ant = ano - 1 if mes == 1 else ano
    inicio  = datetime.date(ano_ant, mes_ant, 26)
    fin     = datetime.date(ano, mes, 25)
    ref     = min(fecha_ref or datetime.date.today(), fin)
    total   = dias_laborables_zgz(inicio, fin, ano)
    trab    = dias_laborables_zgz(inicio, ref, ano)
    return trab, total

# ─── DESCARGAR EXCEL ─────────────────────────────────────────────────────────

def descargar_excel_gmail(cfg, intento=1):
    gcfg    = cfg["gmail"]
    destino = Path(cfg["rutas"]["excel_descargado"])
    destino.parent.mkdir(parents=True, exist_ok=True)
    logging.info(f"Conectando a Gmail ({gcfg['email']})... [intento {intento}]")
    try:
        mail = imaplib.IMAP4_SSL(gcfg["imap_server"], gcfg["imap_port"])
        mail.login(gcfg["email"], gcfg["password_app"])
    except Exception as e:
        logging.error(f"Error Gmail login: {e}")
        return False

    mail.select(gcfg.get("carpeta_busqueda", "INBOX"))
    desde = (datetime.datetime.now() -
             datetime.timedelta(hours=gcfg.get("buscar_ultimas_horas", 26))).strftime("%d-%b-%Y")
    criterios = []
    if gcfg.get("remitente_contiene"):
        criterios.append(f'FROM "{gcfg["remitente_contiene"]}"')
    if gcfg.get("asunto_contiene"):
        criterios.append(f'SUBJECT "{gcfg["asunto_contiene"]}"')
    criterios.append(f'SINCE "{desde}"')

    _, mensajes = mail.search(None, " ".join(criterios))
    ids = mensajes[0].split()
    if not ids:
        logging.warning("No se encontraron emails.")
        mail.logout()
        return False

    nombre_buscado = gcfg["nombre_adjunto"].lower()
    encontrado = False
    for msg_id in reversed(ids):
        _, data = mail.fetch(msg_id, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])
        logging.info(f"Revisando: {msg['Subject']} ({msg['Date']})")
        for parte in msg.walk():
            if parte.get_content_maintype() == "multipart":
                continue
            fn = parte.get_filename()
            if not fn:
                continue
            decoded = email.header.decode_header(fn)
            fn_dec = "".join(
                t.decode(enc or "utf-8") if isinstance(t, bytes) else t
                for t, enc in decoded
            )
            logging.info(f"  Adjunto: {fn_dec}")
            ext = fn_dec.lower()
            if (nombre_buscado in ext or
                    ext.endswith(".xlsx") or ext.endswith(".xlsm") or ext.endswith(".xlmx")):
                payload = parte.get_payload(decode=True)
                with open(destino, "wb") as f:
                    f.write(payload)
                logging.info(f"OK Excel descargado: {destino} ({len(payload):,} bytes)")
                encontrado = True
                break
        if encontrado:
            break

    mail.logout()
    return encontrado

# ─── PARSEAR EXCEL ───────────────────────────────────────────────────────────

def parsear_excel(ruta):
    logging.info(f"Parseando: {ruta}")
    try:
        wb = openpyxl.load_workbook(ruta, data_only=True)
        ws = wb.active
        logging.info(f"Hoja: {ws.title}")
    except Exception as e:
        logging.error(f"Error abriendo Excel: {e}")
        return None

    rows = list(ws.iter_rows(values_only=True))
    r = {"total":0,"sjp":0,"sjd":0,"garp":0,"gard":0,"alm":0,"avd":0,
         "cavero":0,"ursula":0,"prof":0,"pvp_pin":0,"pvp_ins":0,
         "distrib":0,"ind":0}

    def pN(v):
        try:
            f = float(v)
            return 0.0 if (f != f) else f
        except: return 0.0

    rawvPF = {}
    mode   = "c"

    for row in rows:
        tienda = str(row[0]).strip() if row[0] is not None else ""
        nombre = str(row[1]).strip() if row[1] is not None else ""
        grupo  = str(row[2]).strip().upper() if row[2] is not None else ""
        try:
            base   = pN(row[3])
            inst   = pN(row[4]) if len(row) > 4 else 0.0
            no_ins = pN(row[5]) if len(row) > 5 else 0.0
        except:
            continue

        if not tienda or tienda in ("VACIO","nan","Base Imponible","Tienda"):
            continue
        if "vendedor" in tienda.lower() and "total" not in tienda.lower():
            mode = "v"

        if tienda == "TOTAL INFORME":
            r["total"] = base
            continue

        if tienda == "TOTAL GRUPOS CLASIFICACION":
            if grupo in ("PVP","FINALES"):
                r["pvp_ins"] += inst
                r["pvp_pin"] += max(0, base - inst)
            elif grupo == "PROF":
                r["prof"] += base
            elif grupo.startswith("INDUSTRIA"):
                r["ind"] += base
            elif grupo in ("DISTRIB","DISTRIBUIDORES"):
                r["distrib"] += base
            continue

        if tienda == "TOTAL GRUPOS":
            continue

        if mode == "c" and tienda.startswith("Total tienda "):
            key = tienda.replace("Total tienda ", "").strip()
            # SJP = col F (No Instalaciones = pintura only)
            # todos los demás = col D (Base Imponible)
            if "SAN JOS" in key.upper() and key != "52":
                r["sjp"] += no_ins
            elif key == "52":
                r["sjd"] += base
            elif key == "36":
                r["garp"] += base
            elif key == "56":
                r["gard"] += base
            elif key == "ALMACEN":
                r["alm"] += base
            elif "AVD" in key.upper() and "MADRID" in key.upper():
                r["avd"] += base

        if mode == "v":
            if tienda.startswith("Total vendedor "):
                if "URSULA" in nombre.upper() or "ÚRSULA" in nombre.upper():
                    r["ursula"] += base
            elif not tienda.startswith("Total") and grupo == "PROFESIONALES" and nombre:
                if "CAVERO" in nombre.upper():
                    rawvPF["CAVERO"] = rawvPF.get("CAVERO", 0) + base

    r["cavero"] = rawvPF.get("CAVERO", 0)
    if not r["total"]:
        r["total"] = r["sjp"]+r["sjd"]+r["garp"]+r["gard"]+r["alm"]+r["avd"]

    for k in ["total","sjp","sjd","garp","gard","alm","avd",
              "cavero","ursula","prof","pvp_pin","pvp_ins","distrib","ind"]:
        r[k] = round(r[k], 2)

    # Leer fecha del ERP de las primeras filas
    for row in rows[:5]:
        if not row[0]:
            continue
        txt = str(row[0])
        m = re.search(r"Fecha:\s*(\d{1,2}/\d{1,2}/\d{2,4})\s+Hora:", txt)
        if m:
            r["fechaERP"] = f"ERP {m.group(1)}"
            try:
                dd, mm, yy = m.group(1).split("/")
                yy = int(yy)
                yy = 2000 + yy if yy < 100 else yy
                r["fechaERP_date"] = datetime.date(yy, int(mm), int(dd))
            except:
                pass
        m2 = re.search(r"Fecha hasta:\s*(\d{1,2}/\d{1,2}/\d{2,4})", txt)
        if m2:
            try:
                dd, mm, yy = m2.group(1).split("/")
                yy = int(yy)
                yy = 2000 + yy if yy < 100 else yy
                r["fechaHasta_date"] = datetime.date(yy, int(mm), int(dd))
            except:
                pass

    logging.info(
        f"Total: {r['total']:,.2f} € | "
        f"SJP:{r['sjp']:,.0f} SJD:{r['sjd']:,.0f} GARP:{r['garp']:,.0f} "
        f"GARD:{r['gard']:,.0f} ALM:{r['alm']:,.0f} AVD:{r['avd']:,.0f}"
    )
    logging.info(f"Cavero (PROF): {r['cavero']:,.0f} | Ursula: {r['ursula']:,.0f}")
    return r

def fecha_datos_excel(datos):
    """Fecha de corte del informe ERP (prioridad: Fecha hasta, luego Fecha del informe)."""
    fd = datos.get("fechaHasta_date") or datos.get("fechaERP_date")
    if fd:
        return fd.strftime("%d/%m/%Y")
    txt = datos.get("fechaERP") or ""
    m = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", txt)
    if not m:
        return None
    try:
        dd, mm, yy = m.group(1).split("/")
        yy = int(yy)
        yy = 2000 + yy if yy < 100 else yy
        return datetime.date(yy, int(mm), int(dd)).strftime("%d/%m/%Y")
    except Exception:
        return None

# ─── ACTUALIZAR HTML ─────────────────────────────────────────────────────────

MESES_CONST = {
    1: "ENE26", 2: "FEB26", 3: "MAR26", 4: "ABR26", 5: "MAY26", 6: "JUN26",
    7: "JUL26", 8: "AGO26", 9: "SEP26", 10: "OCT26", 11: "NOV26", 12: "DIC26",
}

REPO_HTML = ("cuadro_mando.html", "cuadro_mando_v2.html", "cuadro_mando_base.html")


def limpiar_inyect_previo(html):
    marker = "/* AUTO_DATA_INJECT */"
    idx = html.find(marker)
    if idx == -1:
        return html
    tail = html[idx + len(marker):]
    m = re.search(r"\n// ═+\n// INIT", tail)
    if not m:
        return html
    return html[: idx + len(marker)] + tail[m.start():]


def bloque_const_mes(nombre, datos, dias, dias_total):
    return (
        f"const {nombre} = {{\n"
        f"  t:{round(datos['total'])},sjp:{round(datos['sjp'])},sjd:{round(datos['sjd'])},"
        f"garp:{round(datos['garp'])},gard:{round(datos['gard'])},alm:{round(datos['alm'])},"
        f"avd:{round(datos['avd'])},\n"
        f"  cavero:{round(datos['cavero'])},ursula:{round(datos['ursula'])},"
        f"dias:{dias},diasT:{dias_total},\n"
        f"  prof:{round(datos['prof'])},pvp:{round(datos['pvp_pin'])},"
        f"inst:{round(datos['pvp_ins'])},ind:{round(datos['ind'])},"
        f"dist:{round(datos['distrib'])}\n"
        f"}};"
    )


def patch_base_d26(html, mes, datos, dias, dias_total):
    nombre = MESES_CONST.get(mes)
    if not nombre:
        return html
    bloque = bloque_const_mes(nombre, datos, dias, dias_total)
    pat = rf"const {nombre} = \{{.*?\}};"
    if re.search(pat, html, flags=re.DOTALL):
        html = re.sub(pat, bloque, html, count=1, flags=re.DOTALL)
    else:
        html = html.replace("const MAY26 = {", bloque + "\n\nconst MAY26 = {", 1)

    fila = f"  {{t:{round(datos['total'])}, ...{nombre}}},"
    fila_pat = rf"  \{{t:\d+, \.\.\.{nombre}\}},"
    if re.search(fila_pat, html):
        html = re.sub(fila_pat, fila, html, count=1)
    else:
        html = re.sub(
            r"(\{t:276749, \.\.\.MAY26\},\s*\n)\s*null,",
            rf"\1{fila}\n",
            html,
            count=1,
        )
    return html


def guardar_html_repo(html, cfg):
    salida = Path(cfg["rutas"]["html_salida"])
    salida.write_text(html, encoding="utf-8")
    for nombre in REPO_HTML:
        Path(nombre).write_text(html, encoding="utf-8")
    logging.info("OK HTML guardado: %s + %s", salida, ", ".join(REPO_HTML))


def actualizar_html(cfg, datos, mes, ano, dias, dias_total):
    plantilla = Path(cfg["rutas"]["html_plantilla"])
    salida    = Path(cfg["rutas"]["html_salida"])

    if not plantilla.exists():
        logging.error(f"No se encuentra la plantilla: {plantilla}")
        return False

    with open(plantilla, encoding="utf-8") as f:
        html = f.read()

    html = limpiar_inyect_previo(html)
    if ano == 2026:
        html = patch_base_d26(html, mes, datos, dias, dias_total)

    mes_js = json.dumps({
        "total":   datos["total"],   "sjp":     datos["sjp"],
        "sjd":     datos["sjd"],     "garp":    datos["garp"],
        "gard":    datos["gard"],    "alm":     datos["alm"],
        "avd":     datos["avd"],     "cavero":  datos["cavero"],
        "ursula":  datos["ursula"],  "prof":    datos["prof"],
        "pvp_pin": datos["pvp_pin"], "pvp_ins": datos["pvp_ins"],
        "distrib": datos["distrib"], "ind":     datos["ind"],
        "dias": dias, "diasT": dias_total, "mes": mes, "ano": ano,
        "diasFromERP": True,
        "actualizado": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "fechaERP": datos.get("fechaERP",
                    datetime.datetime.now().strftime("ERP %d/%m/%y %H:%M")),
        "datosFecha": fecha_datos_excel(datos) or "",
    })

    MARKER = "/* AUTO_DATA_INJECT */"
    ts     = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    inject = f"""
// Datos inyectados automaticamente {ts}
(function autoLoad(){{
  const d = {mes_js};
  if(!window._autoLoaded){{
    window._autoLoaded=true;
    function run(){{
      if(typeof applyAutoERPData==='function'){{
        applyAutoERPData(d);
        console.log('OK Auto-cargado V2:',d.mes+'/'+d.ano,'Total:',d.total);
      }}
    }}
    if(document.readyState==='complete')run();
    else window.addEventListener('load',run);
  }}
}})();
"""
    if MARKER in html:
        html = html.replace(MARKER, MARKER + inject)
    else:
        html = html.replace("</script>\n</body>", inject + "\n</script>\n</body>")

    logging.info("OK Datos inyectados en HTML")

    guardar_html_repo(html, cfg)
    return True

# ─── SUBIR A GITHUB ──────────────────────────────────────────────────────────

def subir_archivo_github(cfg, destino, ruta_html, mensaje):
    gcfg = cfg["github"]
    token = gcfg["token"]
    usuario = gcfg["usuario"]
    repo = gcfg["repositorio"]
    api_url = f"https://api.github.com/repos/{usuario}/{repo}/contents/{destino}"

    with open(ruta_html, "rb") as f:
        contenido_b64 = base64.b64encode(f.read()).decode("utf-8")

    sha = None
    try:
        req = urllib.request.Request(api_url)
        req.add_header("Authorization", f"token {token}")
        req.add_header("User-Agent", "HipopotamoCuadroMando/2.0")
        with urllib.request.urlopen(req, timeout=15) as resp:
            sha = json.loads(resp.read().decode()).get("sha")
    except Exception:
        pass

    payload = {"message": mensaje, "content": contenido_b64}
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        method="PUT",
    )
    req.add_header("Authorization", f"token {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "HipopotamoCuadroMando/2.0")
    with urllib.request.urlopen(req, timeout=30):
        pass
    logging.info("OK Subido: %s", destino)


def subir_a_github(cfg, ruta_html):
    """Sube siempre el HTML recién generado (plantilla V2 + ERP), no archivos viejos del checkout."""
    mensaje = f"Auto {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
    origen = Path(ruta_html)
    if not origen.exists():
        logging.error("No existe HTML generado: %s", origen)
        return False
    html = origen.read_text(encoding="utf-8")
    if "page-ceo" not in html or "applyAutoERPData" not in html:
        logging.error("El HTML generado no es V2 (falta page-ceo / applyAutoERPData). No se sube.")
        return False
    try:
        for nombre in REPO_HTML:
            subir_archivo_github(cfg, nombre, str(origen), mensaje)
        logging.info("OK GitHub Pages (3 HTML, origen unico V2)")
        return True
    except Exception as e:
        logging.warning(f"GitHub error: {e}")
        return False

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    setup_log()
    cfg = cargar_config()
    logging.info("=" * 60)
    logging.info("HIPOPOTAMO PINTURAS — Cuadro de Mando (GitHub Actions)")
    logging.info("=" * 60)

    mes, ano = mes_comercial_actual()
    logging.info(f"Mes comercial inicial: {mes}/{ano}")

    # Descargar Excel
    max_ret  = cfg["opciones"]["reintentos_gmail"]
    mins_ret = cfg["opciones"]["minutos_entre_reintentos"]
    excel_ok = False
    for intento in range(1, max_ret + 2):
        excel_ok = descargar_excel_gmail(cfg, intento)
        if excel_ok:
            break
        if intento <= max_ret:
            logging.warning(f"Reintentando en {mins_ret} min...")
            enviar_telegram(cfg, f"No se encontró el Excel (intento {intento}). Reintentando...")
            time.sleep(mins_ret * 60)

    excel_path = Path(cfg["rutas"]["excel_descargado"])
    if not excel_ok:
        logging.error("No hay Excel. Abortando.")
        enviar_telegram(cfg, "ERROR: No hay Excel disponible. Cuadro NO actualizado.")
        sys.exit(1)

    datos = parsear_excel(excel_path)
    if datos is None:
        logging.error("Error parseando Excel.")
        enviar_telegram(cfg, "ERROR: Falló la lectura del Excel.")
        sys.exit(1)

    # Determinar mes desde fecha del ERP (más fiable que fecha del servidor).
    #
    # Nota: en algunos ERP el campo "Fecha hasta" puede venir en día 26..N
    # aunque el corte real que queremos reflejar sea el comercial (hasta día 25).
    # Para "rescatar" ventas hasta 25/04 inclusive, asignamos el mes por el mes
    # calendario y dejamos que `dias_mes_comercial()` haga el cap al 25.
    fecha_hasta = datos.get("fechaHasta_date") or datos.get("fechaERP_date")
    if fecha_hasta:
        mes, ano = fecha_hasta.month, fecha_hasta.year
        logging.info(f"Mes comercial (desde ERP fecha_hasta={fecha_hasta}): {mes}/{ano}")
    else:
        logging.warning("No se leyó fecha del ERP — usando mes por fecha actual")

    fecha_ref = datos.get("fechaERP_date") or fecha_hasta
    dias, dias_total = dias_mes_comercial(mes, ano, fecha_ref)
    logging.info(f"Días: {dias}/{dias_total} (ref: {fecha_ref})")

    # Generar HTML
    if not actualizar_html(cfg, datos, mes, ano, dias, dias_total):
        logging.error("Error generando HTML.")
        enviar_telegram(cfg, "ERROR: No se pudo generar el HTML.")
        sys.exit(1)

    # Subir a GitHub Pages (cuadro público + plantillas V2)
    subir_a_github(cfg, cfg["rutas"]["html_salida"])

    # Notificar OK
    total_fmt = f"{datos['total']:,.0f}".replace(",", ".")
    enviar_telegram(cfg,
        f"✓ Hipopotamo actualizado — {mes}/{ano}\n"
        f"Total: {total_fmt} € | Días: {dias}/{dias_total}\n"
        f"Cavero (PROF): {datos['cavero']:,.0f} € | Úrsula: {datos['ursula']:,.0f} €"
    )

    logging.info("=" * 60)
    logging.info(f"COMPLETADO {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    logging.info("=" * 60)

if __name__ == "__main__":
    main()
