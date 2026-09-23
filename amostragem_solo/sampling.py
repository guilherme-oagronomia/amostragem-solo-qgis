"""Geração dos planos de amostragem (lógica geométrica, sem interface)."""

import math

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant

METODO_CELULA = "celula"
METODO_GRADE = "grade"
METODO_HEXAGONO = "hexagono"

NOMES_METODO = {
    METODO_CELULA: "Célula",
    METODO_GRADE: "Grade normal",
    METODO_HEXAGONO: "Hexágono",
}

# Fragmentos de borda menores que esta fração da célula são unidos à vizinha
FRACAO_MIN_FRAGMENTO = 0.5


class ErroAmostragem(Exception):
    pass


# ---------------------------------------------------------------------------
# Preparação do perímetro
# ---------------------------------------------------------------------------

def crs_utm_para(geom_wgs84):
    """Retorna o CRS UTM (WGS 84) adequado ao centroide da geometria em graus."""
    c = geom_wgs84.centroid().asPoint()
    zona = int(math.floor((c.x() + 180.0) / 6.0)) + 1
    zona = min(max(zona, 1), 60)
    epsg = (32700 if c.y() < 0 else 32600) + zona
    return QgsCoordinateReferenceSystem("EPSG:%d" % epsg)


def preparar_perimetro(layer, somente_selecionadas=False):
    """Une as feições do perímetro e devolve (geometria_métrica, crs_métrico)."""
    feats = layer.selectedFeatures() if somente_selecionadas else list(layer.getFeatures())
    geoms = [f.geometry() for f in feats if f.hasGeometry() and not f.geometry().isEmpty()]
    if not geoms:
        raise ErroAmostragem("A camada de perímetro não possui feições com geometria.")

    geom = QgsGeometry.unaryUnion(geoms)
    if geom is None or geom.isEmpty():
        raise ErroAmostragem("Não foi possível unir as geometrias do perímetro.")
    geom = geom.makeValid()

    src_crs = layer.crs()
    if not src_crs.isValid():
        raise ErroAmostragem("A camada de perímetro não possui sistema de coordenadas definido.")

    if src_crs.isGeographic():
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        g84 = QgsGeometry(geom)
        g84.transform(QgsCoordinateTransform(src_crs, wgs84, QgsProject.instance()))
        dst_crs = crs_utm_para(g84)
        geom.transform(QgsCoordinateTransform(src_crs, dst_crs, QgsProject.instance()))
    else:
        dst_crs = src_crs

    geom = geom.makeValid()
    if geom.area() <= 0:
        raise ErroAmostragem("O perímetro possui área nula.")
    return geom, dst_crs


# ---------------------------------------------------------------------------
# Geradores de grade
# ---------------------------------------------------------------------------

def _grade_centralizada(ext, passo_x, passo_y):
    """Número de colunas/linhas e origem que centralizam a grade na extensão."""
    nx = max(1, int(math.ceil(ext.width() / passo_x)))
    ny = max(1, int(math.ceil(ext.height() / passo_y)))
    cx, cy = ext.center().x(), ext.center().y()
    x0 = cx - nx * passo_x / 2.0
    y_topo = cy + ny * passo_y / 2.0
    return nx, ny, x0, y_topo


def celulas_quadradas(area, lado):
    ext = area.boundingBox()
    nx, ny, x0, y_topo = _grade_centralizada(ext, lado, lado)
    celulas = []
    for lin in range(ny):
        y1 = y_topo - lin * lado
        for col in range(nx):
            x1 = x0 + col * lado
            celulas.append(QgsGeometry.fromRect(QgsRectangle(x1, y1 - lado, x1 + lado, y1)))
    return celulas


