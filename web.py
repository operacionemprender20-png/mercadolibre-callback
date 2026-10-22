# =========================================================
# TrendVenta - versión web (fase 1)
# Archivo nuevo: web.py (va al lado de app.py)
#
# Pantallas:
#   /web                    Inicio (resumen de la semana)
#   /web/buscar?q=...       ¿Qué quieres vender?
#   /web/explorar           Explorar categorías (con árbol)
#   /web/buscado            Lo más buscado
#   /web/categoria/<id>     Detalle de una categoría
#
# Usa solo datos que ya existen en Neon:
#   indicadores_principiante, categorias, tendencias_categoria,
#   ranking_mas_vendidos
# =========================================================

import os
from datetime import date, datetime

import psycopg2
import psycopg2.extras
from flask import Blueprint, render_template_string, request, redirect, url_for, g
from markupsafe import Markup

web_bp = Blueprint("web", __name__, url_prefix="/web")

NOMBRE_USUARIA = "Sandra"
# Revisa la fecha oficial del Black Friday en Chile y ajústala si cambia
FECHA_BLACK_FRIDAY = date(2026, 11, 27)
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


# ---------------------------------------------------------
# Base de datos
# ---------------------------------------------------------
def _conexion():
    # Una sola conexión por pantalla: se abre en la primera consulta
    # y se reutiliza en las siguientes de la misma visita.
    if "tv_conn" not in g:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        conn.autocommit = True
        g.tv_conn = conn
    return g.tv_conn


@web_bp.teardown_request
def _cerrar_conexion(_error=None):
    conn = g.pop("tv_conn", None)
    if conn is not None:
        conn.close()


def _consultar(sql, params=None):
    with _conexion().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


# Página para UptimeRobot: mantiene Render despierto SIN tocar la base de datos
@web_bp.route("/ping")
def ping():
    return "ok"


SQL_INDICADORES = """
    SELECT v.*, c.ruta_ids, c.es_hoja
    FROM indicadores_principiante v
    JOIN categorias c ON c.id = v.categoria_id
"""


# ---------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------
def _hoy():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Santiago")).date()
    except Exception:
        return date.today()


def _miles(n):
    if n is None:
        return "—"
    return f"{int(n):,}".replace(",", ".")


def _pesos(n):
    return "—" if n is None else "$ " + _miles(n)


def _fecha_corta(d):
    return "—" if not d else f"{d.day} {MESES[d.month - 1]}"


def _preparar(fila):
    f = dict(fila)
    indicadores = [f.get("baja_competencia"), f.get("bajo_catalogo"),
                   f.get("en_crecimiento"), f.get("precio_bajo")]
    f["puntaje"] = sum(1 for x in indicadores if x)
    f["nivel"] = "alto" if f["puntaje"] >= 3 else ("medio" if f["puntaje"] == 2 else "bajo")
    f["publicaciones_txt"] = _miles(f.get("total_publicaciones"))
    if f.get("pct_catalogo") is not None:
        f["pct_catalogo"] = int(f["pct_catalogo"])
    return f


def _ordenar(filas):
    return sorted(filas, key=lambda f: (
        -f["puntaje"],
        f["pct_catalogo"] if f.get("pct_catalogo") is not None else 999,
        f.get("categoria") or "",
    ))


def _veredicto(f):
    if f["puntaje"] >= 3:
        titulo = "Buena para partir."
    elif f["puntaje"] == 2:
        titulo = "Se puede, con cuidado."
    else:
        titulo = "Difícil para partir."

    partes = []
    if f.get("bajo_catalogo"):
        partes.append("Los que más venden son vendedores propios, no fichas de catálogo: puedes entrar con tu propia publicación.")
    elif f.get("pct_catalogo") is not None:
        partes.append("La mayoría de los más vendidos son de catálogo: ahí suele ganar el precio más bajo.")
    if f.get("baja_competencia"):
        partes.append("Hay pocas publicaciones compitiendo.")
    else:
        partes.append("Hay mucha competencia: vas a necesitar buenas fotos y un buen título.")
    if f.get("en_crecimiento"):
        partes.append("Las búsquedas vienen subiendo.")
    return titulo, " ".join(partes)


def _fechas_tendencias(n=4):
    filas = _consultar(
        "SELECT DISTINCT fecha FROM tendencias_categoria ORDER BY fecha DESC LIMIT %s", (n,))
    return [r["fecha"] for r in filas]


def _pagina(titulo, activo, plantilla, **datos):
    contenido = render_template_string(plantilla, **datos)
    return render_template_string(BASE, titulo=titulo, activo=activo, contenido=Markup(contenido))


