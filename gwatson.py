from __future__ import annotations

import os
import json
import subprocess

from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QSystemTrayIcon,
    QMenu,
    QWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QInputDialog,
    QPushButton,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QShowEvent
from typing import List, Optional
from datetime import datetime

GW_LOGO_PATH = "logo.png"
GW_WATSON = "watson"
GW_FRAMES_PATH = os.path.join(os.path.expanduser("~"),
                              "Library/Application Support/watson/frames")


def main() -> None:
    gw_application = GWApplication()
    gw_application.exec_()


def find_and_replace(path: str, find_str: str, replace_str: str) -> None:
    with open(path, "r") as f:
        content = f.read()
    content = content.replace(find_str, replace_str)
    with open(path, "w") as f:
        f.write(content)


def str_to_timestamp(datetime_str: str) -> str:
    return str(int(datetime.fromisoformat(datetime_str).timestamp()))


class GWApplication(QApplication):
    def __init__(self) -> None:
        QApplication.__init__(self, [])
        self.setQuitOnLastWindowClosed(False)
        self.init_main_window()
        self.init_system_tray()

    def init_main_window(self) -> None:
        self.main_window = GWMainWindow()
        self.main_window.edit_clicked.connect(self.edit_frame)
        self.main_window.delete_clicked.connect(self.delete_frame)
        self.main_window.window_shown.connect(self.update_report)
        self.main_window.show()

    def edit_frame(self) -> None:
        frame = self.main_window.current_frame()
        if frame is not None:
            frame_json = GWCli.frame_json_truncated(frame.id)
            new_frame_json, okay = QInputDialog.getMultiLineText(
                self.main_window, "Edit frame", "Frame", frame_json)
            if okay:
                new_frame = json.loads(new_frame_json)
                GWCli.edit(frame.id, new_frame["start"], new_frame["stop"])
                self.update_report()

    def delete_frame(self) -> None:
        frame = self.main_window.current_frame()
        if frame is not None:
            GWCli.remove(frame.id)
            self.update_report()

    def init_system_tray(self) -> None:
        self.tray = GWSystemTrayIcon()
        self.tray.menu.start_clicked.connect(self.start_project)
        self.tray.menu.stop_clicked.connect(self.stop_project)
        self.tray.menu.open_clicked.connect(self.main_window.show)
        self.tray.menu.quit_clicked.connect(self.quit)
        self.tray.menu.set_start_enabled(not GWCli.projects_running())

    def start_project(self) -> None:
        project, okay = QInputDialog.getText(
            self.main_window,
            "Start project",
            "Project name",
        )
        if okay:
            self.tray.menu.set_start_enabled(False)
            GWCli.start(project)

    def stop_project(self) -> None:
        self.tray.menu.set_start_enabled(True)
        GWCli.stop()
        self.update_report()

    def update_report(self) -> None:
        self.main_window.update_report(GWCli.weekly_report())


class GWSystemTrayIcon(QSystemTrayIcon):
    def __init__(self) -> None:
        QSystemTrayIcon.__init__(self)
        self.menu = GWSystemTrayContextMenu()
        self.setIcon(QIcon(GW_LOGO_PATH))
        self.setContextMenu(self.menu)
        self.setVisible(True)


class GWSystemTrayContextMenu(QMenu):
    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    open_clicked = pyqtSignal()
    quit_clicked = pyqtSignal()

    def __init__(self) -> None:
        QMenu.__init__(self)
        self.start = self.addAction("Start Project", self.start_clicked.emit)
        self.stop = self.addAction("Stop Project", self.stop_clicked.emit)
        self.open = self.addAction("Open", self.open_clicked.emit)
        self.quit = self.addAction("Quit", self.quit_clicked.emit)

    def set_start_enabled(self, status: bool) -> None:
        self.start.setEnabled(status)
        self.stop.setEnabled(not status)


