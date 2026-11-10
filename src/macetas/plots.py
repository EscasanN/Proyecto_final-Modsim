"""Figuras regenerables exclusivamente desde tablas exportadas."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


COLORS = ["#276587", "#c16b34", "#4a8573", "#8a6599"]


def _save(fig, output, name):
    fig.tight_layout()
    for extension in ("png", "pdf"):
        fig.savefig(output / f"{name}.{extension}", dpi=170)
    plt.close(fig)


def generate_plots(experiment_dir, *, validation_dir=None, output_dir=None):
    root = Path(experiment_dir)
    output = Path(output_dir) if output_dir else root / "figures"
    output.mkdir(parents=True, exist_ok=True)
    runs = pd.read_csv(root / "runs.csv")
    trace = pd.read_csv(root / "trajectory.csv")
    events = pd.read_csv(root / "events.csv")
    origin = ", ".join(sorted(runs.data_origin.unique()))
    with plt.rc_context({"axes.spines.top": False, "axes.spines.right": False,
                         "axes.prop_cycle": matplotlib.cycler(color=COLORS), "font.size": 10}):
        fig, ax = plt.subplots(figsize=(10, 4.5))
        if validation_dir:
            observed = pd.read_csv(Path(validation_dir) / "comparisons.csv")
            pot = sorted(observed.pot_id.unique())[0]
            observed = observed[observed.pot_id.eq(pot) & observed.window_id.eq(observed.window_id.min())]
            vt = pd.read_csv(Path(validation_dir) / "trajectory.csv")
            vt = vt[vt.pot_id.eq(pot) & vt.window_id.eq(observed.window_id.iloc[0])]
            ax.plot(pd.to_datetime(vt.timestamp), vt.deficit_ml, label=f"Simulado {pot}")
            ax.scatter(pd.to_datetime(observed.timestamp), observed.observed_deficit_ml,
                       marker="x", color=COLORS[1], label=f"Observado {pot} ({observed.data_origin.iloc[0]})")
            ve = pd.read_csv(Path(validation_dir) / "events.csv")
            ve = ve[ve.pot_id.eq(pot) & ve.window_id.eq(observed.window_id.iloc[0])]
            for t in ve.timestamp:
                ax.axvline(pd.Timestamp(t), color="gray", alpha=0.25)
            title = "Validación de dinámica; líneas verticales: riegos registrados"
        else:
            seed = int(runs.seed.min())
            for condition in ("B0", "O0"):
                subset = trace[trace.seed.eq(seed) & trace.condition.eq(condition)]
                ax.plot(pd.to_datetime(subset.timestamp), subset.deficit_ml, label=condition)
            subset = events[events.seed.eq(seed) & events.condition.isin(["B0", "O0"])]
            ax.scatter(pd.to_datetime(subset.timestamp), subset.deficit_before_ml, marker="v", label="Riego (incluye cierre)")
            ax.axhline(runs.safe_deficit_ml.iloc[0], ls="--", color="#a33d3d", label="Límite operacional del ejemplo" if origin == "synthetic" else "Límite operacional")
            title = f"Dinámica de políticas, semilla {seed}; observaciones no disponibles"
        ax.set(title=f"{title}\nOrigen: {origin}", xlabel="Fecha y hora (America/Guatemala)", ylabel="Déficit de agua [mL]")
        ax.legend(fontsize=8)
        fig.autofmt_xdate()
        _save(fig, output, "01_system")

        fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
        conditions = ["B0", "O0", "B1", "O1"]
        groups = [runs[runs.condition.eq(c)] for c in conditions]
        means = np.array([g.total_irrigation_ml.mean() for g in groups])
        refills = np.array([g.final_refill_ml.mean() for g in groups])
        sd = [g.total_irrigation_ml.std(ddof=1) if len(g) > 1 else 0 for g in groups]
        axes[0].bar(conditions, means-refills, label="Operacional", color=COLORS[0])
        axes[0].bar(conditions, refills, bottom=means-refills, label="Reposición final", color=COLORS[1])
        axes[0].errorbar(conditions, means, yerr=sd, fmt="none", color="black", capsize=4)
        axes[0].set(title="Agua aplicada: media ± DE", ylabel="Agua [mL]")
        axes[0].legend(fontsize=8)
        axes[1].boxplot([g.drainage_ml for g in groups], tick_labels=conditions)
        axes[1].set(title="Dispersión del drenaje", ylabel="Drenaje [mL]")
        fig.suptitle(f"Comparación pareada de políticas; origen: {origin}")
        _save(fig, output, "02_policies")

        fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
        x = np.arange(2)
        for i, label in enumerate(("B", "O")):
            gs = [runs[runs.condition.eq(f"{label}{s}")] for s in (0, 1)]
            axes[0].errorbar(x + (i-.5)*.06, [g.total_irrigation_ml.mean() for g in gs],
                             yerr=[g.total_irrigation_ml.std() if len(g)>1 else 0 for g in gs],
                             marker="o", capsize=4, label=label)
            axes[1].bar(x + (i-.5)*.34, [g.feasible.mean() for g in gs], width=.32, label=label)
        for ax in axes:
            ax.set_xticks(x, ["Normal", "Pérdidas +20 %"])
            ax.legend()
        axes[0].set(title="Consumo: media ± DE", ylabel="Agua total [mL]")
        axes[1].set(title="Cumplimiento de restricciones", ylabel="Proporción factible [0–1]", ylim=(0, 1.05))
        fig.suptitle(f"Sensibilidad con política congelada; origen: {origin}")
        _save(fig, output, "03_sensitivity")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiments", required=True)
    parser.add_argument("--validation")
    parser.add_argument("--out")
    args = parser.parse_args()
    print(generate_plots(args.experiments, validation_dir=args.validation, output_dir=args.out))
