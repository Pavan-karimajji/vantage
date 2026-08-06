# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`ProbePanel` -- `sim probe` as a panel, not just a verb (`S-D8`,
`sim_player.md` §4: "drop a library on the window and Vantage prints its
ports, types and schemas. This is the **day-one screen** for a new
component"). Reuses `contracts.component.CtypesSilComponent` directly --
the exact same load `cli/probe.py` performs, never a re-parse of that
command's own text output, so the two can never silently disagree about
what a library declares.

**No mapping step** (`sim_architecture.md` §5.16.1, `cli/probe.py`'s own
docstring): every field shown comes straight off `adasManifest()`'s
decoded bytes."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from adas_sim.contracts.component import ComponentManifest, CtypesSilComponent, PortSpec
from adas_sim.core.errors import SimError

_PORT_COLUMNS = ("port", "proto_type", "optional", "owner", "period_us")


class ProbePanel(QtWidgets.QWidget):
    """Accepts a dropped file OR a browsed one -- both paths converge on
    `probe()`, the one place a library actually gets loaded."""

    manifest_loaded = QtCore.Signal(object)  # ComponentManifest
    load_failed = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProbePanel")
        self.setAcceptDrops(True)

        layout = QtWidgets.QVBoxLayout(self)
        self._browse_button = QtWidgets.QPushButton("Probe a Library…")
        self._browse_button.clicked.connect(self._on_browse_clicked)
        layout.addWidget(self._browse_button)

        self._summary_label = QtWidgets.QLabel("Drop a component library here, or click above.")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        self._ports_tree = QtWidgets.QTreeWidget()
        self._ports_tree.setHeaderLabels(_PORT_COLUMNS)
        layout.addWidget(self._ports_tree)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # noqa: N802 -- Qt override
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: N802 -- Qt override
        urls = event.mimeData().urls()
        if urls:
            self.probe(Path(urls[0].toLocalFile()))

    def _on_browse_clicked(self) -> None:
        path_str, _filter = QtWidgets.QFileDialog.getOpenFileName(self, "Probe a Library")
        if path_str:
            self.probe(Path(path_str))

    def probe(self, path: Path) -> None:
        """Public so a drag/drop, a browse, or a caller wiring the
        start page's own `probe_requested` signal all reach exactly one
        code path (`app/shell/window.py`'s own integration point)."""
        try:
            component = CtypesSilComponent(path)
        except SimError as exc:
            message = str(exc)
            self._summary_label.setText(f"could not load {path}: {message}")
            self._ports_tree.clear()
            self.load_failed.emit(message)
            return
        self._render_manifest(path, component.manifest)
        self.manifest_loaded.emit(component.manifest)

    def _render_manifest(self, path: Path, manifest: ComponentManifest) -> None:
        self._summary_label.setText(
            f"{manifest.component} v{manifest.version} (abi {manifest.abi_version}, build {manifest.build_id or '(unset)'}) "
            f"-- {path}\nproject={manifest.project or '(unset)'} "
            f"config_bundle={manifest.config_bundle_sha256 or '(unresolved)'} "
            f"period_ns={manifest.period_ns or '(undeclared)'}"
        )
        self._ports_tree.clear()
        inputs_root = QtWidgets.QTreeWidgetItem(["inputs", "", "", "", ""])
        self._ports_tree.addTopLevelItem(inputs_root)
        for port in manifest.inputs:
            inputs_root.addChild(self._port_item(port))
        outputs_root = QtWidgets.QTreeWidgetItem(["outputs", "", "", "", ""])
        self._ports_tree.addTopLevelItem(outputs_root)
        for port in manifest.outputs:
            outputs_root.addChild(self._port_item(port))
        self._ports_tree.expandAll()

    @staticmethod
    def _port_item(port: PortSpec) -> QtWidgets.QTreeWidgetItem:
        return QtWidgets.QTreeWidgetItem([
            port.name, port.proto_type, str(port.optional),
            port.owner_function, str(port.period_us) if port.period_us else "",
        ])
