"""Renderização responsiva dos gráficos do dashboard."""

from __future__ import annotations

import math
import textwrap
from typing import Mapping, Sequence, Tuple

from matplotlib.ticker import FuncFormatter


class DashboardChartRenderer:
    """Desenha gráficos legíveis tanto na tela quanto na exportação."""

    SERIES_COLORS = (
        "#317968", "#5A8EB2", "#8D83B6", "#C1955F",
        "#6BA892", "#A6778A", "#7E93A8", "#A3AF70",
    )

    def __init__(self, colors: Mapping[str, str]):
        self.colors = colors

    def draw_bar(
        self,
        canvas_info,
        data: Sequence[Tuple[str, float]],
        title: str,
        axis_label: str,
        *,
        is_value: bool,
    ):
        ax, fig, canvas = self._prepare(canvas_info)
        self._resize_for_rows(fig, canvas, len(data))
        self._title(ax, title)
        ax.set_xlabel(axis_label, fontsize=10, color=self.colors["muted"], labelpad=9)
        if not data:
            self._draw_empty(ax, canvas)
            return

        labels = [self._wrap_label(label) for label, _ in data]
        values = [float(value or 0) for _, value in data]
        positions = list(range(len(labels)))
        self._row_guides(ax, positions)

        colors = [
            self.colors["primary"] if value >= 0 else self.colors["orange"]
            for value in values
        ]
        bars = ax.barh(
            positions,
            values,
            color=colors,
            alpha=0.94,
            height=0.56,
            edgecolor="none",
            zorder=2,
        )
        ax.set_yticks(positions)
        ax.set_yticklabels(labels, fontsize=9.5, color=self.colors["text"])
        ax.invert_yaxis()
        ax.grid(axis="x", color="#E6ECF5", linewidth=0.9)
        ax.set_axisbelow(True)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: self._fmt_axis(value)))
        ax.get_xaxis().get_offset_text().set_visible(False)

        minimum = min(values)
        maximum = max(values)
        largest = max(abs(value) for value in values) or 1.0
        if minimum >= 0:
            ax.set_xlim(0, largest * 1.24)
            label_x = largest * 1.035
            for bar, value in zip(bars, values):
                label = ax.text(
                    label_x,
                    bar.get_y() + bar.get_height() / 2,
                    self._fmt_value(value, is_value),
                    va="center",
                    ha="left",
                    fontsize=9.2,
                    fontweight="bold",
                    color=self.colors["text"],
                    clip_on=False,
                )
                label.set_gid("value-label")
        else:
            span = (maximum - minimum) or largest
            ax.set_xlim(minimum - span * 0.18, maximum + span * 0.22)
            ax.axvline(0, color="#BAC5D6", linewidth=1.0, zorder=1)
            for bar, value in zip(bars, values):
                offset = largest * 0.018
                label = ax.text(
                    value + (offset if value >= 0 else -offset),
                    bar.get_y() + bar.get_height() / 2,
                    self._fmt_value(value, is_value),
                    va="center",
                    ha="left" if value >= 0 else "right",
                    fontsize=9.0,
                    fontweight="bold",
                    color=self.colors["text"],
                    clip_on=False,
                )
                label.set_gid("value-label")

        self._finish_axes(ax)
        self._apply_layout(
            fig,
            left=self._left_margin(labels),
            right=0.965,
            top_inches=0.64,
            bottom_inches=0.70,
        )
        self._render(canvas)

    def draw_line(
        self,
        canvas_info,
        data: Sequence[Tuple[str, float]],
        title: str,
        axis_label: str,
        *,
        is_value: bool,
    ):
        ax, fig, canvas = self._prepare(canvas_info)
        self._resize_figure(fig, canvas, 4.8)
        self._title(ax, title)
        if not data:
            self._draw_empty(ax, canvas)
            return

        labels = [self._format_competence(label) for label, _ in data]
        values = [float(value or 0) for _, value in data]
        positions = list(range(len(labels)))

        if len(data) == 1:
            ax.bar(
                positions,
                values,
                color=self.colors["primary"],
                alpha=0.15,
                width=0.28,
            )
        else:
            ax.plot(
                positions,
                values,
                marker="o",
                markersize=5.5,
                linewidth=2.5,
                color=self.colors["primary"],
                zorder=3,
            )
            ax.fill_between(
                positions,
                values,
                alpha=0.08,
                color=self.colors["primary"],
                zorder=1,
            )

        ax.scatter(
            positions,
            values,
            color=self.colors["primary"],
            edgecolor="#FFFFFF",
            linewidth=1.2,
            s=48,
            zorder=4,
        )
        for index in range(len(values)):
            self._annotate(
                ax,
                positions[index],
                values[index],
                self._fmt_value(values[index], is_value),
                9,
                rotation=90,
            )

        tick_step = max(1, math.ceil(len(labels) / 12))
        tick_indexes = list(range(0, len(labels), tick_step))
        if tick_indexes[-1] != len(labels) - 1:
            tick_indexes.append(len(labels) - 1)
        ax.set_xticks(tick_indexes)
        ax.set_xticklabels(
            [labels[index] for index in tick_indexes],
            rotation=35 if len(tick_indexes) > 7 else 0,
            ha="right" if len(tick_indexes) > 7 else "center",
        )
        ax.set_ylabel(axis_label, fontsize=10, color=self.colors["muted"], labelpad=10)
        ax.grid(axis="y", color="#E6ECF5", linewidth=0.9)
        ax.set_axisbelow(True)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: self._fmt_axis(value)))
        ax.get_yaxis().get_offset_text().set_visible(False)
        self._finish_axes(ax)
        ax.tick_params(axis="x", colors=self.colors["muted"], labelsize=9.2)
        largest = max(values) if values else 1
        ax.set_ylim(0, largest * 1.27 if largest > 0 else 1)
        ax.margins(x=0.035)
        self._apply_layout(
            fig,
            left=0.11,
            right=0.97,
            top_inches=0.68,
            bottom_inches=0.92,
        )
        self._render(canvas)

    def draw_stacked_bar(
        self,
        canvas_info,
        comparison,
        title: str,
        axis_label: str,
        *,
        is_value: bool,
        competence_labels: bool = False,
        legend_at_top: bool = False,
    ):
        """Desenha uma comparação por financiamento sem sobrepor rótulos."""
        ax, fig, canvas = self._prepare(canvas_info)
        categories = list(comparison.categories)
        series = list(comparison.series)
        matrix = [list(row) for row in comparison.values]
        self._resize_for_rows(fig, canvas, len(categories), legend=True)
        if not legend_at_top:
            self._title(ax, title)
        ax.set_xlabel(axis_label, fontsize=10, color=self.colors["muted"], labelpad=9)

        if not categories or not series:
            self._draw_empty(ax, canvas)
            return

        if competence_labels:
            labels = [self._format_competence(label) for label in categories]
        else:
            labels = [self._wrap_label(label) for label in categories]
        positions = list(range(len(labels)))
        self._row_guides(ax, positions)
        row_totals = [sum(float(value or 0) for value in row) for row in matrix]
        largest = max(row_totals) or 1.0
        cumulative = [0.0] * len(categories)

        for series_index, series_label in enumerate(series):
            values = [float(row[series_index] or 0) for row in matrix]
            color = self.SERIES_COLORS[series_index % len(self.SERIES_COLORS)]
            bars = ax.barh(
                positions,
                values,
                left=cumulative,
                height=0.58,
                color=color,
                edgecolor="#FFFFFF",
                linewidth=0.7,
                label=self._legend_label(series_label),
                zorder=2,
            )
            for row_index, (bar, value) in enumerate(zip(bars, values)):
                total = row_totals[row_index]
                if value <= 0 or total <= 0:
                    continue
                share = value / total
                # O total externo continua visível; o texto interno só aparece
                # quando o segmento tem largura real para comportá-lo.
                if share >= 0.12 and value / largest >= 0.085:
                    segment_label = ax.text(
                        cumulative[row_index] + value / 2,
                        bar.get_y() + bar.get_height() / 2,
                        self._fmt_compact(value, is_value),
                        ha="center",
                        va="center",
                        fontsize=7.6,
                        fontweight="bold",
                        color="#FFFFFF",
                        clip_on=True,
                    )
                    segment_label.set_gid("segment-label")
            cumulative = [left + value for left, value in zip(cumulative, values)]

        total_x = largest * 1.025
        for position, total in zip(positions, row_totals):
            total_label = ax.text(
                total_x,
                position,
                f"Total {self._fmt_value(total, is_value)}",
                va="center",
                ha="left",
                fontsize=8.8,
                fontweight="bold",
                color=self.colors["text"],
                clip_on=False,
            )
            total_label.set_gid("total-label")

        ax.set_yticks(positions)
        ax.set_yticklabels(labels, fontsize=9.3, color=self.colors["text"])
        ax.invert_yaxis()
        ax.set_xlim(0, largest * 1.25)
        ax.grid(axis="x", color="#E6ECF5", linewidth=0.9)
        ax.set_axisbelow(True)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: self._fmt_axis(value)))
        ax.get_xaxis().get_offset_text().set_visible(False)
        self._finish_axes(ax)

        legend_columns = min(3, len(series))
        legend_rows = math.ceil(len(series) / legend_columns)
        if legend_at_top:
            legend = ax.legend(
                loc="lower left",
                bbox_to_anchor=(0, 1.015),
                frameon=False,
                ncol=legend_columns,
                fontsize=8.2,
                labelcolor=self.colors["text"],
                handlelength=1.5,
                columnspacing=1.3,
                title="Legenda — Tipo de financiamento",
                title_fontproperties={"size": 9.2, "weight": "bold"},
            )
            legend.set_gid("financing-legend-top")
            top_inches = 0.74 + legend_rows * 0.40
            bottom_inches = 0.74
        else:
            legend = ax.legend(
                loc="upper left",
                bbox_to_anchor=(0, -0.14),
                frameon=False,
                ncol=legend_columns,
                fontsize=8.2,
                labelcolor=self.colors["text"],
                handlelength=1.5,
                columnspacing=1.3,
                title="Legenda — Tipo de financiamento",
                title_fontproperties={"size": 9.2, "weight": "bold"},
            )
            legend.set_gid("financing-legend-bottom")
            top_inches = 0.64
            bottom_inches = 0.92 + legend_rows * 0.30

        left_margin = self._left_margin(labels)
        self._apply_layout(
            fig,
            left=left_margin,
            right=0.965,
            top_inches=top_inches,
            bottom_inches=bottom_inches,
        )
        if legend_at_top:
            height = max(float(fig.get_figheight()), 1.0)
            fig.text(
                left_margin,
                1.0 - 0.13 / height,
                title,
                ha="left",
                va="top",
                fontsize=12,
                fontweight="bold",
                color=self.colors["text"],
            ).set_gid("chart-title")
        self._render(canvas)

    def _prepare(self, canvas_info):
        fig = canvas_info["fig"]
        canvas = canvas_info["canvas"]
        # Recriar o eixo impede que artistas/eixos de uma renderização anterior
        # permaneçam sobrepostos após atualizar um gráfico já visível no Tk.
        fig.clear()
        ax = fig.add_subplot(111)
        canvas_info["ax"] = ax
        ax.set_facecolor(self.colors["card"])
        fig.patch.set_facecolor(self.colors["card"])
        return ax, fig, canvas

    def _title(self, ax, title: str):
        ax.set_title(
            title,
            loc="left",
            fontsize=12,
            fontweight="bold",
            color=self.colors["text"],
            pad=12,
        )

    def _draw_empty(self, ax, canvas):
        ax.text(
            0.5,
            0.52,
            "Sem produção para esta consulta.\nAjuste os filtros ou importe arquivos do SIA.",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=11,
            color=self.colors["muted"],
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        self._render(canvas)

    def _annotate(
        self,
        ax,
        x,
        y,
        text: str,
        offset: int,
        *,
        rotation: int = 0,
    ):
        annotation = ax.annotate(
            text,
            xy=(x, y),
            xytext=(0, offset),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7.8 if rotation else 8.2,
            fontweight="bold",
            color=self.colors["text"],
            rotation=rotation,
            bbox={
                "boxstyle": "round,pad=0.18" if rotation else "round,pad=0.26",
                "facecolor": self.colors["card"],
                "edgecolor": "#DDE5F2",
                "linewidth": 0.6,
                "alpha": 0.96,
            },
        )
        annotation.set_gid("value-label")

    def _finish_axes(self, ax):
        for spine in ("top", "right", "left"):
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color("#D7DEEA")
        ax.tick_params(axis="x", colors=self.colors["muted"], labelsize=9.2)
        ax.tick_params(axis="y", colors=self.colors["muted"], labelsize=9.2, length=0, pad=8)

    def _row_guides(self, ax, positions):
        for index in positions:
            if index % 2 == 0:
                ax.axhspan(index - 0.48, index + 0.48, color="#F8FAFD", zorder=0)

    def _resize_for_rows(self, fig, canvas, row_count: int, legend: bool = False):
        base = 5.0 if legend else 4.6
        extra = 0.48 if legend else 0.43
        height = min(18.0, max(base, 1.9 + row_count * extra))
        self._resize_figure(fig, canvas, height)

    @staticmethod
    def _resize_figure(fig, canvas, height: float):
        # forward=False evita que o redimensionamento do Figure dispute a
        # largura com o widget Tk durante uma atualização do gráfico.
        fig.set_size_inches(10.0, height, forward=False)
        get_widget = getattr(canvas, "get_tk_widget", None)
        if callable(get_widget):
            widget = get_widget()
            if widget is not None:
                widget.configure(height=max(420, int(height * fig.dpi)))

    @staticmethod
    def _apply_layout(
        fig,
        *,
        left: float,
        right: float,
        top_inches: float,
        bottom_inches: float,
    ):
        """Mantém o respiro vertical constante mesmo em gráficos muito altos."""
        height = max(float(fig.get_figheight()), 1.0)
        top = min(0.96, max(0.58, 1.0 - top_inches / height))
        bottom = min(0.36, max(0.04, bottom_inches / height))
        if bottom >= top - 0.18:
            bottom = max(0.04, top - 0.18)
        fig.subplots_adjust(left=left, right=right, top=top, bottom=bottom)

    @staticmethod
    def _render(canvas):
        """Finaliza o desenho antes de aceitar outra atualização do Tk."""
        canvas.draw()

    @staticmethod
    def _left_margin(labels) -> float:
        longest = max(
            (len(line) for label in labels for line in str(label).splitlines()),
            default=12,
        )
        return min(0.44, max(0.15, 0.0085 * longest))

    @staticmethod
    def _wrap_label(value, width: int = 44) -> str:
        text = " ".join(str(value or "Não informado").split())
        lines = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
        if len(lines) <= 2:
            return "\n".join(lines)
        second = textwrap.shorten(" ".join(lines[1:]), width=width, placeholder="…")
        return f"{lines[0]}\n{second}"

    @classmethod
    def _legend_label(cls, value: str) -> str:
        return cls._wrap_label(value, width=34)

    @staticmethod
    def _format_competence(value) -> str:
        text = str(value or "")
        if len(text) == 6 and text.isdigit():
            return f"{text[4:6]}/{text[:4]}"
        return text

    @staticmethod
    def _fmt_int(value) -> str:
        return f"{int(round(float(value or 0))):,}".replace(",", ".")

    @staticmethod
    def _fmt_money(value) -> str:
        rendered = f"{float(value or 0):,.2f}"
        return "R$ " + rendered.replace(",", "X").replace(".", ",").replace("X", ".")

    @classmethod
    def _fmt_axis(cls, value) -> str:
        value = float(value)
        if abs(value) >= 1_000_000_000:
            return f"{value / 1_000_000_000:.1f} bi".replace(".", ",")
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:.1f} mi".replace(".", ",")
        if abs(value) >= 1_000:
            return f"{value / 1_000:.0f} mil"
        return cls._fmt_int(value)

    @classmethod
    def _fmt_compact(cls, value, is_value: bool) -> str:
        numeric = float(value or 0)
        prefix = "R$ " if is_value else ""
        if abs(numeric) >= 1_000_000_000:
            rendered = f"{numeric / 1_000_000_000:.1f} bi"
        elif abs(numeric) >= 1_000_000:
            rendered = f"{numeric / 1_000_000:.1f} mi"
        elif abs(numeric) >= 1_000:
            rendered = f"{numeric / 1_000:.0f} mil"
        else:
            rendered = cls._fmt_int(numeric)
        return prefix + rendered.replace(".", ",")

    @classmethod
    def _fmt_value(cls, value, is_value: bool) -> str:
        return cls._fmt_money(value) if is_value else cls._fmt_int(value)