def celulas_hexagonais(area, area_celula):
    """Hexágonos 'pointy-top' com área igual a area_celula."""
    s = math.sqrt(2.0 * area_celula / (3.0 * math.sqrt(3.0)))  # lado / raio
    w = math.sqrt(3.0) * s  # largura (entre lados paralelos)
    dy = 1.5 * s            # distância vertical entre linhas
    ext = area.boundingBox()
    ext.grow(2 * s)
    nx, ny, x0, y_topo = _grade_centralizada(ext, w, dy)
    celulas = []
    for lin in range(ny + 1):
        cy = y_topo - lin * dy
        desloc = w / 2.0 if lin % 2 else 0.0
        for col in range(nx + 1):
            cx = x0 + col * w + desloc
            pts = []
            for k in range(6):
                ang = math.radians(60 * k + 30)
                # arredonda ao milímetro para que hexágonos vizinhos compartilhem
                # exatamente os mesmos vértices
                pts.append(QgsPointXY(round(cx + s * math.cos(ang), 3),
                                      round(cy + s * math.sin(ang), 3)))
            pts.append(pts[0])
            celulas.append(QgsGeometry.fromPolygonXY([pts]))
    return celulas


def recortar(area, celulas):
    area_engine = QgsGeometry.createGeometryEngine(area.constGet())
    area_engine.prepareGeometry()
    pedacos = []
    for c in celulas:
        if not area_engine.intersects(c.constGet()):
            continue
        g = c.intersection(area)
        if g is None or g.isEmpty() or g.area() <= 1e-6:
            continue
        # cada parte desconectada (ex.: dos dois lados de uma estrada) vira um
        # pedaço próprio, para que nenhuma borda fique sem amostra;
        # descarta partes lineares/pontuais residuais
        pedacos.extend(p for p in g.asGeometryCollection() if p.area() > 1e-6)
    return pedacos


def unir_fragmentos(pedacos, area_celula):
    """Une fragmentos de borda pequenos à célula vizinha com maior fronteira comum."""
    limite = FRACAO_MIN_FRAGMENTO * area_celula
    pedacos = list(pedacos)
    mudou = True
    while mudou:
        mudou = False
        pequenos = sorted(
            (i for i, g in enumerate(pedacos) if g.area() < limite),
            key=lambda i: pedacos[i].area(),
        )
        for i in pequenos:
            g = pedacos[i]
            # buffer pequeno para tolerar imprecisão numérica nas arestas comuns;
            # a área da sobreposição é proporcional ao comprimento da fronteira
            g_buf = g.buffer(0.05, 2)
            bb = g_buf.boundingBox()
            melhor, melhor_comp = None, 0.0
            for j, h in enumerate(pedacos):
                if j == i or not bb.intersects(h.boundingBox()):
                    continue
                comum = g_buf.intersection(h)
                comp = comum.area() if comum and not comum.isEmpty() else 0.0
                if comp > melhor_comp:
                    melhor, melhor_comp = j, comp
            if melhor is not None:
                pedacos[melhor] = pedacos[melhor].combine(g).makeValid()
                del pedacos[i]
                mudou = True
                break  # índices mudaram: recomeça
    return pedacos


def ponto_amostral(geom):
    c = geom.centroid()
    if not c.isEmpty() and geom.contains(c):
        return c.asPoint()
    return geom.pointOnSurface().asPoint()


def pontos_grade_normal(area, espacamento):
    ext = area.boundingBox()
    nx, ny, x0, y_topo = _grade_centralizada(ext, espacamento, espacamento)
    engine = QgsGeometry.createGeometryEngine(area.constGet())
    engine.prepareGeometry()
    pontos = []
    for lin in range(ny):
        y = y_topo - (lin + 0.5) * espacamento
        for col in range(nx):
            x = x0 + (col + 0.5) * espacamento
            p = QgsGeometry.fromPointXY(QgsPointXY(x, y))
            if engine.contains(p.constGet()):
                pontos.append(QgsPointXY(x, y))
    if not pontos:
        pontos.append(area.pointOnSurface().asPoint())
    return pontos


