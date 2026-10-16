"""Exportação de gráficos do dashboard sem dependência da interface Tk."""

from __future__ import annotations

from pathlib import Path


class DashboardImageExporter:
    """Salva uma figura Matplotlib em PNG ou JPEG com qualidade de relatório."""

    FORMATS = {
        ".png": "png",
        ".jpg": "jpeg",
        ".jpeg": "jpeg",
    }

    @classmethod
    def save(cls, figure, destination: str | Path) -> Path:
        path = Path(destination).expanduser()
        image_format = cls.FORMATS.get(path.suffix.lower())
        if image_format is None:
            raise ValueError("Formato inválido. Escolha PNG, JPG ou JPEG.")

        path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(
            path,
            format=image_format,
            dpi=300,
            bbox_inches="tight",
            facecolor=figure.get_facecolor(),
            edgecolor="none",
            metadata={"Software": "Sistema SIA"} if image_format == "png" else None,
        )
        if not path.exists() or path.stat().st_size == 0:
            raise OSError("A imagem não pôde ser gravada.")
        return path