# ---------------------------------------------------------
# Plantilla base (menú + estilos)
# ---------------------------------------------------------
BASE = """<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ titulo }} · TrendVenta</title>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=Figtree:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--verde:#0B6E4F;--verde-claro:#E3F2EA;--oscuro:#16201B;--fondo:#F5F6F2;--gris:#5B6661;--linea:#E4E7E2;--ambar:#9A4A06;--ambar-claro:#FDF0DC;--azul:#0B5394;--azul-claro:#E3EEFA}
*{box-sizing:border-box}
body{margin:0;background:var(--fondo);color:var(--oscuro);font-family:'Figtree',system-ui,sans-serif}
a{color:var(--verde)}a:hover{color:#08513A}
h1,h2{margin:0}
h1{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:34px;letter-spacing:-.8px;line-height:1.1}
h2{font-size:17px;font-weight:700}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.app{display:flex;flex-wrap:wrap;min-height:100vh}
.side{flex:1 1 220px;background:var(--oscuro);color:#fff;padding:24px 16px;display:flex;flex-direction:column;gap:4px}
.marca{display:flex;align-items:center;gap:10px;padding:0 8px 24px;font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:20px;color:#fff;text-decoration:none}
.logo{width:36px;height:36px;border-radius:10px;background:var(--verde);display:flex;align-items:center;justify-content:center}
.side a.item{color:#C9D2CC;text-decoration:none;padding:11px 12px;border-radius:10px;font-weight:600;font-size:14.5px}
.side a.item:hover{color:#fff}
.side a.item.on{background:#24332B;color:#fff}
.fase{margin-top:18px;padding:0 12px 6px;font-size:11px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:#8C9A92}
.apagado{padding:11px 12px;font-size:14.5px;font-weight:600;color:#8C9A92}
.main{flex:999 1 560px;min-width:0;padding:28px 32px 40px}
.wrap{max-width:1200px;margin:0 auto;display:flex;flex-direction:column;gap:20px}
.sub{font-size:15px;color:var(--gris);margin-top:4px}
.card{background:#fff;border:1px solid var(--linea);border-radius:18px;padding:20px;display:flex;flex-direction:column;gap:12px}
.grid4{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:18px}
.dato{background:#fff;border:1px solid var(--linea);border-radius:16px;padding:16px}
.dato b{display:block;font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:30px}
.dato span{font-size:14px;color:var(--gris)}
.dato.ambar{background:var(--ambar-claro);border-color:#F4DDB8}
.dato.ambar b{color:var(--ambar)}
.buscador{display:flex;flex-wrap:wrap;gap:12px;align-items:center}
.buscador input{flex:1 1 320px;min-width:0;font:inherit;font-size:16px;border:1px solid #D5DAD3;border-radius:12px;padding:13px 16px;background:#fff;color:var(--oscuro)}
.btn{font:inherit;font-size:15px;font-weight:700;border:0;background:var(--verde);color:#fff;border-radius:12px;padding:13px 22px;cursor:pointer;text-decoration:none;display:inline-block}
.btn:hover{background:#08513A;color:#fff}
.btn2{font:inherit;font-size:15px;font-weight:700;border:1.5px solid var(--oscuro);background:#fff;color:var(--oscuro);border-radius:12px;padding:11px 18px;text-decoration:none;display:inline-block}
.pill{font-size:13px;font-weight:600;color:var(--gris);background:#fff;border:1px solid var(--linea);border-radius:999px;padding:8px 14px}
.nota{width:44px;height:44px;border-radius:12px;display:inline-flex;flex-direction:column;align-items:center;justify-content:center;font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:18px;line-height:1;flex-shrink:0}
.nota small{font-family:'Figtree',sans-serif;font-size:9px;font-weight:700}
.nota.grande{width:80px;height:80px;border-radius:18px;font-size:34px}
.nota.grande small{font-size:11px}
.alto{background:var(--verde-claro);color:var(--verde)}
.medio{background:var(--ambar-claro);color:var(--ambar)}
.bajo{background:#EEF0EC;color:var(--gris)}
.destacada{background:var(--oscuro);color:#fff;border-radius:20px;padding:26px 28px;display:flex;flex-wrap:wrap;gap:24px;align-items:center}
.destacada .etiqueta{font-size:12px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:#9FE0C4}
.destacada .nombre{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:34px;line-height:1.05}
.destacada p{margin:0;font-size:15px;line-height:1.5;color:#E2E8E4;max-width:600px}
.destacada .nota{background:#9FE0C4;color:#0B3D2C}
.blanco{background:#fff;color:var(--oscuro);font-weight:700;font-size:15px;border-radius:12px;padding:14px 22px;text-decoration:none}
.fila{display:flex;align-items:center;gap:14px;padding:12px 0;border-bottom:1px solid #EEF0EC;text-decoration:none;color:var(--oscuro)}
.fila:last-child{border-bottom:0}
.fila .t{font-weight:700}
.fila .m{font-size:13px;color:var(--gris)}
.nueva{font-size:12px;font-weight:700;color:var(--azul);background:var(--azul-claro);border-radius:6px;padding:3px 9px;white-space:nowrap}
.cabecera{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{font:inherit;font-size:14px;font-weight:600;border:1px solid #D5DAD3;background:#fff;color:var(--oscuro);border-radius:999px;padding:9px 16px;cursor:pointer}
.chip.on{background:var(--oscuro);color:#fff;border-color:var(--oscuro)}
.arbol{background:#fff;border:1px solid var(--linea);border-radius:16px;padding:16px 18px;display:flex;flex-direction:column;gap:12px}
.niveles{display:flex;flex-wrap:wrap;gap:12px}
.niveles div{display:flex;flex-direction:column;gap:4px;flex:1 1 200px}
.niveles label{font-size:12px;font-weight:700;color:var(--gris)}
.niveles select{font:inherit;font-size:14px;font-weight:600;border:1px solid #D5DAD3;background:#fff;color:var(--oscuro);border-radius:10px;padding:10px 12px}
.tabla{background:#fff;border:1px solid var(--linea);border-radius:18px;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:14px;min-width:820px}
th{text-align:left;font-size:12px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--gris);padding:12px 14px;background:#FAFBF8;border-bottom:1px solid var(--linea)}
td{padding:13px 14px;border-bottom:1px solid #EEF0EC;vertical-align:middle}
tr:last-child td{border-bottom:0}
.c{text-align:center}
.si{color:var(--verde);font-weight:800;font-size:16px}
.no{color:#A3ABA6;font-weight:700;font-size:16px}
.nd{color:#A3ABA6;font-size:13px}
.leyenda{font-size:13px;color:var(--gris)}
.veredicto{border-radius:14px;padding:14px 18px;font-size:16px;line-height:1.5}
.veredicto.alto{color:#0B3D2C}
.veredicto.medio{color:#6B3304}
.veredicto.bajo{color:var(--oscuro)}
.ind{display:flex;gap:12px;align-items:flex-start;font-size:14.5px;line-height:1.4}
.ind .ico{width:24px;height:24px;border-radius:50%;font-size:13px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.ind .ico.ok{background:var(--verde-claro);color:var(--verde)}
.ind .ico.mal{background:#EEF0EC;color:var(--gris)}
.ind .ico.nd{background:#fff;border:1px dashed #C9CFC8;color:#A3ABA6}
.ind span{color:var(--gris)}
.barras{display:flex;align-items:flex-end;gap:16px;height:160px;padding:0 8px}
.barras div{flex:1;display:flex;flex-direction:column;align-items:center;gap:6px}
.barras i{display:block;width:100%;background:#B9DECB;border-radius:8px 8px 0 0}
.barras div:last-child i{background:var(--verde)}
.barras small{font-size:12px;color:var(--gris)}
.pal{font-size:14px;font-weight:600;background:var(--fondo);border:1px solid var(--linea);border-radius:999px;padding:7px 14px;text-decoration:none;color:var(--oscuro)}
.panel{background:#fff;border:1px solid var(--linea);border-radius:18px;overflow:hidden}
.panel .cab{display:flex;justify-content:space-between;align-items:center;padding:16px 18px;border-bottom:1px solid var(--linea)}
.panel .fila{padding:11px 18px}
.vacio{text-align:center;color:var(--gris);padding:28px;background:#fff;border:1px dashed var(--linea);border-radius:18px}
@media (max-width:640px){.main{padding:20px 16px 32px}h1{font-size:28px}}
</style>
</head><body>
<div class="app">
  <nav class="side" aria-label="Menú principal">
    <a class="marca" href="{{ url_for('web.inicio') }}">
      <span class="logo"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 17 9 11 13 15 21 7"/><polyline points="15 7 21 7 21 13"/></svg></span>
      TrendVenta
    </a>
    <a class="item {{ 'on' if activo == 'inicio' }}" href="{{ url_for('web.inicio') }}">Inicio</a>
    <a class="item {{ 'on' if activo == 'buscar' }}" href="{{ url_for('web.buscar') }}">¿Qué quieres vender?</a>
    <a class="item {{ 'on' if activo == 'explorar' }}" href="{{ url_for('web.explorar') }}">Explorar categorías</a>
    <a class="item {{ 'on' if activo == 'buscado' }}" href="{{ url_for('web.buscado') }}">Lo más buscado</a>
    <div class="fase">Fase 2</div>
    <div class="apagado">Mis nichos</div>
    <div class="apagado">Temporadas</div>
  </nav>
  <main class="main"><div class="wrap">{{ contenido }}</div></main>
</div>
</body></html>"""