def ordenar_serpentina(itens, espacamento_linha, chave_ponto):
    """Ordena em zigue-zague (linhas de norte a sul, alternando o sentido)."""
    if not itens:
        return itens
    ymax = max(chave_ponto(i).y() for i in itens)
    linhas = {}
    for it in itens:
        lin = int(round((ymax - chave_ponto(it).y()) / espacamento_linha))
        linhas.setdefault(lin, []).append(it)
    ordenados = []
    for k, lin in enumerate(sorted(linhas)):
        grupo = sorted(linhas[lin], key=lambda i: chave_ponto(i).x(), reverse=bool(k % 2))
        ordenados.extend(grupo)
    return ordenados


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def gerar_plano(area, metodo, ha_por_amostra):
    """Retorna (pontos, poligonos). poligonos é None para grade normal."""
    if ha_por_amostra <= 0:
        raise ErroAmostragem("A densidade amostral deve ser maior que zero.")
    area_celula = ha_por_amostra * 10000.0
    lado = math.sqrt(area_celula)

    n_estimado = area.area() / area_celula
    if n_estimado > 20000:
        raise ErroAmostragem(
            "A densidade informada geraria cerca de %d amostras. "
            "Verifique o valor de hectares por amostra." % n_estimado
        )

    if metodo == METODO_GRADE:
        pontos = pontos_grade_normal(area, lado)
        pontos = ordenar_serpentina(pontos, lado, lambda p: p)
        return pontos, None

    if metodo == METODO_CELULA:
        celulas = celulas_quadradas(area, lado)
        passo_linha = lado
    elif metodo == METODO_HEXAGONO:
        celulas = celulas_hexagonais(area, area_celula)
        passo_linha = 1.5 * math.sqrt(2.0 * area_celula / (3.0 * math.sqrt(3.0)))
    else:
        raise ErroAmostragem("Método desconhecido: %s" % metodo)

    pedacos = unir_fragmentos(recortar(area, celulas), area_celula)
    pares = [(g, ponto_amostral(g)) for g in pedacos]
    pares = ordenar_serpentina(pares, passo_linha, lambda par: par[1])
    return [p for _, p in pares], [g for g, _ in pares]


def criar_camadas(pontos, poligonos, crs, nome_base):
    authid = crs.authid() or crs.toWkt()

    lyr_pts = QgsVectorLayer("Point?crs=%s" % authid, "%s - pontos" % nome_base, "memory")
    pr = lyr_pts.dataProvider()
    pr.addAttributes([
        QgsField("id", QVariant.Int),
        QgsField("x", QVariant.Double, len=15, prec=3),
        QgsField("y", QVariant.Double, len=15, prec=3),
    ])
    lyr_pts.updateFields()
    feats = []
    for i, p in enumerate(pontos, start=1):
        f = QgsFeature(lyr_pts.fields())
        f.setGeometry(QgsGeometry.fromPointXY(p))
        f.setAttributes([i, round(p.x(), 3), round(p.y(), 3)])
        feats.append(f)
    pr.addFeatures(feats)
    lyr_pts.updateExtents()

    lyr_pol = None
    if poligonos is not None:
        lyr_pol = QgsVectorLayer("MultiPolygon?crs=%s" % authid, "%s - células" % nome_base, "memory")
        pr = lyr_pol.dataProvider()
        pr.addAttributes([
            QgsField("id", QVariant.Int),
            QgsField("area_ha", QVariant.Double, len=12, prec=4),
        ])
        lyr_pol.updateFields()
        feats = []
        for i, g in enumerate(poligonos, start=1):
            f = QgsFeature(lyr_pol.fields())
            g2 = QgsGeometry(g)
            g2.convertToMultiType()
            f.setGeometry(g2)
            f.setAttributes([i, round(g.area() / 10000.0, 4)])
            feats.append(f)
        pr.addFeatures(feats)
        lyr_pol.updateExtents()

    return lyr_pts, lyr_pol
