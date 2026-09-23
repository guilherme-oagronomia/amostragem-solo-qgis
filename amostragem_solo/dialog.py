import os

from qgis.core import (
    Qgis,
    QgsFillSymbol,
    QgsMapLayerProxyModel,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsProject,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
    QgsWkbTypes,
)
from qgis.gui import QgsFileWidget, QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from . import sampling

DENSIDADES_PADRAO = ["1", "2", "2,5", "3", "4", "5", "10"]


class AmostragemDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("Plano de Amostragem de Solo")
        self.setMinimumWidth(460)
        self._montar_interface()
        self._atualizar_origem()
        self._atualizar_resumo()

    # ------------------------------------------------------------------ UI
    def _montar_interface(self):
        layout = QVBoxLayout(self)

        # --- Perímetro
        grp_in = QGroupBox("Perímetro da área")
        lay_in = QVBoxLayout(grp_in)

        self.rb_camada = QRadioButton("Camada aberta no QGIS")
        self.rb_arquivo = QRadioButton("Shapefile do computador")
        self.rb_camada.setChecked(True)
        grupo = QButtonGroup(self)
        grupo.addButton(self.rb_camada)
        grupo.addButton(self.rb_arquivo)

        self.cb_camada = QgsMapLayerComboBox()
        self.cb_camada.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.chk_selecionadas = QCheckBox("Usar apenas feições selecionadas")

        self.fw_arquivo = QgsFileWidget()
        self.fw_arquivo.setFilter("Shapefile (*.shp);;Todos os vetores (*.shp *.gpkg *.geojson *.kml)")
        self.fw_arquivo.setStorageMode(QgsFileWidget.GetFile)

        lay_in.addWidget(self.rb_camada)
        lay_in.addWidget(self.cb_camada)
        lay_in.addWidget(self.chk_selecionadas)
        lay_in.addWidget(self.rb_arquivo)
        lay_in.addWidget(self.fw_arquivo)
        layout.addWidget(grp_in)

        # --- Métodos
        grp_met = QGroupBox("Método de amostragem")
        lay_met = QVBoxLayout(grp_met)
        self.chk_celula = QCheckBox("Amostragem por célula (grade quadrada)")
        self.chk_grade = QCheckBox("Amostragem em grade normal (pontos regulares)")
        self.chk_hex = QCheckBox("Amostragem em hexágonos")
        self.chk_celula.setChecked(True)
        for c in (self.chk_celula, self.chk_grade, self.chk_hex):
            lay_met.addWidget(c)
        layout.addWidget(grp_met)

        # --- Densidade
        grp_dens = QGroupBox("Densidade amostral")
        lay_dens = QFormLayout(grp_dens)
        self.cb_densidade = QComboBox()
        self.cb_densidade.setEditable(True)
        self.cb_densidade.addItems(DENSIDADES_PADRAO)
        self.cb_densidade.setCurrentText("5")
        self.cb_densidade.setToolTip("Selecione ou digite a quantidade de hectares por amostra")
        lay_dens.addRow("Hectares por amostra:", self.cb_densidade)
        self.lbl_resumo = QLabel()
        self.lbl_resumo.setWordWrap(True)
        lay_dens.addRow(self.lbl_resumo)
        layout.addWidget(grp_dens)

        # --- Botões
        botoes = QDialogButtonBox()
        self.btn_gerar = QPushButton("Gerar plano")
        self.btn_gerar.setDefault(True)
        botoes.addButton(self.btn_gerar, QDialogButtonBox.AcceptRole)
        botoes.addButton("Fechar", QDialogButtonBox.RejectRole)
        layout.addWidget(botoes)

        # --- Sinais
        self.rb_camada.toggled.connect(self._atualizar_origem)
        self.cb_camada.layerChanged.connect(self._atualizar_resumo)
        self.chk_selecionadas.toggled.connect(self._atualizar_resumo)
        self.fw_arquivo.fileChanged.connect(self._atualizar_resumo)
        self.cb_densidade.editTextChanged.connect(self._atualizar_resumo)
        self.btn_gerar.clicked.connect(self.gerar)
        botoes.rejected.connect(self.reject)

    def _atualizar_origem(self):
        usar_camada = self.rb_camada.isChecked()
        self.cb_camada.setEnabled(usar_camada)
        self.chk_selecionadas.setEnabled(usar_camada)
        self.fw_arquivo.setEnabled(not usar_camada)
        self._atualizar_resumo()

    # ------------------------------------------------------------ Entradas
    def _densidade(self):
        texto = self.cb_densidade.currentText().strip().replace(",", ".")
        try:
            valor = float(texto)
        except ValueError:
            return None
        return valor if valor > 0 else None

    def _camada_perimetro(self):
        """Retorna (camada, somente_selecionadas)."""
        if self.rb_camada.isChecked():
            return self.cb_camada.currentLayer(), self.chk_selecionadas.isChecked()

        caminho = self.fw_arquivo.filePath()
        if not caminho or not os.path.exists(caminho):
            return None, False
        nome = os.path.splitext(os.path.basename(caminho))[0]
        camada = QgsVectorLayer(caminho, nome, "ogr")
        if not camada.isValid() or camada.geometryType() != QgsWkbTypes.PolygonGeometry:
            return None, False
        return camada, False

    def _atualizar_resumo(self, *args):
        dens = self._densidade()
        camada, sel = self._camada_perimetro()
        if dens is None:
            self.lbl_resumo.setText("<span style='color:#c62828'>Informe um número válido de hectares por amostra.</span>")
            return
        if camada is None:
            self.lbl_resumo.setText("Selecione o perímetro da área.")
            return
        try:
            area, _ = sampling.preparar_perimetro(camada, sel)
        except sampling.ErroAmostragem as e:
            self.lbl_resumo.setText(str(e))
            return
        ha = area.area() / 10000.0
        self.lbl_resumo.setText(
            "Área: <b>%.2f ha</b> — estimativa de <b>~%d amostras</b> (%.2f ha/amostra)."
            % (ha, max(1, round(ha / dens)), dens)
        )

    # ------------------------------------------------------------ Execução
    def gerar(self):
        dens = self._densidade()
        if dens is None:
            QMessageBox.warning(self, "Amostragem de Solo", "Informe um número válido de hectares por amostra.")
            return

        camada, sel = self._camada_perimetro()
        if camada is None:
            QMessageBox.warning(self, "Amostragem de Solo", "Selecione uma camada ou shapefile de polígonos válido.")
            return
        if sel and camada.selectedFeatureCount() == 0:
            QMessageBox.warning(self, "Amostragem de Solo", "Não há feições selecionadas na camada.")
            return

        metodos = [
            m for m, chk in (
                (sampling.METODO_CELULA, self.chk_celula),
                (sampling.METODO_GRADE, self.chk_grade),
                (sampling.METODO_HEXAGONO, self.chk_hex),
            ) if chk.isChecked()
        ]
        if not metodos:
            QMessageBox.warning(self, "Amostragem de Solo", "Selecione ao menos um método de amostragem.")
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            area, crs = sampling.preparar_perimetro(camada, sel)
            area_ha = area.area() / 10000.0
            dens_txt = ("%g" % dens).replace(".", ",")

            root = QgsProject.instance().layerTreeRoot()
            grupo = root.insertGroup(0, "Amostragem - %s (%s ha/amostra)" % (camada.name(), dens_txt))

            linhas = []
            ultima = None
            for metodo in metodos:
                pontos, poligonos = sampling.gerar_plano(area, metodo, dens)
                nome = "%s %s ha" % (sampling.NOMES_METODO[metodo], dens_txt)
                lyr_pts, lyr_pol = sampling.criar_camadas(pontos, poligonos, crs, nome)

                sub = grupo.addGroup(sampling.NOMES_METODO[metodo])
                self._estilo_pontos(lyr_pts)
                QgsProject.instance().addMapLayer(lyr_pts, False)
                sub.addLayer(lyr_pts)
                if lyr_pol is not None:
                    self._estilo_poligonos(lyr_pol)
                    QgsProject.instance().addMapLayer(lyr_pol, False)
                    sub.addLayer(lyr_pol)
                ultima = lyr_pts

                n = len(pontos)
                linhas.append("• %s: %d amostras (%.2f ha/amostra real)"
                              % (sampling.NOMES_METODO[metodo], n, area_ha / n))
        except sampling.ErroAmostragem as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Amostragem de Solo", str(e))
            return
        except Exception as e:  # erro inesperado
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Amostragem de Solo", "Erro ao gerar o plano:\n%s" % e)
            raise
        QApplication.restoreOverrideCursor()

        if ultima is not None and self.iface.mapCanvas() is not None:
            self.iface.mapCanvas().refresh()

        msg = "Área: %.2f ha | SRC: %s\n%s" % (area_ha, crs.authid(), "\n".join(linhas))
        self.iface.messageBar().pushMessage("Amostragem de Solo", msg.replace("\n", "  "), level=Qgis.Success, duration=8)
        QMessageBox.information(self, "Amostragem de Solo", "Plano gerado com sucesso.\n\n" + msg)

    # -------------------------------------------------------------- Estilos
    @staticmethod
    def _estilo_pontos(layer):
        sym = QgsMarkerSymbol.createSimple({
            "name": "circle", "color": "229,57,53", "outline_color": "255,255,255",
            "outline_width": "0.3", "size": "2.6",
        })
        layer.renderer().setSymbol(sym)

        fmt = QgsTextFormat()
        fmt.setSize(8)
        fmt.setColor(QColor(20, 20, 20))
        buf = QgsTextBufferSettings()
        buf.setEnabled(True)
        buf.setSize(0.8)
        buf.setColor(QColor(255, 255, 255))
        fmt.setBuffer(buf)
        pal = QgsPalLayerSettings()
        pal.fieldName = "id"
        pal.setFormat(fmt)
        pal.dist = 1.0
        layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
        layer.setLabelsEnabled(True)

    @staticmethod
    def _estilo_poligonos(layer):
        sym = QgsFillSymbol.createSimple({
            "color": "255,235,59,40", "outline_color": "80,80,80", "outline_width": "0.4",
        })
        layer.renderer().setSymbol(sym)