# ---------------------------------------------------------
# 1. Inicio
# ---------------------------------------------------------
PLANTILLA_INICIO = """
<form class="buscador" action="{{ url_for('web.buscar') }}" method="get">
  <label for="q" class="sr">Buscar producto</label>
  <input id="q" name="q" placeholder="¿Qué quieres vender? Escribe un producto">
  <button class="btn" type="submit">Analizar</button>
  {% if actualizado %}<span class="pill">Actualizado {{ actualizado }}</span>{% endif %}
</form>

<div>
  <div class="sub">Hola, {{ nombre }}</div>
  <h1>Resumen de la semana</h1>
</div>

<div class="grid4">
  <div class="dato"><b>{{ total }}</b><span>categorías analizadas</span></div>
  <div class="dato"><b style="color:#0B6E4F">{{ oportunidades }}</b><span>buenas oportunidades</span></div>
  <div class="dato"><b>{{ n_busquedas }}</b><span>búsquedas en tendencia</span></div>
  {% if semanas_bf is not none %}
  <div class="dato ambar"><b>{{ semanas_bf }} sem.</b><span>para Black Friday</span></div>
  {% endif %}
</div>

{% if mejor %}
<div class="destacada">
  <div style="flex:1 1 380px;display:flex;flex-direction:column;gap:10px">
    <div class="etiqueta">Mejor oportunidad de la semana</div>
    <div class="nombre">{{ mejor.categoria }}</div>
    <p>{{ mejor_texto }}</p>
  </div>
  <div style="display:flex;align-items:center;gap:18px">
    <div class="nota grande">{{ mejor.puntaje }}<small>de 4</small></div>
    <a class="blanco" href="{{ url_for('web.categoria', categoria_id=mejor.categoria_id) }}">Ver análisis</a>
  </div>
</div>
{% endif %}

<div class="grid2">
  <div class="card">
    <div class="cabecera"><h2>Mejores categorías para partir</h2><a href="{{ url_for('web.explorar') }}" style="font-size:14px;font-weight:600">Ver las {{ total }}</a></div>
    <div>
    {% for f in top %}
      <a class="fila" href="{{ url_for('web.categoria', categoria_id=f.categoria_id) }}">
        <span class="nota {{ f.nivel }}">{{ f.puntaje }}<small>de 4</small></span>
        <span style="flex:1"><span class="t" style="display:block">{{ f.categoria }}</span>
        <span class="m">{{ f.publicaciones_txt }} publicaciones{% if f.pct_catalogo is not none %} · {{ f.pct_catalogo }}% catálogo{% endif %}</span></span>
      </a>
    {% else %}
      <div class="m">Todavía no hay datos.</div>
    {% endfor %}
    </div>
  </div>

  <div class="card">
    <div class="cabecera"><h2>Búsquedas nuevas esta semana</h2><a href="{{ url_for('web.buscado') }}" style="font-size:14px;font-weight:600">Ver ranking</a></div>
    <div>
    {% for b in nuevas %}
      <a class="fila" href="{{ url_for('web.buscar', q=b.keyword) }}">
        <span style="flex:1"><span class="t" style="display:block;font-weight:600">{{ b.keyword }}</span><span class="m">{{ b.categoria or 'Sin categoría' }}</span></span>
        <span class="nueva">Nueva</span>
      </a>
    {% else %}
      <div class="m">Se verán aquí cuando haya al menos dos semanas para comparar.</div>
    {% endfor %}
    </div>
  </div>
</div>
"""


