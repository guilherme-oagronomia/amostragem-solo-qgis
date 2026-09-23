# Amostragem de Solo — plugin QGIS

Plugin para o QGIS que gera **planos de amostragem de solo** a partir do perímetro da área.

## Métodos

| Método | O que gera |
|---|---|
| **Célula** | Grade de células quadradas recortada pelo perímetro, com um ponto amostral por célula |
| **Grade normal** | Pontos em grade regular dentro do perímetro |
| **Hexágono** | Grade de hexágonos recortada pelo perímetro, com um ponto amostral por hexágono |

A única variável é a **densidade amostral** (hectares por amostra): você escolhe um valor da lista ou digita qualquer valor.

- O tamanho da célula é igual à densidade escolhida. Na célula quadrada, o lado é √(ha × 10.000) m.
- Pedaços de borda menores que 50% de uma célula são unidos à célula vizinha. Áreas separadas por estradas ou divisas recebem amostra própria.
- Os pontos são numerados em zigue-zague, de norte para sul, para facilitar o percurso no campo.
- Se o perímetro estiver em coordenadas geográficas, o resultado sai em UTM WGS 84, na zona da área.

## Instalação

1. Baixe o `amostragem_solo.zip` na página de [Releases](https://github.com/guilherme-oagronomia/amostragem-solo-qgis/releases).
2. No QGIS, vá em *Complementos → Gerenciar e Instalar Complementos → Instalar a partir do ZIP*.
3. Para usar, abra *Complementos → Amostragem de Solo → Plano de Amostragem de Solo* ou clique no ícone da barra de ferramentas.

## Uso

1. Escolha o perímetro: uma camada aberta no QGIS, com opção de usar só as feições selecionadas, ou um shapefile do computador.
2. Marque um ou mais métodos.
3. Informe os hectares por amostra.
4. Clique em **Gerar plano**. As camadas de pontos (e de células, quando houver) são adicionadas a um grupo no projeto.

## Desenvolvimento

Para gerar o zip de instalação:

```bash
python build_zip.py
```

O arquivo sai em `dist/amostragem_solo.zip`, já com o `LICENSE` dentro da pasta do plugin.

## Licença

GPL v3. Veja o arquivo [LICENSE](LICENSE).
