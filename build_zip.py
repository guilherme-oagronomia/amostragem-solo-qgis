"""Gera dist/amostragem_solo.zip no formato aceito pelo QGIS.

Uso: python build_zip.py
"""
import os
import zipfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
PLUGIN = "amostragem_solo"
IGNORAR_DIRS = {"__pycache__"}
IGNORAR_EXT = {".pyc"}


def main():
    os.makedirs(os.path.join(RAIZ, "dist"), exist_ok=True)
    destino = os.path.join(RAIZ, "dist", PLUGIN + ".zip")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for pasta, dirs, arquivos in os.walk(os.path.join(RAIZ, PLUGIN)):
            dirs[:] = [d for d in dirs if d not in IGNORAR_DIRS]
            for nome in arquivos:
                if os.path.splitext(nome)[1] in IGNORAR_EXT:
                    continue
                caminho = os.path.join(pasta, nome)
                z.write(caminho, os.path.relpath(caminho, RAIZ).replace(os.sep, "/"))
        # a licença precisa ir dentro da pasta do plugin
        z.write(os.path.join(RAIZ, "LICENSE"), PLUGIN + "/LICENSE")
    print("Gerado:", destino)
    for n in zipfile.ZipFile(destino).namelist():
        print("  ", n)


if __name__ == "__main__":
    main()