@web_bp.route("/")
def inicio():
    filas = _ordenar([_preparar(f) for f in _consultar(SQL_INDICADORES)])
    fechas = _fechas_tendencias(2)

    n_busquedas = 0
    nuevas = []
    if fechas:
        n_busquedas = _consultar(
            "SELECT COUNT(DISTINCT keyword) AS n FROM tendencias_categoria WHERE fecha = %s",
            (fechas[0],))[0]["n"]
    if len(fechas) == 2:
        nuevas = _consultar("""
            SELECT keyword, MAX(category_name) AS categoria
            FROM tendencias_categoria
            WHERE fecha = %s
              AND keyword NOT IN (SELECT keyword FROM tendencias_categoria WHERE fecha = %s)
            GROUP BY keyword
            ORDER BY keyword
            LIMIT 5
        """, (fechas[0], fechas[1]))

    dias_bf = (FECHA_BLACK_FRIDAY - _hoy()).days
    semanas_bf = dias_bf // 7 if dias_bf >= 0 else None

    mejor = filas[0] if filas else None
    mejor_texto = _veredicto(mejor)[1] if mejor else ""

    return _pagina(
        "Inicio", "inicio", PLANTILLA_INICIO,
        nombre=NOMBRE_USUARIA,
        actualizado=_fecha_corta(filas[0]["fecha"]) if filas else None,
        total=len(filas),
        oportunidades=sum(1 for f in filas if f["puntaje"] >= 3),
        n_busquedas=n_busquedas,
        semanas_bf=semanas_bf,
        mejor=mejor, mejor_texto=mejor_texto,
        top=filas[:4],
        nuevas=nuevas,
    )


# ---------------------------------------------------------
# 2. ¿Qué quieres vender?
# ---------------------------------------------------------
PLANTILLA_BUSCAR = """
<form style="display:flex;flex-direction:column;gap:10px" action="{{ url_for('web.buscar') }}" method="get">
  <label for="q"><h1>¿Qué quieres vender?</h1></label>
  <div class="buscador">
    <input id="q" name="q" value="{{ q }}" placeholder="Por ejemplo: pinzas de pelo" style="border:2px solid #0B6E4F">
    <button class="btn" type="submit">Analizar</button>
  </div>
  <div class="leyenda">Escríbelo como lo buscaría un cliente. No necesitas saber en qué categoría está.</div>
</form>

{% if q and f %}
<div class="card" style="flex-direction:row;flex-wrap:wrap;gap:24px;align-items:center;padding:24px">
  <div style="flex:1 1 420px;display:flex;flex-direction:column;gap:8px">
    <div style="font-size:12px;font-weight:700;letter-spacing:.7px;text-transform:uppercase;color:#5B6661">Lo encontramos en</div>
    <div style="font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:30px;line-height:1.05">{{ f.categoria }}</div>
    {% if f.ruta_nombres %}<div class="leyenda">{{ f.ruta_nombres }}</div>{% endif %}
    <div class="veredicto {{ f.nivel }}" style="margin-top:6px"><b>{{ veredicto[0] }}</b> {{ veredicto[1] }}</div>
  </div>
  <div style="display:flex;flex-direction:column;align-items:center;gap:12px">
    <div class="nota grande {{ f.nivel }}">{{ f.puntaje }}<small>de 4</small></div>
    <a href="{{ url_for('web.categoria', categoria_id=f.categoria_id) }}" style="font-size:14px;font-weight:700">Ver análisis completo</a>
  </div>
</div>

<div class="grid4">
  <div class="dato"><b>{{ f.publicaciones_txt }}</b><span>publicaciones</span></div>
  <div class="dato"><b>{{ f.pct_catalogo if f.pct_catalogo is not none else '—' }}{% if f.pct_catalogo is not none %}%{% endif %}</b><span>de los más vendidos son de catálogo</span></div>
  <div class="dato"><b>{{ f.apariciones_tendencias or 0 }}</b><span>búsquedas en tendencia esta semana</span></div>
  <div class="dato"><b>{{ precio }}</b><span>precio más común</span></div>
</div>

<div class="grid2">
  <div class="card">
    <h2>Búsquedas parecidas</h2>
    <div class="leyenda">Otras formas en que la gente busca en esta categoría. Úsalas en el título de tu publicación.</div>
    <div class="chips">
    {% for p in parecidas %}<a class="pal" href="{{ url_for('web.buscar', q=p.keyword) }}">{{ p.keyword }}</a>{% else %}<span class="leyenda">Todavía no hay búsquedas guardadas para esta categoría.</span>{% endfor %}
    </div>
  </div>
  <div class="card">
    <h2>¿No era esta?</h2>
    {% if otras %}
      <div class="leyenda">También podría estar en:</div>
      <div class="chips">{% for o in otras %}<a class="pal" href="{{ url_for('web.categoria', categoria_id=o.categoria_id) }}">{{ o.categoria }}</a>{% endfor %}</div>
    {% endif %}
    <div class="leyenda">¿Prefieres ver opciones en vez de buscar?</div>
    <a class="btn2" href="{{ url_for('web.explorar') }}" style="align-self:flex-start">Explorar categorías</a>
  </div>
</div>

{% elif q %}
<div class="vacio">
  <p style="margin:0 0 6px;font-weight:700;color:#16201B">Todavía no tenemos datos de "{{ q }}".</p>
  <p style="margin:0 0 14px">TrendVenta suma categorías nuevas cada semana. Prueba con otra palabra o explora las que ya tenemos.</p>
  <a class="btn2" href="{{ url_for('web.explorar') }}">Explorar categorías</a>
</div>
{% endif %}
"""