class GWMainWindow(QMainWindow):
    edit_clicked = pyqtSignal()
    delete_clicked = pyqtSignal()
    window_shown = pyqtSignal()

    def __init__(self) -> None:
        QMainWindow.__init__(self)
        self.init_window_properties()
        self.init_central_widget()

    def init_window_properties(self) -> None:
        self.setWindowTitle("GWatson")
        self.setWindowIcon(QIcon(GW_LOGO_PATH))
        self.setFixedSize(450, 250)

    def init_central_widget(self) -> None:
        main_layout = QVBoxLayout()
        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        self.total_time_spent_label = QLabel()
        main_layout.addWidget(self.total_time_spent_label)
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        main_layout.addWidget(self.tree_widget)
        menu_layout = QHBoxLayout()
        menu_widget = QWidget()
        menu_widget.setLayout(menu_layout)
        main_layout.addWidget(menu_widget)
        edit_button = QPushButton("Edit")
        edit_button.pressed.connect(self.edit_clicked.emit)  # type: ignore
        menu_layout.addWidget(edit_button)
        delete_button = QPushButton("Delete")
        delete_button.pressed.connect(self.delete_clicked.emit)  # type: ignore
        menu_layout.addWidget(delete_button)

    def update_report(self, report: GWReport) -> None:
        self.total_time_spent_label.setText(
            f"{report.time_range} (total: {report.time_spent})")
        self.tree_widget.clear()
        for project in report.projects:
            item = QTreeWidgetItem()
            item.setText(0, f"{project.name} - {project.time_spent}")
            item.setData(0, Qt.UserRole, project)  # type: ignore
            self.tree_widget.addTopLevelItem(item)
            for frame in project.frames:
                child_item = QTreeWidgetItem()
                label = f"{frame.date} - {frame.starts} to {frame.ends}"
                child_item.setText(0, label)
                child_item.setData(0, Qt.UserRole, frame)  # type: ignore
                item.addChild(child_item)

    def current_frame(self) -> Optional[GWFrame]:
        item = self.tree_widget.currentItem()
        if item is None:
            return None
        frame = item.data(0, Qt.UserRole)  # type: ignore
        if not isinstance(frame, GWFrame):
            return None
        return frame

    def showEvent(self, event: QShowEvent) -> None:
        self.window_shown.emit()
        return super().showEvent(event)


class GWCli(object):
    @staticmethod
    def start(project: str) -> None:
        subprocess.run([GW_WATSON, "start", project])

    @staticmethod
    def stop() -> None:
        subprocess.run([GW_WATSON, "stop"])

    @staticmethod
    def remove(frame: str) -> None:
        subprocess.run([GW_WATSON, "remove", "-f", frame])

    @staticmethod
    def edit(frame: str, starts: str, ends: str) -> None:
        frame_json = json.loads(GWCli.frame_json(frame))
        find_and_replace(
            GW_FRAMES_PATH,
            str_to_timestamp(frame_json["start"]),
            str_to_timestamp(starts),
        )
        find_and_replace(
            GW_FRAMES_PATH,
            str_to_timestamp(frame_json["stop"]),
            str_to_timestamp(ends),
        )

    @staticmethod
    def frame_json(frame: str) -> str:
        env = os.environ
        env.update({"VISUAL": "cat"})
        output = subprocess.run(
            [GW_WATSON, "edit", frame],
            stdout=subprocess.PIPE,
            env=env,
        ).stdout.decode()[:-17]
        return output

    @staticmethod
    def frame_json_truncated(frame: str) -> str:
        frame_json = json.loads(GWCli.frame_json(frame))
        return json.dumps(
            {
                "start": frame_json["start"],
                "stop": frame_json["stop"]
            },
            indent=4)

    @staticmethod
    def projects_running() -> bool:
        output = subprocess.run([GW_WATSON, "status"], stdout=subprocess.PIPE)
        return "No project started" not in output.stdout.decode()

    @staticmethod
    def frames(project: str) -> List[GWFrame]:
        lines = subprocess.run(
            [GW_WATSON, "log", "-w", "-p", project],
            stdout=subprocess.PIPE,
        ).stdout.decode().split("\n")
        frames = []
        last_date = ""
        for line in lines[:-1]:
            if line != "":
                nple = line.split(" ")
                if len(nple) < 10:
                    last_date = nple[0]
                else:
                    id, starts, ends, time_spent = nple[0].strip(
                    ), nple[2], nple[4], f"{nple[-5]} {nple[-4]} {nple[-3]}"
                    frames.append(
                        GWFrame(id, last_date, starts, ends, time_spent))
        return frames

    @staticmethod
    def weekly_report() -> GWReport:
        lines = subprocess.run(
            [GW_WATSON, "report", "-w"],
            stdout=subprocess.PIPE,
        ).stdout.decode().split("\n")
        projects = []
        for line in lines[2:-3]:
            if line != "":
                project, time_spent = line.split(" - ")
                frames = GWCli.frames(project)
                projects.append(GWProject(project, frames, time_spent))
        return GWReport(lines[0], projects, lines[-2].split(": ")[1])


class GWReport(object):
    def __init__(
        self,
        time_range: str,
        projects: List[GWProject],
        time_spent: str,
    ) -> None:
        self.time_range = time_range
        self.projects = projects
        self.time_spent = time_spent


class GWProject(object):
    def __init__(
        self,
        name: str,
        frames: List[GWFrame],
        time_spent: str,
    ) -> None:
        self.name = name
        self.frames = frames
        self.time_spent = time_spent


class GWFrame(object):
    def __init__(
        self,
        id: str,
        date: str,
        starts: str,
        ends: str,
        time_spent: str,
    ) -> None:
        self.id = id
        self.date = date
        self.starts = starts
        self.ends = ends
        self.time_spent = time_spent