def _buscar_categorias(texto):
    patron = f"%{texto}%"
    ids = []
    for r in _consultar(
            "SELECT categoria_id FROM indicadores_principiante WHERE categoria ILIKE %s", (patron,)):
        ids.append(r["categoria_id"])
    for r in _consultar("""
            SELECT category_id, COUNT(*) AS n FROM tendencias_categoria
            WHERE keyword ILIKE %s AND category_id IS NOT NULL
            GROUP BY category_id ORDER BY n DESC LIMIT 10
        """, (patron,)):
        if r["category_id"] not in ids:
            ids.append(r["category_id"])
    return ids


@web_bp.route("/buscar")
def buscar():
    q = (request.args.get("q") or "").strip()
    datos = dict(q=q, f=None, veredicto=None, precio="—", parecidas=[], otras=[])

    if q:
        ids = _buscar_categorias(q)
        if not ids:
            # Segundo intento: palabra por palabra
            for palabra in q.split():
                if len(palabra) > 3:
                    ids += [i for i in _buscar_categorias(palabra) if i not in ids]

        filas = {}
        if ids:
            for r in _consultar(SQL_INDICADORES + " WHERE v.categoria_id = ANY(%s)", (ids,)):
                filas[r["categoria_id"]] = _preparar(r)
        encontradas = [filas[i] for i in ids if i in filas]

        if encontradas:
            f = encontradas[0]
            datos["f"] = f
            datos["veredicto"] = _veredicto(f)
            datos["precio"] = _pesos(f.get("precio_mediana"))
            datos["otras"] = encontradas[1:5]
            datos["parecidas"] = _consultar("""
                SELECT keyword, COUNT(DISTINCT fecha) AS semanas
                FROM tendencias_categoria WHERE category_id = %s
                GROUP BY keyword ORDER BY semanas DESC, keyword LIMIT 8
            """, (f["categoria_id"],))

    return _pagina("¿Qué quieres vender?", "buscar", PLANTILLA_BUSCAR, **datos)


# ---------------------------------------------------------
# 3. Explorar categorías
# ---------------------------------------------------------
PLANTILLA_EXPLORAR = """
{% macro ind(v) -%}
{% if v %}<span class="si">✓</span>{% elif v is none %}<span class="nd">sin dato</span>{% else %}<span class="no">✕</span>{% endif %}
{%- endmacro %}

<div>
  <h1>Explorar categorías</h1>
  <div class="sub">{{ filas|length }} categorías, de la mejor a la peor para alguien que recién parte</div>
</div>

<div class="arbol">
  <div class="cabecera" style="font-size:14px;flex-wrap:wrap">
    <div><span style="color:#5B6661">Estás en:</span>
      <a href="{{ url_for('web.explorar') }}" style="font-weight:600">Todas</a>
      {% for p in camino %} › {% if loop.last %}<b>{{ p.nombre }}</b>{% else %}<a href="{{ url_for('web.explorar', cat=p.id) }}" style="font-weight:600">{{ p.nombre }}</a>{% endif %}{% endfor %}
    </div>
    {% if camino %}<a href="{{ url_for('web.explorar') }}" style="font-weight:600">Volver a todas</a>{% endif %}
  </div>
  <div class="niveles">
    {% for nivel in niveles %}
    <div>
      <label for="nivel{{ loop.index }}">{{ nombres_nivel[loop.index0] if loop.index0 < nombres_nivel|length else 'Nivel ' ~ loop.index }}</label>
      <select id="nivel{{ loop.index }}" onchange="location = this.value ? '?cat=' + encodeURIComponent(this.value) : '?'">
        <option value="{{ nivel.todas }}">Todas</option>
        {% for o in nivel.opciones %}<option value="{{ o.id }}" {{ 'selected' if o.id == nivel.elegido }}>{{ o.nombre }}</option>{% endfor %}
      </select>
    </div>
    {% endfor %}
  </div>
  <div class="leyenda">Baja por el árbol hasta el tipo de producto. Ahí los datos son más precisos.</div>
</div>

<div class="chips" role="group" aria-label="Filtros">
  <button class="chip on" data-f="todas">Todas</button>
  <button class="chip" data-f="mejores">Solo las mejores (3 o 4)</button>
  <button class="chip" data-f="bc">Poca competencia</button>
  <button class="chip" data-f="bcat">Poco catálogo</button>
  <button class="chip" data-f="crec">En tendencia</button>
  <button class="chip" data-f="prec">Precio accesible</button>
</div>

{% if filas %}
<div class="tabla">
  <table>
    <thead><tr>
      <th>Categoría</th><th class="c">Nota</th><th>Publicaciones</th><th>% catálogo</th>
      <th class="c">Poca competencia</th><th class="c">Poco catálogo</th><th class="c">En tendencia</th><th class="c">Precio accesible</th>
    </tr></thead>
    <tbody>
    {% for f in filas %}
      <tr data-puntaje="{{ f.puntaje }}" data-bc="{{ f.baja_competencia }}" data-bcat="{{ f.bajo_catalogo }}" data-crec="{{ f.en_crecimiento }}" data-prec="{{ f.precio_bajo }}">
        <td><a href="{{ url_for('web.categoria', categoria_id=f.categoria_id) }}" style="font-weight:700">{{ f.categoria }}</a>
          {% if f.ruta_nombres and f.ruta_nombres != f.categoria %}<div style="font-size:12.5px;color:#5B6661">{{ f.ruta_nombres }}</div>{% endif %}</td>
        <td class="c"><span class="nota {{ f.nivel }}" style="width:40px;height:30px;border-radius:9px;font-size:16px">{{ f.puntaje }}</span></td>
        <td>{{ f.publicaciones_txt }}</td>
        <td>{{ f.pct_catalogo ~ '%' if f.pct_catalogo is not none else '—' }}</td>
        <td class="c">{{ ind(f.baja_competencia) }}</td>
        <td class="c">{{ ind(f.bajo_catalogo) }}</td>
        <td class="c">{{ ind(f.en_crecimiento) }}</td>
        <td class="c">{{ ind(f.precio_bajo) }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
<div class="vacio" id="vacio" hidden>No hay categorías con ese filtro.</div>
{% else %}
<div class="vacio">Todavía no tenemos datos de esta categoría. TrendVenta suma categorías nuevas cada semana.</div>
{% endif %}

<div class="leyenda">✓ cumple · ✕ no cumple · sin dato = todavía no hay información</div>

<script>
document.querySelectorAll('.chip').forEach(function (b) {
  b.addEventListener('click', function () {
    document.querySelectorAll('.chip').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    var f = b.dataset.f, n = 0;
    document.querySelectorAll('tbody tr').forEach(function (tr) {
      var ok = f === 'todas' || (f === 'mejores' ? +tr.dataset.puntaje >= 3 : tr.dataset[f] === 'True');
      tr.hidden = !ok;
      if (ok) n++;
    });
    var v = document.getElementById('vacio');
    if (v) v.hidden = n > 0;
  });
});
</script>
"""


def _hijos(padre_id):
    if padre_id is None:
        return _consultar("SELECT id, nombre FROM categorias WHERE padre_id IS NULL ORDER BY nombre")
    return _consultar("SELECT id, nombre FROM categorias WHERE padre_id = %s ORDER BY nombre", (padre_id,))


@web_bp.route("/explorar")
def explorar():
    cat = (request.args.get("cat") or "").strip()

    camino_ids = []
    if cat:
        r = _consultar("SELECT id, ruta_ids FROM categorias WHERE id = %s", (cat,))
        if r:
            camino_ids = list(r[0]["ruta_ids"] or [])
            if not camino_ids or camino_ids[-1] != cat:
                camino_ids.append(cat)
        else:
            cat = ""

    # Nombres para "Estás en: Todas › ..."
    camino = []
    if camino_ids:
        nombres = {x["id"]: x["nombre"] for x in _consultar(
            "SELECT id, nombre FROM categorias WHERE id = ANY(%s)", (camino_ids,))}
        camino = [{"id": i, "nombre": nombres.get(i, i)} for i in camino_ids]

    # Un desplegable por nivel del árbol
    niveles = [{"opciones": _hijos(None), "elegido": camino_ids[0] if camino_ids else "", "todas": ""}]
    for i, cid in enumerate(camino_ids):
        hijos = _hijos(cid)
        if not hijos:
            break
        niveles.append({
            "opciones": hijos,
            "elegido": camino_ids[i + 1] if i + 1 < len(camino_ids) else "",
            "todas": cid,
        })

    filas = [_preparar(f) for f in _consultar(SQL_INDICADORES)]
    if cat:
        filas = [f for f in filas if f["categoria_id"] == cat or cat in (f.get("ruta_ids") or [])]

    return _pagina(
        "Explorar categorías", "explorar", PLANTILLA_EXPLORAR,
        filas=_ordenar(filas), camino=camino, niveles=niveles,
        nombres_nivel=["Categoría", "Subcategoría", "Tipo de producto"],
    )


# ---------------------------------------------------------
# 4. Lo más buscado
# ---------------------------------------------------------
PLANTILLA_BUSCADO = """
<div>
  <h1>Lo más buscado</h1>
  <div class="sub">Lo que la gente escribe cuando quiere comprar</div>
</div>

{% if not fechas %}
<div class="vacio">Todavía no hay búsquedas guardadas.</div>
{% else %}
<div class="grid2">
  <div class="panel">
    <div class="cab"><h2>Esta semana</h2><span class="leyenda">{{ fecha_txt }}</span></div>
    {% for b in esta %}
      <a class="fila" href="{{ url_for('web.buscar', q=b.keyword) }}">
        <span style="flex:1"><span style="display:block;font-weight:600">{{ b.keyword }}</span><span class="m">{{ b.categoria or 'Sin categoría' }}</span></span>
        {% if b.nueva %}<span class="nueva">Nueva</span>{% endif %}
      </a>
    {% endfor %}
  </div>

  <div class="panel">
    <div class="cab"><h2>Últimas {{ fechas|length }} semanas</h2><span class="leyenda">Semanas en tendencia</span></div>
    {% for b in constantes %}
      <a class="fila" href="{{ url_for('web.buscar', q=b.keyword) }}">
        <span style="flex:1"><span style="display:block;font-weight:600">{{ b.keyword }}</span><span class="m">{{ b.categoria or 'Sin categoría' }}</span></span>
        <span style="display:flex;gap:4px" aria-label="{{ b.semanas }} de {{ fechas|length }} semanas">
          {% for s in b.marcas %}<i style="display:block;width:10px;height:22px;border-radius:3px;background:{{ '#0B6E4F' if s else '#E4E7E2' }}"></i>{% endfor %}
        </span>
      </a>
    {% endfor %}
  </div>
</div>

{% if salieron %}
<div class="card">
  <h2>Dejaron de aparecer esta semana</h2>
  <div class="chips">{% for b in salieron %}<span class="pal">{{ b.keyword }}</span>{% endfor %}</div>
</div>
{% endif %}

<div class="leyenda">Cada barrita es una semana, de la más antigua a la más reciente. Una búsqueda que aparece todas las semanas es demanda estable, no una moda pasajera.</div>
{% endif %}
"""


@web_bp.route("/buscado")
def buscado():
    fechas = _fechas_tendencias(4)
    datos = dict(fechas=fechas, esta=[], constantes=[], salieron=[], fecha_txt="")

    if fechas:
        filas = _consultar("""
            SELECT keyword, MAX(category_name) AS categoria,
                   ARRAY_AGG(DISTINCT fecha) AS vistas
            FROM tendencias_categoria
            WHERE fecha = ANY(%s)
            GROUP BY keyword
        """, (fechas,))

        orden = list(reversed(fechas))  # de la más antigua a la más reciente
        for b in filas:
            vistas = set(b["vistas"] or [])
            b["marcas"] = [d in vistas for d in orden]
            b["semanas"] = len(vistas)
            b["en_esta"] = fechas[0] in vistas
            b["en_anterior"] = len(fechas) > 1 and fechas[1] in vistas
            b["nueva"] = b["en_esta"] and len(fechas) > 1 and b["semanas"] == 1

        datos["fecha_txt"] = _fecha_corta(fechas[0])
        datos["esta"] = sorted([b for b in filas if b["en_esta"]],
                               key=lambda b: (-b["semanas"], b["keyword"]))
        datos["constantes"] = sorted(filas,
                                     key=lambda b: (-b["semanas"], not b["en_esta"], b["keyword"]))[:15]
        datos["salieron"] = sorted([b for b in filas if b["en_anterior"] and not b["en_esta"]],
                                   key=lambda b: b["keyword"])

    return _pagina("Lo más buscado", "buscado", PLANTILLA_BUSCADO, **datos)


# ---------------------------------------------------------
# 5. Detalle de categoría
# ---------------------------------------------------------
PLANTILLA_CATEGORIA = """
<a href="{{ url_for('web.explorar') }}" style="align-self:flex-start;font-size:14px;font-weight:600;text-decoration:none;color:#5B6661">← Volver a categorías</a>

{% if not f %}
<div class="vacio">Todavía no tenemos datos de esta categoría. TrendVenta suma categorías nuevas cada semana.</div>
{% else %}
<div class="cabecera" style="flex-wrap:wrap;align-items:center">
  <div>
    {% if f.ruta_nombres and f.ruta_nombres != f.categoria %}<div class="leyenda">{{ f.ruta_nombres }}</div>{% endif %}
    <h1 style="font-size:40px">{{ f.categoria }}</h1>
  </div>
  <div class="nota grande {{ f.nivel }}">{{ f.puntaje }}<small>de 4</small></div>
</div>

<div class="veredicto {{ f.nivel }}"><b>{{ veredicto[0] }}</b> {{ veredicto[1] }}</div>

<div class="grid2">
  <div class="card">
    <h2>Por qué tiene esta nota</h2>
    {% for i in indicadores %}
    <div class="ind">
      <div class="ico {{ 'ok' if i.valor else ('nd' if i.valor is none else 'mal') }}">{{ '✓' if i.valor else ('·' if i.valor is none else '✕') }}</div>
      <div><b>{{ i.titulo }}</b><br><span>{{ i.texto }}</span></div>
    </div>
    {% endfor %}
  </div>

  <div class="card">
    <h2>Búsquedas en tendencia, semana a semana</h2>
    <div class="barras">
      {% for s in semanas %}
      <div><b style="font-size:13px">{{ s.n }}</b><i style="height:{{ s.alto }}px"></i><small>{{ s.etiqueta }}</small></div>
      {% endfor %}
    </div>
  </div>

  <div class="card">
    <h2>Quién vende más</h2>
    {% if ranking_total %}
      <div style="font-size:15px;line-height:1.5">De los <b>{{ ranking_total }}</b> productos más vendidos:</div>
      <div class="grid4" style="grid-template-columns:repeat(2,minmax(0,1fr))">
        <div class="dato"><b style="color:#0B6E4F">{{ propios }}</b><span>vendedores con publicación propia</span></div>
        <div class="dato"><b>{{ catalogo }}</b><span>fichas de catálogo</span></div>
      </div>
    {% else %}
      <div class="leyenda">Todavía no tenemos el ranking de más vendidos de esta categoría.</div>
    {% endif %}
  </div>

  <div class="card">
    <h2>Lo que la gente escribe</h2>
    <div class="chips">
      {% for p in palabras %}<a class="pal" href="{{ url_for('web.buscar', q=p.keyword) }}">{{ p.keyword }}</a>{% else %}<span class="leyenda">Todavía no hay búsquedas guardadas para esta categoría.</span>{% endfor %}
    </div>
    <div style="border-top:1px solid #EEF0EC;padding-top:12px;display:flex;justify-content:space-between;font-size:14px">
      <span>Precio más común</span><b>{{ precio }}</b>
    </div>
  </div>
</div>
{% endif %}
"""


@web_bp.route("/categoria/<categoria_id>")
def categoria(categoria_id):
    r = _consultar(SQL_INDICADORES + " WHERE v.categoria_id = %s", (categoria_id,))
    if not r:
        return _pagina("Categoría", "explorar", PLANTILLA_CATEGORIA, f=None)

    f = _preparar(r[0])
    pct = f.get("pct_catalogo")

    indicadores = [
        {"valor": f.get("baja_competencia"), "titulo": "Poca competencia",
         "texto": f"{f['publicaciones_txt']} publicaciones compitiendo."},
        {"valor": f.get("bajo_catalogo"), "titulo": "Poco catálogo",
         "texto": (f"{pct}% de los más vendidos son fichas de catálogo." if pct is not None
                   else "Todavía no tenemos el ranking de esta categoría.")},
        {"valor": f.get("en_crecimiento"), "titulo": "En tendencia",
         "texto": f"{f.get('apariciones_tendencias') or 0} búsquedas en tendencia esta semana."},
        {"valor": f.get("precio_bajo"), "titulo": "Precio accesible",
         "texto": ("Precio más común: " + _pesos(f.get("precio_mediana"))) if f.get("precio_mediana") is not None
                  else "Los precios los agregamos pronto."},
    ]

    # Búsquedas por semana (últimas 4 fotos de tendencias)
    fechas = list(reversed(_fechas_tendencias(4)))
    conteo = {x["fecha"]: x["n"] for x in _consultar("""
        SELECT fecha, COUNT(DISTINCT keyword) AS n FROM tendencias_categoria
        WHERE category_id = %s AND fecha = ANY(%s) GROUP BY fecha
    """, (categoria_id, fechas))} if fechas else {}
    maximo = max(conteo.values()) if conteo else 1
    semanas = [{"n": conteo.get(d, 0),
                "alto": 8 + int(110 * conteo.get(d, 0) / maximo),
                "etiqueta": _fecha_corta(d)} for d in fechas]

    # Quién vende más (última carga de ranking de esta categoría)
    tipos = {x["entidad_tipo"]: x["n"] for x in _consultar("""
        SELECT UPPER(entidad_tipo) AS entidad_tipo, COUNT(*) AS n FROM ranking_mas_vendidos
        WHERE category_id = %s
          AND fecha >= (SELECT MAX(fecha) FROM ranking_mas_vendidos WHERE category_id = %s) - 6
        GROUP BY UPPER(entidad_tipo)
    """, (categoria_id, categoria_id))}
    catalogo = tipos.get("PRODUCT", 0)
    ranking_total = sum(tipos.values())

    palabras = _consultar("""
        SELECT keyword, COUNT(DISTINCT fecha) AS semanas FROM tendencias_categoria
        WHERE category_id = %s GROUP BY keyword ORDER BY semanas DESC, keyword LIMIT 12
    """, (categoria_id,))

    return _pagina(
        f["categoria"], "explorar", PLANTILLA_CATEGORIA,
        f=f, veredicto=_veredicto(f), indicadores=indicadores, semanas=semanas,
        ranking_total=ranking_total, catalogo=catalogo, propios=ranking_total - catalogo,
        palabras=palabras, precio=_pesos(f.get("precio_mediana")),
    )
