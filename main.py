import csv
import json
import math
import os
import re
import sys
from pathlib import Path

from PyQt5.QtCore import QDateTime, QEvent, QPointF, QRectF, QSize, QSharedMemory, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QKeySequence,
    QPixmap,
    QPolygonF,
)
from PyQt5.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QShortcut,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


COLORS = {
    "bg": "#02070F",
    "panel": "#071321",
    "panel_2": "#0B1D31",
    "header_a": "#244AA0",
    "header_b": "#142A66",
    "cyan": "#54D8FF",
    "blue_line": "#2F7DD1",
    "text": "#F5FBFF",
    "muted": "#B8D4FF",
    "green": "#3CE590",
    "green_deep": "#0F8D4F",
    "red": "#FF2F3B",
    "red_deep": "#A10008",
    "yellow": "#F1D143",
    "card": "#376A9B",
    "card_2": "#2F587E",
}

CONFIG_FILENAME = "dashboard_config.json"
WINDOW_TITLE_TEXT = "ui"
DEFAULT_MAIN_TITLE = "PyQt Dashboard"
LEGACY_MAIN_TITLES = set()
DEFAULT_LOWER_LIMIT_OPERATOR = "<="
DEFAULT_UPPER_LIMIT_OPERATOR = ">="
SINGLE_INSTANCE_KEY = "pyqt_dashboard_single_instance_lock_v1"
DEFAULT_SETUP_TITLE = "#带设置#"

DEFAULT_RESULT_ROW_TITLES = {
    "result_1": "指标 1 曲线",
    "result_2": "指标 2 曲线",
    "result_3": "指标 3 状态",
    "result_4": "指标 4 状态",
    "result_5": "指标 5 状态",
    "result_6": "指标 6 状态",
    "result_7": "指标 7 状态",
    "result_8": "指标 8 数值",
    "result_9": "指标 9 数值",
    "result_10": "指标 10 数值",
}

DEFAULT_INSPECTION_TILE_TITLES = {
    "inspect_image_1": "1 指标 1 曲线",
    "inspect_image_2": "2 指标 2 曲线",
    "inspect_image_3": "3 示例图像 1",
    "inspect_image_4": "4 示例图像 2",
    "inspect_image_5": "5 示例图像 3",
    "inspect_image_6": "6 示例图像 4",
    "inspect_image_7": "7 示例图像 5",
    "inspect_image_8": "示例图像 6",
    "inspect_image_9": "示例图像 7",
    "inspect_image_10": "示例图像 8",
}

DEFAULT_RESULT_ROW_SPECS = [
    ("result_1", "指标 1 曲线", "OK", "ok"),
    ("result_2", "指标 2 曲线", "OK", "ok"),
    ("result_3", "指标 3 状态", "OK", "ok"),
    ("result_4", "指标 4 状态", "OK", "ok"),
    ("result_5", "指标 5 状态", "OK", "ok"),
    ("result_6", "指标 6 状态", "OK", "ok"),
    ("result_7", "指标 7 状态", "NG", "bad"),
    ("result_8", "指标 8 数值", "Disabled", "bad"),
    ("result_9", "指标 9 数值", "OK", "bad"),
    ("result_10", "指标 10 数值", "OK", "bad"),
]


def is_builtin_result_title(text):
    clean = str(text or "").strip()
    if not clean:
        return False
    builtin_titles = set(DEFAULT_RESULT_ROW_TITLES.values()) | {spec[1] for spec in DEFAULT_RESULT_ROW_SPECS}
    return clean in builtin_titles


def is_builtin_tile_title(text):
    clean = str(text or "").strip()
    if not clean:
        return False
    return clean in set(DEFAULT_INSPECTION_TILE_TITLES.values())


def default_tile_setup_title(field_id):
    match = re.search(r"inspect_image_(\d+)$", str(field_id or "").strip())
    if match:
        return f"{int(match.group(1))} {DEFAULT_SETUP_TITLE}"
    return DEFAULT_SETUP_TITLE


def make_font(size, weight=QFont.Normal, family="Microsoft YaHei UI"):
    font = QFont(family, pointSize=size)
    font.setWeight(weight)
    return font


def apply_compact_dialog_style(dialog, point_size=8):
    compact_font = make_font(point_size, family="SimSun")
    dialog.setFont(compact_font)
    dialog.setStyleSheet(
        f"""
        QDialog, QLabel, QComboBox, QLineEdit, QPushButton, QListWidget {{
            font-family: SimSun;
            font-size: {point_size}pt;
        }}
        QComboBox, QLineEdit, QPushButton {{
            min-height: 18px;
            padding: 0 4px;
        }}
        QListWidget::item {{
            min-height: 16px;
        }}
        """
    )


def hide_form_row(form_layout, field_widget):
    if not form_layout or field_widget is None:
        return
    label_widget = form_layout.labelForField(field_widget)
    if label_widget is not None:
        label_widget.hide()
    field_widget.hide()


def apply_settings_button_style(button):
    button.setFont(make_font(8, QFont.Bold))
    button.setStyleSheet(
        """
        QPushButton {
            color: #F5FBFF;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #2E5EB7, stop:1 #173873);
            border: 1px solid #58D4FF;
            border-radius: 3px;
            padding: 2px 8px;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #3B73D7, stop:1 #1C4A92);
        }
        """
    )


def get_runtime_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_user_config_dir():
    local_appdata = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
    if local_appdata:
        return Path(local_appdata) / "PyQtDashboardTemplate"
    return Path.home() / ".pyqt_dashboard_template"


def get_config_path_candidates():
    runtime_path = get_runtime_base_dir() / CONFIG_FILENAME
    user_path = get_user_config_dir() / CONFIG_FILENAME
    candidates = []
    for path in (runtime_path, user_path):
        if path not in candidates:
            candidates.append(path)
    return candidates


def parse_numeric_value_from_text(text):
    source = str(text or "").strip()
    if not source:
        return None
    match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", source)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def normalize_lower_limit_operator(value):
    return "<" if str(value or "").strip() == "<" else DEFAULT_LOWER_LIMIT_OPERATOR


def normalize_upper_limit_operator(value):
    return ">" if str(value or "").strip() == ">" else DEFAULT_UPPER_LIMIT_OPERATOR


def add_shadow(widget, color, blur=22, x_offset=0, y_offset=0):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(x_offset, y_offset)
    effect.setColor(QColor(color))
    widget.setGraphicsEffect(effect)


def normalize_status_kind(text):
    value = str(text).strip().upper()
    if not value or value in {"N/A", "NA", "NONE", "NULL", "--", "-"}:
        return "na"
    if value in {"OK", "PASS", "ON", "TRUE", "ENABLE", "ENABLED"}:
        return "ok"
    if value in {"WARN", "WARNING", "ALARM"}:
        return "warn"
    return "bad"


def is_missing_data_value(value):
    if value is None:
        return True
    text = str(value).strip()
    return not text or text.upper() in {"N/A", "NA", "NONE", "NULL", "--", "-"}


def resolve_indicator_color(value, default_color="#57DB8F"):
    text = str(value or "").strip()
    if not text:
        return QColor(default_color)

    direct = QColor(text)
    if direct.isValid():
        return direct

    simplified = text.lower().replace("色", "").strip()
    tokens = {
        "#57DB8F": ("绿色", "绿", "green", "lime", "正常"),
        "#F1D143": ("黄色", "黄", "yellow", "告警", "警告"),
        "#F39A2D": ("橙色", "橙", "orange"),
        "#FF2F3B": ("红色", "红", "red", "异常", "过期"),
        "#4AA8FF": ("蓝色", "蓝", "blue"),
        "#F5FBFF": ("白色", "白", "white"),
    }
    for color_hex, names in tokens.items():
        if any(name in text for name in names) or any(name in simplified for name in names):
            return QColor(color_hex)

    status_kind = normalize_status_kind(text)
    if status_kind == "ok":
        return QColor("#57DB8F")
    if status_kind == "warn":
        return QColor("#F1D143")
    if status_kind == "na":
        return QColor("#7E8792")
    return QColor("#FF2F3B")


def get_curve_limit_color_options():
    return [
        ("橙色", "#FFB020"),
        ("红色", "#FF4D4F"),
        ("黄色", "#F1D143"),
        ("绿色", "#57DB8F"),
        ("蓝色", "#4AA8FF"),
        ("白色", "#F5FBFF"),
    ]


def get_curve_line_style_options():
    return [
        ("虚线", "dash"),
        ("实线", "solid"),
        ("点线", "dot"),
        ("点划线", "dashdot"),
    ]


def get_curve_line_style_label(value):
    normalized = str(value or "dash").strip().lower()
    labels = {style: label for label, style in get_curve_line_style_options()}
    return labels.get(normalized, "虚线")


def resolve_curve_pen_style(value):
    normalized = str(value or "dash").strip().lower()
    mapping = {
        "solid": Qt.SolidLine,
        "dash": Qt.DashLine,
        "dot": Qt.DotLine,
        "dashdot": Qt.DashDotLine,
    }
    return mapping.get(normalized, Qt.DashLine)


def read_text_with_fallback(path):
    for encoding in ("utf-8", "gbk", "utf-8-sig"):
        try:
            return Path(path).read_text(encoding=encoding)
        except Exception:
            continue
    return Path(path).read_text(encoding="latin-1", errors="ignore")


def normalize_section_name(section_name):
    value = str(section_name or "").replace("\ufeff", "").strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1].strip()
    return value


def format_section_title(section_name):
    normalized = normalize_section_name(section_name)
    return f"[{normalized}]" if normalized else "[无小节]"


def split_marked_value(value_text):
    text = str(value_text or "").strip()
    if "###" not in text:
        return text, False
    value, _, _ = text.partition("###")
    return value.rstrip(), True


def get_marked_entries(entries):
    return [entry for entry in entries if entry.get("marked")]


def parse_key_value_lines(lines):
    entries = []
    current_section = ""
    for raw_line in lines:
        line = str(raw_line).replace("\ufeff", "").strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = normalize_section_name(line)
            continue
        if "=" not in line:
            continue
        left, right = line.split("=", 1)
        parsed_value, marked = split_marked_value(right)
        entries.append(
            {
                "section": current_section,
                "key": left.replace("\ufeff", "").strip(),
                "value": parsed_value,
                "marked": marked,
                "raw_line": line,
            }
        )
    return entries


def extract_value_from_lines(lines, key_text, section_name=None):
    target_key = str(key_text).replace("\ufeff", "").strip()
    if not target_key:
        return None
    target_section = None if section_name is None else normalize_section_name(section_name)
    for entry in parse_key_value_lines(lines):
        if target_section is not None and normalize_section_name(entry["section"]) != target_section:
            continue
        if entry["key"] == target_key:
            if not entry.get("marked"):
                return None
            return entry["value"]
    return None


def clean_path_text(value):
    text = str(value or "").strip().strip('"').strip("'")
    return text


def compose_image_path(base_path_value, image_name_value, relative_root=None):
    base_text = clean_path_text(base_path_value)
    name_text = clean_path_text(image_name_value)
    if not base_text and not name_text:
        return None

    candidate = Path(name_text) if not base_text else Path(base_text) / name_text
    if relative_root and not candidate.is_absolute():
        candidate = Path(relative_root) / candidate
    return str(candidate)


def resolve_target_ini_path(target_value, lookup_file_path=None, ini_dir=None):
    target_text = clean_path_text(target_value)
    if not target_text:
        return None

    raw_candidate = Path(target_text)
    candidates = []

    def add_candidate(path_value):
        if not path_value:
            return
        candidate = Path(path_value)
        if not candidate.suffix:
            candidate = candidate.with_suffix(".ini")
        normalized = str(candidate)
        if normalized not in {str(item) for item in candidates}:
            candidates.append(candidate)

    if raw_candidate.is_absolute():
        add_candidate(raw_candidate)
    else:
        add_candidate(raw_candidate)
        if lookup_file_path:
            lookup_path = Path(lookup_file_path)
            add_candidate(lookup_path.parent / raw_candidate)
            add_candidate(lookup_path.parent / "Data" / raw_candidate)
        if ini_dir:
            root_dir = Path(ini_dir)
            add_candidate(root_dir / raw_candidate)
            add_candidate(root_dir / "Data" / raw_candidate)
            add_candidate(root_dir / "UIConfig" / raw_candidate)
            add_candidate(root_dir / "UIConfig" / "Data" / raw_candidate)

    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except Exception:
            continue
    return candidates[-1] if candidates else None


def extract_numeric_values_from_csv_line(raw_line):
    line = raw_line.strip()
    if not line:
        return []

    normalized = line.replace(";", ",").replace("\t", ",")
    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    if len(parts) <= 1:
        parts = [part.strip() for part in line.split() if part.strip()]

    numeric_values = []
    for part in parts:
        try:
            numeric_values.append(float(part))
        except Exception:
            continue
    return numeric_values


def split_csv_row_cells(raw_line):
    text = str(raw_line or "").strip()
    if not text:
        return []
    for delimiter in (",", "\t", ";"):
        if delimiter in text:
            try:
                row = next(csv.reader([text], delimiter=delimiter))
            except Exception:
                row = text.split(delimiter)
            return [cell.strip() for cell in row]
    return [cell.strip() for cell in re.split(r"\s{2,}", text) if cell.strip()]


def extract_curve_match_sn_text(value):
    text = str(value or "").strip()
    if not text or is_missing_data_value(text):
        return ""
    text = re.sub(r"^(当前编号|待处理编号)\s*[:：]\s*", "", text).strip()
    if "_" in text:
        tail = text.rsplit("_", 1)[-1].strip()
        if tail:
            return tail
    stripped = re.sub(
        r"^\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*\d{1,2}\s*[-:]\s*\d{1,2}\s*[-:]\s*\d{1,2}\s*[_\s-]*",
        "",
        text,
    ).strip()
    return stripped or text


def normalize_curve_sn_key(value):
    return re.sub(r"\s+", "", str(value or "").strip()).upper()


def numeric_values_from_csv_cells(cells, start_index=0):
    numeric_values = []
    for cell in cells[start_index:]:
        try:
            numeric_values.append(float(str(cell).strip()))
        except Exception:
            continue
    return numeric_values


def build_sequential_curve_points(numeric_values):
    return [(float(index), float(value)) for index, value in enumerate(numeric_values, start=1)]


def select_curve_points_segment(points, segment):
    if segment not in {"first_half", "second_half"}:
        return points
    if not points:
        return []
    split_index = len(points) // 2
    selected = points[:split_index] if segment == "first_half" else points[split_index:]
    return [(float(index), float(point[1])) for index, point in enumerate(selected, start=1)]


def infer_curve_axis_name(text):
    source = str(text or "")
    if "斜率" in source:
        return "斜率"
    if "亮度" in source:
        return "亮度"
    if "电流" in source:
        return "电流"
    return "数值"


def safe_float_value(value, fallback):
    try:
        return float(value)
    except Exception:
        return float(fallback)


def get_default_curve_y_axis_config(text):
    source = str(text or "")
    if "斜率" in source:
        return {"min": -10.0, "max": 10.0, "interval": 5.0}
    if "亮度" in source:
        return {"min": 0.0, "max": 150.0, "interval": 50.0}
    return {"min": 0.0, "max": 100.0, "interval": 20.0}


def normalize_curve_y_axis_config(y_min, y_max, interval, fallback_text=""):
    defaults = get_default_curve_y_axis_config(fallback_text)
    min_value = safe_float_value(y_min, defaults["min"])
    max_value = safe_float_value(y_max, defaults["max"])
    interval_value = abs(safe_float_value(interval, defaults["interval"]))
    if interval_value <= 0:
        interval_value = defaults["interval"]
    if max_value <= min_value:
        max_value = min_value + interval_value
    return {"min": min_value, "max": max_value, "interval": interval_value}


def build_curve_axis_ticks(y_min, y_max, interval):
    min_value = float(y_min)
    max_value = float(y_max)
    interval_value = abs(float(interval))
    if interval_value <= 0 or max_value <= min_value:
        return [min_value, max_value]

    ticks = []
    value = min_value
    max_ticks = 200
    epsilon = interval_value * 0.001
    while value <= max_value + epsilon and len(ticks) < max_ticks:
        ticks.append(round(value, 6))
        value += interval_value
    if not ticks or abs(ticks[-1] - max_value) > epsilon:
        ticks.append(max_value)
    return ticks


def format_axis_value(value):
    try:
        number = float(value)
    except Exception:
        return str(value)
    if abs(number) >= 100:
        return f"{number:.1f}"
    if abs(number - round(number)) < 1e-6:
        return str(int(round(number)))
    if abs(number) >= 10:
        return f"{number:.1f}"
    return f"{number:.2f}"


def parse_csv_curve_series(csv_path):
    path = Path(csv_path)
    if not path.exists():
        return [], []

    lines = read_text_with_fallback(path).splitlines()
    numeric_rows = []

    for line_index, raw_line in enumerate(lines):
        numeric_values = extract_numeric_values_from_csv_line(raw_line)
        if numeric_values:
            numeric_rows.append((line_index, numeric_values))

    if not numeric_rows:
        return [], lines

    row_lengths = [len(values) for _, values in numeric_rows]
    has_multi_value_rows = any(length > 1 for length in row_lengths)
    all_rows_single_value = all(length == 1 for length in row_lengths)
    all_rows_xy_like = (
        len(numeric_rows) >= 2
        and all(2 <= length <= 3 for length in row_lengths)
        and max(row_lengths) <= 3
    )

    if all_rows_single_value:
        series_list = [[(float(index), values[0]) for index, (_line_idx, values) in enumerate(numeric_rows, start=1)]]
        return series_list, lines

    if all_rows_xy_like:
        points = [(float(index), values[1]) for index, (_line_idx, values) in enumerate(numeric_rows, start=1)]
        return [points], lines

    if has_multi_value_rows:
        series_list = [build_sequential_curve_points(values) for _line_idx, values in numeric_rows if len(values) >= 2]
        if series_list:
            return series_list, lines

    fallback_points = []
    for _line_idx, values in numeric_rows:
        for value in values:
            fallback_points.append((float(len(fallback_points) + 1), value))
    return ([fallback_points] if fallback_points else []), lines


def parse_csv_curve_points(csv_path, series_index=0):
    series_list, _raw_lines = parse_csv_curve_series(csv_path)
    if not series_list:
        return []

    try:
        index = int(series_index)
    except Exception:
        index = 0
    index = max(0, min(index, len(series_list) - 1))
    return series_list[index]


def parse_csv_curve_points_by_sn(csv_path, sn_text):
    target_key = normalize_curve_sn_key(extract_curve_match_sn_text(sn_text))
    if not target_key:
        return [], False

    path = Path(csv_path)
    if not path.exists():
        return [], False

    lines = read_text_with_fallback(path).splitlines()
    for raw_line in lines:
        cells = split_csv_row_cells(raw_line)
        if len(cells) <= 2:
            continue
        row_key = normalize_curve_sn_key(cells[2])
        if not row_key:
            continue
        if row_key == target_key or row_key.endswith(target_key) or target_key.endswith(row_key):
            values = numeric_values_from_csv_cells(cells, 3)
            return build_sequential_curve_points(values), True
    return [], False


def extract_csv_numeric_rows(csv_path):
    path = Path(csv_path)
    if not path.exists():
        return [], []

    lines = read_text_with_fallback(path).splitlines()
    rows = []
    for line_number, raw_line in enumerate(lines, start=1):
        numeric_values = extract_numeric_values_from_csv_line(raw_line)
        if not numeric_values:
            continue
        text = raw_line.strip()
        if len(text) > 180:
            text = text[:180] + "..."
        rows.append(
            {
                "line_number": line_number,
                "text": text,
                "values": numeric_values,
                "series_index": len(rows),
            }
        )
    return rows, lines


class SettingsButton(QPushButton):
    doubleClicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class BindingDialog(QDialog):
    def __init__(self, field_title, ini_dir, current_binding=None, parent=None, fixed_ini_path=None):
        super().__init__(parent)
        self.setWindowTitle(f"绑定设置 - {field_title}")
        self.setModal(True)
        self.resize(620, 420)
        apply_compact_dialog_style(self, 8)
        self._clear_requested = False
        self.ini_dir = Path(ini_dir) if ini_dir else None
        self.fixed_ini_path = Path(fixed_ini_path) if fixed_ini_path else None
        self._pending_file = current_binding.get("file", "") if current_binding else ""
        self._pending_key = current_binding.get("key", "") if current_binding else ""
        self._pending_section = current_binding.get("section") if current_binding and "section" in current_binding else None
        self._entries = []

        layout = QVBoxLayout(self)
        self.form = QFormLayout()
        self.form.setSpacing(8)
        layout.addLayout(self.form)

        folder_host = QWidget()
        folder_layout = QHBoxLayout(folder_host)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(6)
        self.folder_edit = QLineEdit(str(self.ini_dir) if self.ini_dir else "")
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("请选择 INI 文件夹")
        self.folder_edit.setStyleSheet(f"color: {COLORS['muted']};")
        folder_layout.addWidget(self.folder_edit, 1)
        self.folder_browse_button = QPushButton("选择...")
        self.folder_browse_button.clicked.connect(self.choose_folder)
        folder_layout.addWidget(self.folder_browse_button)
        self.form.addRow("INI目录", folder_host)

        self.file_combo = QComboBox()
        self.form.addRow("INI文件", self.file_combo)

        self.section_combo = QComboBox()
        self.form.addRow("匹配小节", self.section_combo)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("输入要匹配的文字，例如 Total 或 Result")
        self.form.addRow("匹配文字", self.key_edit)

        self.preview_label = QLabel("预览值：")
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(30)
        self.preview_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                padding: 8px;
            }}
            """
        )
        self.form.addRow("预览结果", self.preview_label)

        list_title = QLabel("当前 INI 内容")
        list_title.setStyleSheet(f"color: {COLORS['muted']};")
        layout.addWidget(list_title)

        self.entry_list = QListWidget()
        self.entry_list.setMinimumHeight(150)
        self.entry_list.setStyleSheet(
            f"""
            QListWidget {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                outline: none;
            }}
            QListWidget::item {{
                padding: 3px 6px;
                border-bottom: 1px solid #143457;
            }}
            QListWidget::item:selected {{
                background: #1E4D8D;
            }}
            """
        )
        layout.addWidget(self.entry_list, 1)

        if current_binding:
            self.key_edit.setText(current_binding.get("key", ""))
        if self.fixed_ini_path:
            self.folder_browse_button.setEnabled(False)
            self.file_combo.setEnabled(False)
        self.refresh_ini_files()
        self.file_combo.currentIndexChanged.connect(self.handle_file_changed)
        self.section_combo.currentIndexChanged.connect(self.update_preview)
        self.key_edit.textChanged.connect(self.update_preview)
        self.entry_list.itemClicked.connect(self.handle_entry_clicked)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        clear_button = QPushButton("清除绑定")
        buttons.addButton(clear_button, QDialogButtonBox.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        clear_button.clicked.connect(self.clear_binding)
        layout.addWidget(buttons)

    def clear_binding(self):
        self._clear_requested = True
        self.accept()

    def choose_folder(self):
        if self.fixed_ini_path:
            return
        start_dir = str(self.ini_dir or Path.cwd())
        selected = QFileDialog.getExistingDirectory(self, "选择 INI 文件夹", start_dir)
        if not selected:
            return
        self.ini_dir = Path(selected)
        self.folder_edit.setText(str(self.ini_dir))
        self.refresh_ini_files()
        self.update_preview()

    def get_current_file_value(self):
        if self.fixed_ini_path:
            if self.ini_dir:
                try:
                    return str(self.fixed_ini_path.relative_to(self.ini_dir))
                except Exception:
                    return str(self.fixed_ini_path)
            return str(self.fixed_ini_path)
        return self.file_combo.currentData()

    def get_current_file_path(self):
        if self.fixed_ini_path:
            return self.fixed_ini_path
        file_value = self.file_combo.currentData()
        if not file_value or not self.ini_dir:
            return None
        return self.ini_dir / file_value

    def refresh_ini_files(self):
        self.file_combo.clear()
        if self.fixed_ini_path:
            file_value = self.get_current_file_value() if self.fixed_ini_path.exists() else ""
            self.file_combo.addItem(file_value or "当前目标配置不存在", file_value)
            self.refresh_entry_list_from_current_file()
            self.update_preview()
            return
        if not self.ini_dir or not self.ini_dir.exists():
            self.file_combo.addItem("请先选择 INI 文件夹", "")
            self.refresh_section_options([])
            self.refresh_entry_list([])
            self.update_preview()
            return

        ini_files = sorted(str(path.relative_to(self.ini_dir)) for path in self.ini_dir.rglob("*.ini"))
        if not ini_files:
            self.file_combo.addItem("该文件夹下没有 INI 文件", "")
            self.refresh_section_options([])
            self.refresh_entry_list([])
            self.update_preview()
            return

        self.file_combo.addItem("请选择 INI 文件", "")
        for rel_path in ini_files:
            self.file_combo.addItem(rel_path, rel_path)

        if self._pending_file:
            idx = self.file_combo.findData(self._pending_file)
            if idx >= 0:
                self.file_combo.setCurrentIndex(idx)
            self._pending_file = ""
        self.refresh_entry_list_from_current_file()
        self.update_preview()

    def handle_file_changed(self, *_args):
        self.refresh_entry_list_from_current_file()
        self.update_preview()

    def refresh_section_options(self, entries):
        current_data = self.get_selected_section()
        self.section_combo.blockSignals(True)
        self.section_combo.clear()
        self.section_combo.addItem("全部小节（不限定）", None)

        has_root_entries = False
        seen_sections = set()
        for entry in entries:
            section = normalize_section_name(entry["section"])
            if section:
                if section not in seen_sections:
                    seen_sections.add(section)
                    self.section_combo.addItem(format_section_title(section), section)
            else:
                has_root_entries = True

        if has_root_entries:
            self.section_combo.addItem(format_section_title(""), "")

        if self._pending_section is not None:
            self.set_selected_section(normalize_section_name(self._pending_section))
        else:
            self.set_selected_section(current_data)
        self.section_combo.blockSignals(False)

    def set_selected_section(self, section_value):
        for index in range(self.section_combo.count()):
            if self.section_combo.itemData(index) == section_value:
                self.section_combo.setCurrentIndex(index)
                return
        if self.section_combo.count():
            self.section_combo.setCurrentIndex(0)

    def get_selected_section(self):
        if self.section_combo.count() == 0:
            return None
        return self.section_combo.currentData()

    def refresh_entry_list(self, entries):
        self.entry_list.clear()
        if not entries:
            placeholder = QListWidgetItem("当前没有带 ### 标记的可绑定键值行")
            placeholder.setFlags(Qt.NoItemFlags)
            self.entry_list.addItem(placeholder)
            return

        matched_item = None
        last_section = object()
        for entry in entries:
            section = normalize_section_name(entry["section"])
            if section != last_section:
                header = QListWidgetItem(format_section_title(section))
                header.setFlags(Qt.NoItemFlags)
                header.setForeground(QColor(COLORS["muted"]))
                self.entry_list.addItem(header)
                last_section = section

            item = QListWidgetItem(f"  {entry['key']} = {entry['value']}")
            item.setData(Qt.UserRole, entry)
            item.setToolTip(f"{format_section_title(section)}  {entry['key']} = {entry['value']}")
            self.entry_list.addItem(item)
            if self._pending_key and entry["key"] == self._pending_key:
                pending_section = None if self._pending_section is None else normalize_section_name(self._pending_section)
                if pending_section is None and matched_item is None:
                    matched_item = item
                elif pending_section == section:
                    matched_item = item

        if matched_item is not None:
            bound_entry = matched_item.data(Qt.UserRole) or {}
            self.set_selected_section(normalize_section_name(bound_entry.get("section", "")))
            self.entry_list.setCurrentItem(matched_item)
            self._pending_key = ""
            self._pending_section = None

    def refresh_entry_list_from_current_file(self):
        self._entries = []
        file_path = self.get_current_file_path()
        if not file_path or not file_path.exists():
            self.refresh_section_options([])
            self.refresh_entry_list([])
            return
        try:
            self._entries = parse_key_value_lines(read_text_with_fallback(file_path).splitlines())
        except Exception:
            self._entries = []
        bindable_entries = get_marked_entries(self._entries)
        self.refresh_section_options(bindable_entries)
        self.refresh_entry_list(bindable_entries)

    def handle_entry_clicked(self, item):
        entry = item.data(Qt.UserRole)
        if not entry:
            return
        self.set_selected_section(normalize_section_name(entry.get("section", "")))
        key = entry.get("key", "")
        if key:
            self.key_edit.setText(str(key))

    def update_preview(self):
        if not self.ini_dir or not self.ini_dir.exists():
            self.preview_label.setText("预览值：请先选择 INI 文件夹")
            return
        file_value = self.get_current_file_value()
        key_value = self.key_edit.text().strip()
        section_value = self.get_selected_section()
        if not file_value:
            self.preview_label.setText("预览值：请选择 INI 文件")
            return
        if not key_value:
            self.preview_label.setText("预览值：请输入匹配文字")
            return
        file_path = self.get_current_file_path()
        if not file_path:
            self.preview_label.setText("预览值：未找到当前目标配置")
            return
        try:
            lines = read_text_with_fallback(file_path).splitlines()
        except Exception as exc:
            self.preview_label.setText(f"预览值：读取失败 - {exc}")
            return
        value = extract_value_from_lines(lines, key_value, section_value)
        if value is None:
            self.preview_label.setText("预览值：未找到匹配项")
            return
        section_text = "全部小节"
        if section_value is not None:
            section_text = format_section_title(section_value)
        self.preview_label.setText(f"预览值：{section_text}  {key_value} = {value}")

    def get_result(self):
        ini_dir_value = str(self.ini_dir) if self.ini_dir else ""
        if self._clear_requested:
            return {"ini_dir": ini_dir_value, "binding": None}
        file_value = self.get_current_file_value()
        key_value = self.key_edit.text().strip()
        section_value = self.get_selected_section()
        if not file_value or not key_value:
            return {"ini_dir": ini_dir_value, "binding": None}
        binding = {"file": file_value, "key": key_value}
        if section_value is not None:
            binding["section"] = normalize_section_name(section_value)
        return {"ini_dir": ini_dir_value, "binding": binding}


class ResultItemBindingDialog(BindingDialog):
    def __init__(self, field_title, ini_dir, current_binding=None, current_display_name="", parent=None, fixed_ini_path=None):
        self._pending_display_name = str(current_display_name or "").strip()
        super().__init__(field_title, ini_dir, current_binding, parent, fixed_ini_path=fixed_ini_path)
        self.display_name_edit = QLineEdit(self._pending_display_name)
        self.display_name_edit.setPlaceholderText("设置这条分项结果在界面上的显示名称")
        self.form.insertRow(4, "显示名称", self.display_name_edit)

    def get_result(self):
        result = super().get_result()
        result["display_name"] = self.display_name_edit.text().strip()
        return result


class RabbitCountBindingDialog(BindingDialog):
    def __init__(self, field_title, ini_dir, current_binding=None, parent=None):
        self._pending_total_key = current_binding.get("total_key", "") if current_binding else ""
        self._active_key_target = "count"
        super().__init__(field_title, ini_dir, current_binding, parent)
        key_label = self.form.labelForField(self.key_edit)
        if key_label is not None:
            key_label.setText("点检匹配文字")
        self.total_key_edit = QLineEdit(self._pending_total_key)
        self.total_key_edit.setPlaceholderText("输入总数对应的匹配文字，例如 总数")
        self.form.insertRow(4, "总数匹配文字", self.total_key_edit)
        self.key_edit.installEventFilter(self)
        self.total_key_edit.installEventFilter(self)
        self.total_key_edit.textChanged.connect(self.update_preview)
        self.update_preview()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.FocusIn, QEvent.MouseButtonPress):
            if obj is self.total_key_edit:
                self._active_key_target = "total"
            elif obj is self.key_edit:
                self._active_key_target = "count"
        return super().eventFilter(obj, event)

    def handle_entry_clicked(self, item):
        entry = item.data(Qt.UserRole)
        if not entry:
            return
        self.set_selected_section(normalize_section_name(entry.get("section", "")))
        key = str(entry.get("key", "") or "")
        if not key:
            return
        if getattr(self, "_active_key_target", "count") == "total":
            self.total_key_edit.setText(key)
        else:
            self.key_edit.setText(key)

    def update_preview(self):
        if not hasattr(self, "total_key_edit"):
            super().update_preview()
            return
        if not self.ini_dir or not self.ini_dir.exists():
            self.preview_label.setText("预览值：请先选择 INI 文件夹")
            return
        file_value = self.get_current_file_value()
        count_key = self.key_edit.text().strip()
        total_key = self.total_key_edit.text().strip()
        section_value = self.get_selected_section()
        if not file_value:
            self.preview_label.setText("预览值：请选择 INI 文件")
            return
        if not count_key:
            self.preview_label.setText("预览值：请输入点检匹配文字")
            return
        if not total_key:
            self.preview_label.setText("预览值：请输入总数匹配文字")
            return
        file_path = self.get_current_file_path()
        if not file_path:
            self.preview_label.setText("预览值：未找到当前目标配置")
            return
        try:
            lines = read_text_with_fallback(file_path).splitlines()
        except Exception as exc:
            self.preview_label.setText(f"预览值：读取失败 - {exc}")
            return
        count_value = extract_value_from_lines(lines, count_key, section_value)
        total_value = extract_value_from_lines(lines, total_key, section_value)
        if count_value is None and total_value is None:
            self.preview_label.setText("预览值：未找到点检匹配项和总数匹配项")
            return
        if count_value is None:
            self.preview_label.setText("预览值：未找到点检匹配项")
            return
        if total_value is None:
            self.preview_label.setText("预览值：未找到总数匹配项")
            return
        section_text = "全部小节"
        if section_value is not None:
            section_text = format_section_title(section_value)
        self.preview_label.setText(f"预览值：{section_text}  {count_key}/{total_key} = {count_value}/{total_value}")

    def get_result(self):
        result = super().get_result()
        binding = result.get("binding")
        if binding is not None:
            total_key = self.total_key_edit.text().strip()
            if not total_key:
                return {"ini_dir": result.get("ini_dir", ""), "binding": None}
            binding["total_key"] = total_key
        return result


class TileTitleLinkDialog(QDialog):
    def __init__(self, field_title, options, current_link="", current_display_name="", current_status_links=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"标题绑定设置 - {field_title}")
        self.setModal(True)
        self.resize(480, 360)
        apply_compact_dialog_style(self, 8)
        self._clear_requested = False
        self.options = list(options or [])
        self.current_status_links = {str(field_id) for field_id in (current_status_links or []) if str(field_id).strip()}

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)
        layout.addLayout(form)

        self.link_combo = QComboBox()
        self.link_combo.addItem("不绑定左侧分项", "")
        selected_index = 0
        for index, (field_id, display_text) in enumerate(self.options, start=1):
            self.link_combo.addItem(display_text, field_id)
            if field_id == current_link:
                selected_index = index
        self.link_combo.setCurrentIndex(selected_index)
        form.addRow("绑定到左侧", self.link_combo)

        self.display_name_edit = QLineEdit(str(current_display_name or "").strip())
        self.display_name_edit.setPlaceholderText("不填则按左侧绑定或默认标题显示")
        form.addRow("显示名称", self.display_name_edit)

        self.status_link_list = QListWidget()
        self.status_link_list.setMinimumHeight(105)
        self.status_link_list.setStyleSheet(
            f"""
            QListWidget {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                outline: none;
            }}
            QListWidget::item {{
                padding: 3px 6px;
                border-bottom: 1px solid #143457;
            }}
            """
        )
        for field_id, display_text in self.options:
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, field_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if field_id in self.current_status_links else Qt.Unchecked)
            self.status_link_list.addItem(item)
        form.addRow("结果状态绑定", self.status_link_list)

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(52)
        self.preview_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                padding: 6px;
            }}
            """
        )
        form.addRow("预览结果", self.preview_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        clear_button = QPushButton("清除绑定")
        buttons.addButton(clear_button, QDialogButtonBox.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        clear_button.clicked.connect(self.clear_binding)
        layout.addWidget(buttons)

        self.link_combo.currentIndexChanged.connect(self.update_preview)
        self.display_name_edit.textChanged.connect(self.update_preview)
        self.status_link_list.itemChanged.connect(self.update_preview)
        self.update_preview()

    def clear_binding(self):
        self._clear_requested = True
        self.accept()

    def update_preview(self):
        status_names = self.get_selected_status_link_names()
        custom_name = self.display_name_edit.text().strip()
        if custom_name:
            title_text = f"右侧标题会显示为：{custom_name}\n当前已启用自定义名称，优先级高于左侧联动。"
            status_text = self.format_status_link_preview(status_names)
            self.preview_label.setText(f"{title_text}\n{status_text}")
            return
        field_id = self.link_combo.currentData()
        if not field_id:
            title_text = "当前标题保持右侧自己的默认名称，不跟左侧分项联动。"
            status_text = self.format_status_link_preview(status_names)
            self.preview_label.setText(f"{title_text}\n{status_text}")
            return
        display_text = self.link_combo.currentText().strip()
        title_text = f"右侧标题会显示为：{display_text}\n后续左侧这条名称改动时，这里也会同步更新。"
        status_text = self.format_status_link_preview(status_names)
        self.preview_label.setText(f"{title_text}\n{status_text}")

    def get_selected_status_links(self):
        selected = []
        for index in range(self.status_link_list.count()):
            item = self.status_link_list.item(index)
            if item.checkState() == Qt.Checked:
                field_id = str(item.data(Qt.UserRole) or "").strip()
                if field_id:
                    selected.append(field_id)
        return selected

    def get_selected_status_link_names(self):
        selected = []
        for index in range(self.status_link_list.count()):
            item = self.status_link_list.item(index)
            if item.checkState() == Qt.Checked:
                selected.append(item.text().strip())
        return selected

    def format_status_link_preview(self, status_names):
        if not status_names:
            return "未绑定结果状态；右侧标题不额外汇总 OK/NG。"
        return f"结果状态绑定：{', '.join(status_names)}；任一项 NG 则显示 NG，全部 OK 才显示 OK。"

    def get_result(self):
        if self._clear_requested:
            return {"linked_field_id": None, "display_name": None, "status_linked_field_ids": []}
        return {
            "linked_field_id": self.link_combo.currentData() or "",
            "display_name": self.display_name_edit.text().strip(),
            "status_linked_field_ids": self.get_selected_status_links(),
        }


class ResultItemsManagerDialog(QDialog):
    def __init__(self, current_items, current_font_size=0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("分项结果管理")
        self.setModal(True)
        self.resize(640, 430)
        apply_compact_dialog_style(self, 8)
        self._items = [dict(item) for item in (current_items or [])]
        try:
            self._font_size = max(0, min(int(current_font_size or 0), 24))
        except Exception:
            self._font_size = 0
        for item in self._items:
            item.setdefault("title", "")
            item.setdefault("limit_enabled", False)
            item.setdefault("lower_limit", "")
            item["lower_operator"] = normalize_lower_limit_operator(item.get("lower_operator"))
            item.setdefault("upper_limit", "")
            item["upper_operator"] = normalize_upper_limit_operator(item.get("upper_operator"))

        layout = QVBoxLayout(self)
        tip = QLabel("可添加或删除左侧分项结果；条目变多后主界面会自动缩小每条显示。")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color: {COLORS['muted']};")
        layout.addWidget(tip)

        body = QHBoxLayout()
        body.setSpacing(8)
        layout.addLayout(body, 1)

        self.item_list = QListWidget()
        self.item_list.setStyleSheet(
            f"""
            QListWidget {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                outline: none;
            }}
            QListWidget::item {{
                padding: 4px 6px;
                border-bottom: 1px solid #143457;
            }}
            QListWidget::item:selected {{
                background: #1E4D8D;
            }}
            """
        )
        body.addWidget(self.item_list, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(8)
        body.addLayout(right_col, 1)

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        right_col.addWidget(form_host)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("分项名称")
        form.addRow("子功能", self.title_edit)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(0, 24)
        self.font_size_spin.setSpecialValueText("自动")
        self.font_size_spin.setValue(self._font_size)
        self.font_size_spin.setMaximumWidth(86)
        form.addRow("字体大小", self.font_size_spin)

        self.limit_enabled_check = QCheckBox("启用上下限判断")
        form.addRow("上下限", self.limit_enabled_check)

        self.lower_limit_edit = QLineEdit()
        self.lower_limit_edit.setPlaceholderText("例如 0.01")
        self.lower_operator_combo = QComboBox()
        self.lower_operator_combo.addItem("≤", "<=")
        self.lower_operator_combo.addItem("<", "<")
        self.lower_operator_combo.setMaximumWidth(52)
        lower_limit_host = QWidget()
        lower_limit_layout = QHBoxLayout(lower_limit_host)
        lower_limit_layout.setContentsMargins(0, 0, 0, 0)
        lower_limit_layout.setSpacing(6)
        lower_limit_layout.addWidget(self.lower_limit_edit, 1)
        lower_limit_layout.addWidget(self.lower_operator_combo, 0)
        form.addRow("下限值", lower_limit_host)

        self.upper_limit_edit = QLineEdit()
        self.upper_limit_edit.setPlaceholderText("例如 0.08")
        self.upper_operator_combo = QComboBox()
        self.upper_operator_combo.addItem("≥", ">=")
        self.upper_operator_combo.addItem(">", ">")
        self.upper_operator_combo.setMaximumWidth(52)
        upper_limit_host = QWidget()
        upper_limit_layout = QHBoxLayout(upper_limit_host)
        upper_limit_layout.setContentsMargins(0, 0, 0, 0)
        upper_limit_layout.setSpacing(6)
        upper_limit_layout.addWidget(self.upper_limit_edit, 1)
        upper_limit_layout.addWidget(self.upper_operator_combo, 0)
        form.addRow("上限值", upper_limit_host)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        add_button = QPushButton("新增")
        delete_button = QPushButton("删除")
        button_row.addWidget(add_button)
        button_row.addWidget(delete_button)
        button_row.addStretch(1)
        right_col.addLayout(button_row)
        right_col.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        add_button.clicked.connect(self.add_item)
        delete_button.clicked.connect(self.delete_selected_item)
        self.item_list.currentRowChanged.connect(self.handle_current_row_changed)
        self.title_edit.textChanged.connect(self.handle_title_changed)
        self.font_size_spin.valueChanged.connect(self.handle_font_size_changed)
        self.limit_enabled_check.toggled.connect(self.handle_limit_enabled_changed)
        self.lower_limit_edit.textChanged.connect(self.handle_lower_limit_changed)
        self.upper_limit_edit.textChanged.connect(self.handle_upper_limit_changed)
        self.lower_operator_combo.currentIndexChanged.connect(self.handle_lower_operator_changed)
        self.upper_operator_combo.currentIndexChanged.connect(self.handle_upper_operator_changed)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.refresh_list()

    def refresh_list(self):
        self.item_list.clear()
        for index, item in enumerate(self._items, start=1):
            title = str(item.get("title", "") or "").strip()
            limit_tag = " [上下限]" if item.get("limit_enabled") else ""
            list_item = QListWidgetItem(f"{index} {title}{limit_tag}")
            list_item.setData(Qt.UserRole, item.get("id", ""))
            self.item_list.addItem(list_item)
        if self.item_list.count() > 0 and self.item_list.currentRow() < 0:
            self.item_list.setCurrentRow(self.item_list.count() - 1)
        if self.item_list.count() == 0:
            self.set_editor_enabled(False)
            self.load_item_into_editor(None)

    def add_item(self):
        text, ok = QInputDialog.getText(self, "新增分项", "请输入分项名称：")
        title = str(text or "").strip()
        if not ok or not title:
            return
        self._items.append(
            {
                "id": "",
                "title": title,
                "limit_enabled": False,
                "lower_limit": "",
                "upper_limit": "",
                "lower_operator": DEFAULT_LOWER_LIMIT_OPERATOR,
                "upper_operator": DEFAULT_UPPER_LIMIT_OPERATOR,
            }
        )
        self.refresh_list()
        self.item_list.setCurrentRow(len(self._items) - 1)

    def set_editor_enabled(self, enabled):
        for widget in (
            self.title_edit,
            self.limit_enabled_check,
            self.lower_limit_edit,
            self.lower_operator_combo,
            self.upper_limit_edit,
            self.upper_operator_combo,
        ):
            widget.setEnabled(enabled)

    def set_combo_current_data(self, combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def load_item_into_editor(self, item):
        self.title_edit.blockSignals(True)
        self.limit_enabled_check.blockSignals(True)
        self.lower_limit_edit.blockSignals(True)
        self.lower_operator_combo.blockSignals(True)
        self.upper_limit_edit.blockSignals(True)
        self.upper_operator_combo.blockSignals(True)
        if item is None:
            self.title_edit.setText("")
            self.limit_enabled_check.setChecked(False)
            self.lower_limit_edit.setText("")
            self.set_combo_current_data(self.lower_operator_combo, DEFAULT_LOWER_LIMIT_OPERATOR)
            self.upper_limit_edit.setText("")
            self.set_combo_current_data(self.upper_operator_combo, DEFAULT_UPPER_LIMIT_OPERATOR)
        else:
            self.title_edit.setText(str(item.get("title", "") or "").strip())
            self.limit_enabled_check.setChecked(bool(item.get("limit_enabled")))
            self.lower_limit_edit.setText(str(item.get("lower_limit", "") or "").strip())
            self.set_combo_current_data(self.lower_operator_combo, normalize_lower_limit_operator(item.get("lower_operator")))
            self.upper_limit_edit.setText(str(item.get("upper_limit", "") or "").strip())
            self.set_combo_current_data(self.upper_operator_combo, normalize_upper_limit_operator(item.get("upper_operator")))
        self.title_edit.blockSignals(False)
        self.limit_enabled_check.blockSignals(False)
        self.lower_limit_edit.blockSignals(False)
        self.lower_operator_combo.blockSignals(False)
        self.upper_limit_edit.blockSignals(False)
        self.upper_operator_combo.blockSignals(False)
        self.update_limit_inputs_enabled()

    def update_limit_inputs_enabled(self):
        enabled = self.limit_enabled_check.isChecked() and self.limit_enabled_check.isEnabled()
        self.lower_limit_edit.setEnabled(enabled)
        self.lower_operator_combo.setEnabled(enabled)
        self.upper_limit_edit.setEnabled(enabled)
        self.upper_operator_combo.setEnabled(enabled)

    def get_current_item(self):
        row = self.item_list.currentRow()
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]

    def handle_current_row_changed(self, row):
        if row < 0 or row >= len(self._items):
            self.set_editor_enabled(False)
            self.load_item_into_editor(None)
            return
        self.set_editor_enabled(True)
        self.load_item_into_editor(self._items[row])

    def handle_title_changed(self, text):
        item = self.get_current_item()
        if item is None:
            return
        item["title"] = str(text or "").strip()
        row = self.item_list.currentRow()
        self.refresh_list()
        self.item_list.setCurrentRow(row)

    def handle_font_size_changed(self, value):
        try:
            self._font_size = max(0, min(int(value), 24))
        except Exception:
            self._font_size = 0

    def handle_limit_enabled_changed(self, checked):
        item = self.get_current_item()
        if item is None:
            return
        item["limit_enabled"] = bool(checked)
        self.update_limit_inputs_enabled()
        row = self.item_list.currentRow()
        self.refresh_list()
        self.item_list.setCurrentRow(row)

    def handle_lower_limit_changed(self, text):
        item = self.get_current_item()
        if item is None:
            return
        item["lower_limit"] = str(text or "").strip()

    def handle_lower_operator_changed(self, *_args):
        item = self.get_current_item()
        if item is None:
            return
        item["lower_operator"] = normalize_lower_limit_operator(self.lower_operator_combo.currentData())

    def handle_upper_limit_changed(self, text):
        item = self.get_current_item()
        if item is None:
            return
        item["upper_limit"] = str(text or "").strip()

    def handle_upper_operator_changed(self, *_args):
        item = self.get_current_item()
        if item is None:
            return
        item["upper_operator"] = normalize_upper_limit_operator(self.upper_operator_combo.currentData())

    def delete_selected_item(self):
        row = self.item_list.currentRow()
        if row < 0 or row >= len(self._items):
            return
        self._items.pop(row)
        self.refresh_list()
        if self.item_list.count() > 0:
            self.item_list.setCurrentRow(min(row, self.item_list.count() - 1))

    def get_result(self):
        normalized = []
        for item in self._items:
            title = str(item.get("title", "") or "").strip()
            if not title:
                continue
            normalized.append(
                {
                    "id": item.get("id", ""),
                    "title": title,
                    "limit_enabled": bool(item.get("limit_enabled")),
                    "lower_limit": str(item.get("lower_limit", "") or "").strip(),
                    "lower_operator": normalize_lower_limit_operator(item.get("lower_operator")),
                    "upper_limit": str(item.get("upper_limit", "") or "").strip(),
                    "upper_operator": normalize_upper_limit_operator(item.get("upper_operator")),
                }
            )
        return normalized

    def get_font_size(self):
        return self._font_size


class IniFileSelectDialog(QDialog):
    def __init__(self, field_title, ini_dir, current_file="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"INI文件选择 - {field_title}")
        self.setModal(True)
        self.resize(560, 220)
        apply_compact_dialog_style(self, 8)
        self._clear_requested = False
        self.ini_dir = Path(ini_dir) if ini_dir else None
        self._pending_file = current_file or ""

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)
        layout.addLayout(form)

        folder_host = QWidget()
        folder_layout = QHBoxLayout(folder_host)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(6)
        self.folder_edit = QLineEdit(str(self.ini_dir) if self.ini_dir else "")
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("请选择 INI 文件夹")
        self.folder_edit.setStyleSheet(f"color: {COLORS['muted']};")
        folder_layout.addWidget(self.folder_edit, 1)
        browse_button = QPushButton("选择...")
        browse_button.clicked.connect(self.choose_folder)
        folder_layout.addWidget(browse_button)
        form.addRow("INI目录", folder_host)

        self.file_combo = QComboBox()
        form.addRow("INI文件", self.file_combo)

        self.preview_label = QLabel("用途：该文件将按当前编号查找对应的目标配置文件名。")
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(42)
        self.preview_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                padding: 8px;
            }}
            """
        )
        form.addRow("说明", self.preview_label)

        self.file_combo.currentIndexChanged.connect(self.update_preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        clear_button = QPushButton("清除选择")
        buttons.addButton(clear_button, QDialogButtonBox.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        clear_button.clicked.connect(self.clear_binding)
        layout.addWidget(buttons)

        self.refresh_ini_files()

    def clear_binding(self):
        self._clear_requested = True
        self.accept()

    def choose_folder(self):
        start_dir = str(self.ini_dir or Path.cwd())
        selected = QFileDialog.getExistingDirectory(self, "选择 INI 文件夹", start_dir)
        if not selected:
            return
        self.ini_dir = Path(selected)
        self.folder_edit.setText(str(self.ini_dir))
        self.refresh_ini_files()

    def refresh_ini_files(self):
        self.file_combo.clear()
        if not self.ini_dir or not self.ini_dir.exists():
            self.file_combo.addItem("请先选择 INI 文件夹", "")
            self.update_preview()
            return

        ini_files = sorted(str(path.relative_to(self.ini_dir)) for path in self.ini_dir.rglob("*.ini"))
        if not ini_files:
            self.file_combo.addItem("该文件夹下没有 INI 文件", "")
            self.update_preview()
            return

        self.file_combo.addItem("请选择 INI 文件", "")
        for rel_path in ini_files:
            self.file_combo.addItem(rel_path, rel_path)

        if self._pending_file:
            idx = self.file_combo.findData(self._pending_file)
            if idx >= 0:
                self.file_combo.setCurrentIndex(idx)
            self._pending_file = ""
        self.update_preview()

    def update_preview(self, *_args):
        file_value = self.file_combo.currentData()
        if not self.ini_dir or not self.ini_dir.exists():
            self.preview_label.setText("用途：请选择 INI 文件夹。")
            return
        if not file_value:
            self.preview_label.setText("用途：请选择一个给其他数据更新用的编号映射 INI。")
            return
        self.preview_label.setText(
            "用途：程序会用当前编号，去这个 INI 里查找同名键，\n"
            "并把读取到的值当作目标配置文件名，供左侧结果区和右侧图像/曲线刷新使用。\n"
            f"当前文件：{file_value}"
        )

    def get_result(self):
        ini_dir_value = str(self.ini_dir) if self.ini_dir else ""
        if self._clear_requested:
            return {"ini_dir": ini_dir_value, "file": None}
        file_value = self.file_combo.currentData()
        if not file_value:
            return {"ini_dir": ini_dir_value, "file": None}
        return {"ini_dir": ini_dir_value, "file": file_value}


class OnlineSnBindingDialog(BindingDialog):
    def __init__(self, field_title, ini_dir, current_binding=None, parent=None):
        self._pending_lookup_file = current_binding.get("sn_lookup_file", "") if current_binding else ""
        self._pending_lookup_key = current_binding.get("sn_lookup_key", "") if current_binding else ""
        self._pending_lookup_section = current_binding.get("sn_lookup_section") if current_binding and "sn_lookup_section" in current_binding else None
        self._lookup_entries = []
        super().__init__(field_title, ini_dir, current_binding, parent)
        self.resize(600, 650)
        apply_compact_dialog_style(self, 8)
        self.form.setSpacing(8)
        if self.layout():
            self.layout().setSpacing(6)
        self.setStyleSheet(
            """
            QDialog, QLabel, QComboBox, QLineEdit, QPushButton, QListWidget {
                font-family: SimSun;
                font-size: 8pt;
            }
            QComboBox, QLineEdit, QPushButton {
                min-height: 18px;
            }
            """
        )
        self.preview_label.setMinimumHeight(28)
        self.entry_list.setMinimumHeight(84)
        self.key_edit.setPlaceholderText("匹配文字")
        self.entry_list.setStyleSheet(
            f"""
            QListWidget {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                outline: none;
            }}
            QListWidget::item {{
                padding: 2px 5px;
                border-bottom: 1px solid #143457;
            }}
            QListWidget::item:selected {{
                background: #1E4D8D;
            }}
            """
        )

        section_title = QLabel("编号映射读取配置")
        section_title.setStyleSheet(f"color: {COLORS['muted']};")
        self.layout().insertWidget(self.layout().count() - 1, section_title)

        lookup_form_host = QWidget()
        self.lookup_form = QFormLayout(lookup_form_host)
        self.lookup_form.setContentsMargins(0, 0, 0, 0)
        self.lookup_form.setSpacing(8)

        self.lookup_file_combo = QComboBox()
        self.lookup_form.addRow("编号映射INI", self.lookup_file_combo)

        self.lookup_section_combo = QComboBox()
        self.lookup_form.addRow("匹配小节", self.lookup_section_combo)

        self.lookup_key_edit = QLineEdit()
        self.lookup_key_edit.setPlaceholderText("匹配文字")
        self.lookup_key_edit.setText(self._pending_lookup_key)
        self.lookup_form.addRow("匹配文字", self.lookup_key_edit)

        self.lookup_preview_label = QLabel("预览值：")
        self.lookup_preview_label.setWordWrap(True)
        self.lookup_preview_label.setMinimumHeight(28)
        self.lookup_preview_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                padding: 6px;
            }}
            """
        )
        self.lookup_form.addRow("预览结果", self.lookup_preview_label)
        self.layout().insertWidget(self.layout().count() - 1, lookup_form_host)

        lookup_list_title = QLabel("编号映射INI 内容")
        lookup_list_title.setStyleSheet(f"color: {COLORS['muted']};")
        self.layout().insertWidget(self.layout().count() - 1, lookup_list_title)

        self.lookup_entry_list = QListWidget()
        self.lookup_entry_list.setMinimumHeight(84)
        self.lookup_entry_list.setStyleSheet(
            f"""
            QListWidget {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                outline: none;
            }}
            QListWidget::item {{
                padding: 2px 5px;
                border-bottom: 1px solid #143457;
            }}
            QListWidget::item:selected {{
                background: #1E4D8D;
            }}
            """
        )
        self.layout().insertWidget(self.layout().count() - 1, self.lookup_entry_list)

        self.lookup_file_combo.currentIndexChanged.connect(self.handle_lookup_file_changed)
        self.lookup_section_combo.currentIndexChanged.connect(self.update_lookup_preview)
        self.lookup_key_edit.textChanged.connect(self.update_lookup_preview)
        self.lookup_entry_list.itemClicked.connect(self.handle_lookup_entry_clicked)
        self.refresh_lookup_files()

    def refresh_ini_files(self):
        super().refresh_ini_files()
        if hasattr(self, "lookup_file_combo"):
            self.refresh_lookup_files()

    def refresh_lookup_files(self):
        current_value = self.lookup_file_combo.currentData() if self.lookup_file_combo.count() else ""
        self.lookup_file_combo.blockSignals(True)
        self.lookup_file_combo.clear()
        self.lookup_file_combo.addItem("不额外指定", "")
        if self.ini_dir and self.ini_dir.exists():
            ini_files = sorted(str(path.relative_to(self.ini_dir)) for path in self.ini_dir.rglob("*.ini"))
            for rel_path in ini_files:
                self.lookup_file_combo.addItem(rel_path, rel_path)

        target_value = self._pending_lookup_file or current_value
        if target_value:
            index = self.lookup_file_combo.findData(target_value)
            if index >= 0:
                self.lookup_file_combo.setCurrentIndex(index)
        self.lookup_file_combo.blockSignals(False)
        self._pending_lookup_file = ""
        self.refresh_lookup_entry_list_from_current_file()
        self.update_lookup_preview()

    def handle_lookup_file_changed(self, *_args):
        self.refresh_lookup_entry_list_from_current_file()
        self.update_lookup_preview()

    def refresh_lookup_section_options(self, entries):
        current_data = self.get_lookup_selected_section()
        self.lookup_section_combo.blockSignals(True)
        self.lookup_section_combo.clear()
        self.lookup_section_combo.addItem("全部小节（不限定）", None)

        has_root_entries = False
        seen_sections = set()
        for entry in entries:
            section = normalize_section_name(entry["section"])
            if section:
                if section not in seen_sections:
                    seen_sections.add(section)
                    self.lookup_section_combo.addItem(format_section_title(section), section)
            else:
                has_root_entries = True

        if has_root_entries:
            self.lookup_section_combo.addItem(format_section_title(""), "")

        if self._pending_lookup_section is not None:
            self.set_lookup_selected_section(normalize_section_name(self._pending_lookup_section))
        else:
            self.set_lookup_selected_section(current_data)
        self.lookup_section_combo.blockSignals(False)

    def set_lookup_selected_section(self, section_value):
        for index in range(self.lookup_section_combo.count()):
            if self.lookup_section_combo.itemData(index) == section_value:
                self.lookup_section_combo.setCurrentIndex(index)
                return
        if self.lookup_section_combo.count():
            self.lookup_section_combo.setCurrentIndex(0)

    def get_lookup_selected_section(self):
        if self.lookup_section_combo.count() == 0:
            return None
        return self.lookup_section_combo.currentData()

    def refresh_lookup_entry_list(self, entries):
        self.lookup_entry_list.clear()
        if not entries:
            placeholder = QListWidgetItem("当前没有带 ### 标记的可绑定键值行")
            placeholder.setFlags(Qt.NoItemFlags)
            self.lookup_entry_list.addItem(placeholder)
            return

        matched_item = None
        last_section = object()
        for entry in entries:
            section = normalize_section_name(entry["section"])
            if section != last_section:
                header = QListWidgetItem(format_section_title(section))
                header.setFlags(Qt.NoItemFlags)
                header.setForeground(QColor(COLORS["muted"]))
                self.lookup_entry_list.addItem(header)
                last_section = section

            item = QListWidgetItem(f"  {entry['key']} = {entry['value']}")
            item.setData(Qt.UserRole, entry)
            item.setToolTip(f"{format_section_title(section)}  {entry['key']} = {entry['value']}")
            self.lookup_entry_list.addItem(item)
            if self._pending_lookup_key and entry["key"] == self._pending_lookup_key:
                pending_section = None if self._pending_lookup_section is None else normalize_section_name(self._pending_lookup_section)
                if pending_section is None and matched_item is None:
                    matched_item = item
                elif pending_section == section:
                    matched_item = item

        if matched_item is not None:
            bound_entry = matched_item.data(Qt.UserRole) or {}
            self.set_lookup_selected_section(normalize_section_name(bound_entry.get("section", "")))
            self.lookup_entry_list.setCurrentItem(matched_item)
            self._pending_lookup_key = ""
            self._pending_lookup_section = None

    def refresh_lookup_entry_list_from_current_file(self):
        self._lookup_entries = []
        if not self.ini_dir or not self.ini_dir.exists():
            self.refresh_lookup_section_options([])
            self.refresh_lookup_entry_list([])
            return
        file_value = self.lookup_file_combo.currentData()
        if not file_value:
            self.refresh_lookup_section_options([])
            self.refresh_lookup_entry_list([])
            return
        file_path = self.ini_dir / file_value
        try:
            self._lookup_entries = parse_key_value_lines(read_text_with_fallback(file_path).splitlines())
        except Exception:
            self._lookup_entries = []
        bindable_entries = get_marked_entries(self._lookup_entries)
        self.refresh_lookup_section_options(bindable_entries)
        self.refresh_lookup_entry_list(bindable_entries)

    def handle_lookup_entry_clicked(self, item):
        entry = item.data(Qt.UserRole)
        if not entry:
            return
        self.set_lookup_selected_section(normalize_section_name(entry.get("section", "")))
        key = entry.get("key", "")
        if key:
            self.lookup_key_edit.setText(str(key))

    def update_lookup_preview(self, *_args):
        lookup_file = self.lookup_file_combo.currentData()
        section_value = self.get_lookup_selected_section()
        key_value = self.lookup_key_edit.text().strip()
        if not self.ini_dir or not self.ini_dir.exists():
            self.lookup_preview_label.setText("预览值：请先选择 INI 文件夹")
            return
        if not lookup_file:
            self.lookup_preview_label.setText("预览值：不额外指定时，下方结果区继续按各自绑定里的 INI 文件读取。")
            return
        if not key_value:
            self.lookup_preview_label.setText("预览值：请输入匹配文字")
            return
        file_path = self.ini_dir / lookup_file
        try:
            lines = read_text_with_fallback(file_path).splitlines()
        except Exception as exc:
            self.lookup_preview_label.setText(f"预览值：读取失败 - {exc}")
            return
        value = extract_value_from_lines(lines, key_value, section_value)
        if value is None:
            self.lookup_preview_label.setText("预览值：未找到匹配项")
            return
        section_text = "全部小节"
        if section_value is not None:
            section_text = format_section_title(section_value)
        target_text = clean_path_text(value)
        target_path = Path(target_text) if target_text else Path("")
        if target_text and not target_path.suffix:
            target_path = target_path.with_suffix(".ini")
        target_display = str(target_path) if target_text else ""
        self.lookup_preview_label.setText(
            f"预览值：{section_text}  {key_value} = {value}\n"
            f"目标配置文件名：{target_display}"
        )

    def get_result(self):
        result = super().get_result()
        binding = result.get("binding")
        if not binding:
            return result
        lookup_file = self.lookup_file_combo.currentData() if hasattr(self, "lookup_file_combo") else ""
        lookup_key = self.lookup_key_edit.text().strip() if hasattr(self, "lookup_key_edit") else ""
        lookup_section = self.get_lookup_selected_section() if hasattr(self, "lookup_section_combo") else None
        if lookup_file:
            binding["sn_lookup_file"] = lookup_file
            if lookup_key:
                binding["sn_lookup_key"] = lookup_key
            else:
                binding.pop("sn_lookup_key", None)
            if lookup_section is not None:
                binding["sn_lookup_section"] = normalize_section_name(lookup_section)
            else:
                binding.pop("sn_lookup_section", None)
        else:
            binding.pop("sn_lookup_file", None)
            binding.pop("sn_lookup_key", None)
            binding.pop("sn_lookup_section", None)
        return result


class ImageBindingDialog(QDialog):
    def __init__(self, field_title, ini_dir, current_binding=None, parent=None, mode="image", fixed_ini_path=None):
        super().__init__(parent)
        self.mode = mode
        title_prefix = "图片绑定设置" if self.mode == "image" else "CSV曲线绑定设置"
        self.setWindowTitle(f"{title_prefix} - {field_title}")
        self.setModal(True)
        self.resize(560, 420)
        self.setMinimumSize(500, 360)
        apply_compact_dialog_style(self, 8)
        self._clear_requested = False
        self.ini_dir = Path(ini_dir) if ini_dir else None
        self.fixed_ini_path = Path(fixed_ini_path) if fixed_ini_path else None
        self._pending_file = current_binding.get("file", "") if current_binding else ""
        self._entries = []
        self._preview_image_path = ""
        self._pending_series_index = current_binding.get("series_index", 0) if current_binding and self.mode != "image" else 0
        self._selected_series_index = None
        self.default_y_axis_name = current_binding.get("y_axis_name", "") if current_binding and self.mode != "image" else infer_curve_axis_name(field_title)
        default_axis_config = get_default_curve_y_axis_config(field_title)
        self._pending_y_axis_config = normalize_curve_y_axis_config(
            current_binding.get("y_axis_min", default_axis_config["min"]) if current_binding and self.mode != "image" else default_axis_config["min"],
            current_binding.get("y_axis_max", default_axis_config["max"]) if current_binding and self.mode != "image" else default_axis_config["max"],
            current_binding.get("y_axis_tick_interval", default_axis_config["interval"]) if current_binding and self.mode != "image" else default_axis_config["interval"],
            field_title,
        )
        try:
            self._pending_y_axis_font_size = int(current_binding.get("y_axis_font_size", 9)) if current_binding and self.mode != "image" else 9
        except Exception:
            self._pending_y_axis_font_size = 9
        self._pending_y_axis_font_size = max(4, min(self._pending_y_axis_font_size, 24))
        self.limit_csv_path = current_binding.get("limit_csv_path", "") if current_binding and self.mode != "image" else ""
        self._pending_limit_path_section = normalize_section_name(current_binding.get("limit_path_section", "")) if current_binding and self.mode != "image" else ""
        self._pending_limit_path_key = current_binding.get("limit_path_key", "") if current_binding and self.mode != "image" else ""
        self._pending_upper_limit_color = current_binding.get("upper_limit_color", "#FFB020") if current_binding and self.mode != "image" else "#FFB020"
        self._pending_lower_limit_color = current_binding.get("lower_limit_color", "#FF4D4F") if current_binding and self.mode != "image" else "#FF4D4F"
        self._pending_upper_limit_width = current_binding.get("upper_limit_width", 1) if current_binding and self.mode != "image" else 1
        self._pending_lower_limit_width = current_binding.get("lower_limit_width", 1) if current_binding and self.mode != "image" else 1
        self._pending_upper_limit_style = current_binding.get("upper_limit_style", "dash") if current_binding and self.mode != "image" else "dash"
        self._pending_lower_limit_style = current_binding.get("lower_limit_style", "dash") if current_binding and self.mode != "image" else "dash"
        self._pending_upper_limit_series_index = current_binding.get("upper_limit_series_index") if current_binding and self.mode != "image" else None
        self._pending_lower_limit_series_index = current_binding.get("lower_limit_series_index") if current_binding and self.mode != "image" else None
        self._limit_row_infos = []
        self._resolved_limit_csv_path = ""
        self.active_slot = "path"
        self.selection = {
            "path": {
                "section": normalize_section_name(current_binding.get("path_section", "")) if current_binding else "",
                "key": current_binding.get("path_key", "") if current_binding else "",
            },
            "limit": {
                "section": normalize_section_name(current_binding.get("limit_path_section", "")) if current_binding else "",
                "key": current_binding.get("limit_path_key", "") if current_binding else "",
            },
            "name": {
                "section": normalize_section_name(current_binding.get("name_section", "")) if current_binding else "",
                "key": current_binding.get("name_key", "") if current_binding else "",
            },
        }
        if self.mode != "image":
            self.selection["name"] = {"section": "", "key": ""}

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(6)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(
            """
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #06101B;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #2F7DD1;
                min-height: 28px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )
        outer_layout.addWidget(self.scroll_area, 1)

        scroll_widget = QWidget()
        self.scroll_area.setWidget(scroll_widget)

        layout = QVBoxLayout(scroll_widget)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(8)
        form = QFormLayout()
        form.setSpacing(8)
        layout.addLayout(form)

        folder_host = QWidget()
        folder_layout = QHBoxLayout(folder_host)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(6)
        self.folder_edit = QLineEdit(str(self.ini_dir) if self.ini_dir else "")
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("请选择 INI 文件夹")
        self.folder_edit.setStyleSheet(f"color: {COLORS['muted']};")
        folder_layout.addWidget(self.folder_edit, 1)
        self.folder_browse_button = QPushButton("选择...")
        self.folder_browse_button.clicked.connect(self.choose_folder)
        folder_layout.addWidget(self.folder_browse_button)
        form.addRow("INI目录", folder_host)

        self.file_combo = QComboBox()
        form.addRow("INI文件", self.file_combo)

        self.active_label = QLabel()
        self.active_label.setStyleSheet(f"color: {COLORS['muted']};")
        form.addRow("当前点击目标", self.active_label)

        if self.mode != "image":
            target_switch_host = QWidget()
            target_switch_layout = QHBoxLayout(target_switch_host)
            target_switch_layout.setContentsMargins(0, 0, 0, 0)
            target_switch_layout.setSpacing(8)
            self.target_path_button = QPushButton("主曲线CSV")
            self.target_path_button.setMinimumWidth(96)
            self.target_path_button.clicked.connect(lambda: self.set_active_slot("path"))
            target_switch_layout.addWidget(self.target_path_button, 0)
            self.target_limit_button = QPushButton("上下限CSV")
            self.target_limit_button.setMinimumWidth(96)
            self.target_limit_button.clicked.connect(lambda: self.set_active_slot("limit"))
            target_switch_layout.addWidget(self.target_limit_button, 0)
            target_switch_layout.addStretch(1)
            form.addRow("切换设置项", target_switch_host)

        path_host = QWidget()
        path_layout = QHBoxLayout(path_host)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("点击下方列表，把某一行设为图片路径键" if self.mode == "image" else "点击下方列表，把某一行设为主曲线CSV键")
        path_layout.addWidget(self.path_edit, 1)
        self.path_button = QPushButton("设为图片路径" if self.mode == "image" else "设为主曲线CSV")
        self.path_button.clicked.connect(lambda: self.set_active_slot("path"))
        path_layout.addWidget(self.path_button)
        form.addRow("图片路径键" if self.mode == "image" else "主曲线CSV键", path_host)

        limit_host = None
        if self.mode != "image":
            limit_host = QWidget()
            limit_layout = QHBoxLayout(limit_host)
            limit_layout.setContentsMargins(0, 0, 0, 0)
            limit_layout.setSpacing(8)
            self.limit_edit = QLineEdit()
            self.limit_edit.setReadOnly(True)
            self.limit_edit.setPlaceholderText("点击下方列表，把某一行设为上下限CSV键")
            limit_layout.addWidget(self.limit_edit, 1)
            self.limit_button = QPushButton("设为上下限CSV")
            self.limit_button.clicked.connect(lambda: self.set_active_slot("limit"))
            limit_layout.addWidget(self.limit_button)
            form.addRow("上下限CSV键", limit_host)
            self.path_button.hide()
            self.limit_button.hide()

        name_host = QWidget()
        name_layout = QHBoxLayout(name_host)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(8)
        self.name_edit = QLineEdit()
        self.name_edit.setReadOnly(True)
        self.name_edit.setPlaceholderText("可选：点击下方列表，把某一行设为图片文件名键" if self.mode == "image" else "可选：点击下方列表，把某一行设为CSV文件名键")
        name_layout.addWidget(self.name_edit, 1)
        self.name_button = QPushButton("设为图片名" if self.mode == "image" else "设为CSV名")
        self.name_button.clicked.connect(lambda: self.set_active_slot("name"))
        name_layout.addWidget(self.name_button)
        form.addRow("图片文件名键(可选)" if self.mode == "image" else "CSV文件名键(可选)", name_host)

        self.preview_label = QLabel("预览结果：")
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(52)
        self.preview_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                padding: 8px;
            }}
            """
        )
        form.addRow("预览结果", self.preview_label)

        if self.mode == "image":
            self.preview_image_label = QLabel("缩略图预览")
            self.preview_image_label.setAlignment(Qt.AlignCenter)
            self.preview_image_label.setMinimumSize(220, 104)
            self.preview_image_label.setStyleSheet(
                f"""
                QLabel {{
                    color: {COLORS['muted']};
                    background: #081421;
                    border: 1px solid {COLORS['blue_line']};
                }}
                """
            )
            form.addRow("图片预览", self.preview_image_label)
        else:
            self.y_axis_edit = QLineEdit(self.default_y_axis_name)
            self.y_axis_edit.setPlaceholderText("例如 亮度、斜率、电流")
            form.addRow("纵轴名称", self.y_axis_edit)

            y_axis_range_host = QWidget()
            y_axis_range_layout = QHBoxLayout(y_axis_range_host)
            y_axis_range_layout.setContentsMargins(0, 0, 0, 0)
            y_axis_range_layout.setSpacing(6)
            y_axis_range_layout.addWidget(QLabel("最低"))
            self.y_axis_min_spin = QDoubleSpinBox()
            self.y_axis_min_spin.setRange(-999999.0, 999999.0)
            self.y_axis_min_spin.setDecimals(3)
            self.y_axis_min_spin.setSingleStep(1.0)
            self.y_axis_min_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            self.y_axis_min_spin.setFixedWidth(66)
            self.y_axis_min_spin.setValue(self._pending_y_axis_config["min"])
            y_axis_range_layout.addWidget(self.y_axis_min_spin, 0)
            y_axis_range_layout.addWidget(QLabel("最高"))
            self.y_axis_max_spin = QDoubleSpinBox()
            self.y_axis_max_spin.setRange(-999999.0, 999999.0)
            self.y_axis_max_spin.setDecimals(3)
            self.y_axis_max_spin.setSingleStep(1.0)
            self.y_axis_max_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            self.y_axis_max_spin.setFixedWidth(66)
            self.y_axis_max_spin.setValue(self._pending_y_axis_config["max"])
            y_axis_range_layout.addWidget(self.y_axis_max_spin, 0)
            y_axis_range_layout.addWidget(QLabel("间距"))
            self.y_axis_interval_spin = QDoubleSpinBox()
            self.y_axis_interval_spin.setRange(0.001, 999999.0)
            self.y_axis_interval_spin.setDecimals(3)
            self.y_axis_interval_spin.setSingleStep(1.0)
            self.y_axis_interval_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            self.y_axis_interval_spin.setFixedWidth(66)
            self.y_axis_interval_spin.setValue(self._pending_y_axis_config["interval"])
            y_axis_range_layout.addWidget(self.y_axis_interval_spin, 0)
            y_axis_range_layout.addWidget(QLabel("字号"))
            self.y_axis_font_size_spin = QSpinBox()
            self.y_axis_font_size_spin.setRange(4, 24)
            self.y_axis_font_size_spin.setSingleStep(1)
            self.y_axis_font_size_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            self.y_axis_font_size_spin.setFixedWidth(44)
            self.y_axis_font_size_spin.setValue(self._pending_y_axis_font_size)
            self.y_axis_font_size_spin.lineEdit().editingFinished.connect(self.clamp_y_axis_font_size_input)
            y_axis_range_layout.addWidget(self.y_axis_font_size_spin, 0)
            y_axis_range_layout.addStretch(1)
            form.addRow("竖轴范围", y_axis_range_host)

            upper_limit_host = QWidget()
            upper_limit_layout = QHBoxLayout(upper_limit_host)
            upper_limit_layout.setContentsMargins(0, 0, 0, 0)
            upper_limit_layout.setSpacing(6)
            upper_limit_layout.addWidget(QLabel("颜色"))
            self.upper_limit_color_combo = QComboBox()
            upper_limit_layout.addWidget(self.upper_limit_color_combo, 0)
            upper_limit_layout.addWidget(QLabel("粗细"))
            self.upper_limit_width_spin = QSpinBox()
            self.upper_limit_width_spin.setRange(1, 8)
            self.upper_limit_width_spin.setValue(max(1, int(self._pending_upper_limit_width or 1)))
            self.upper_limit_width_spin.setMaximumWidth(54)
            upper_limit_layout.addWidget(self.upper_limit_width_spin, 0)
            upper_limit_layout.addWidget(QLabel("线型"))
            self.upper_limit_style_combo = QComboBox()
            self.upper_limit_style_combo.setMaximumWidth(68)
            upper_limit_layout.addWidget(self.upper_limit_style_combo, 0)
            upper_limit_layout.addWidget(QLabel("行数"))
            self.upper_limit_combo = QComboBox()
            upper_limit_layout.addWidget(self.upper_limit_combo, 1)
            form.addRow("上限行", upper_limit_host)

            lower_limit_host = QWidget()
            lower_limit_layout = QHBoxLayout(lower_limit_host)
            lower_limit_layout.setContentsMargins(0, 0, 0, 0)
            lower_limit_layout.setSpacing(6)
            lower_limit_layout.addWidget(QLabel("颜色"))
            self.lower_limit_color_combo = QComboBox()
            lower_limit_layout.addWidget(self.lower_limit_color_combo, 0)
            lower_limit_layout.addWidget(QLabel("粗细"))
            self.lower_limit_width_spin = QSpinBox()
            self.lower_limit_width_spin.setRange(1, 8)
            self.lower_limit_width_spin.setValue(max(1, int(self._pending_lower_limit_width or 1)))
            self.lower_limit_width_spin.setMaximumWidth(54)
            lower_limit_layout.addWidget(self.lower_limit_width_spin, 0)
            lower_limit_layout.addWidget(QLabel("线型"))
            self.lower_limit_style_combo = QComboBox()
            self.lower_limit_style_combo.setMaximumWidth(68)
            lower_limit_layout.addWidget(self.lower_limit_style_combo, 0)
            lower_limit_layout.addWidget(QLabel("行数"))
            self.lower_limit_combo = QComboBox()
            lower_limit_layout.addWidget(self.lower_limit_combo, 1)
            form.addRow("下限行", lower_limit_host)

            self.populate_limit_color_combo(self.upper_limit_color_combo, self._pending_upper_limit_color)
            self.populate_limit_color_combo(self.lower_limit_color_combo, self._pending_lower_limit_color)
            self.populate_line_style_combo(self.upper_limit_style_combo, self._pending_upper_limit_style)
            self.populate_line_style_combo(self.lower_limit_style_combo, self._pending_lower_limit_style)

        list_title = QLabel("当前 INI 内容")
        list_title.setStyleSheet(f"color: {COLORS['muted']};")
        layout.addWidget(list_title)

        self.entry_list = QListWidget()
        self.entry_list.setMinimumHeight(126)
        self.entry_list.setStyleSheet(
            f"""
            QListWidget {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                outline: none;
            }}
            QListWidget::item {{
                padding: 3px 6px;
                border-bottom: 1px solid #143457;
            }}
            QListWidget::item:selected {{
                background: #1E4D8D;
            }}
            """
        )
        layout.addWidget(self.entry_list, 1)

        if self.mode != "image":
            series_title = QLabel("CSV数据行预览")
            series_title.setStyleSheet(f"color: {COLORS['muted']};")
            layout.addWidget(series_title)

            hide_form_row(form, name_host)

            self.series_list = QListWidget()
            self.series_list.setMinimumHeight(96)
            self.series_list.setStyleSheet(
                f"""
                QListWidget {{
                    color: {COLORS['text']};
                    background: #081421;
                    border: 1px solid {COLORS['blue_line']};
                    outline: none;
                }}
                QListWidget::item {{
                    padding: 3px 6px;
                    border-bottom: 1px solid #143457;
                }}
                QListWidget::item:selected {{
                    background: #1E4D8D;
                }}
                """
            )
            layout.addWidget(self.series_list, 1)

        self.file_combo.currentIndexChanged.connect(self.handle_file_changed)
        self.entry_list.itemClicked.connect(self.handle_entry_clicked)
        if self.mode != "image":
            self.series_list.currentItemChanged.connect(self.handle_series_changed)
            self.y_axis_edit.textChanged.connect(self.update_preview)
            self.y_axis_min_spin.valueChanged.connect(self.update_preview)
            self.y_axis_max_spin.valueChanged.connect(self.update_preview)
            self.y_axis_interval_spin.valueChanged.connect(self.update_preview)
            self.y_axis_font_size_spin.valueChanged.connect(self.update_preview)
            self.upper_limit_color_combo.currentIndexChanged.connect(self.update_preview)
            self.upper_limit_width_spin.valueChanged.connect(self.update_preview)
            self.upper_limit_style_combo.currentIndexChanged.connect(self.update_preview)
            self.upper_limit_combo.currentIndexChanged.connect(self.update_preview)
            self.lower_limit_color_combo.currentIndexChanged.connect(self.update_preview)
            self.lower_limit_width_spin.valueChanged.connect(self.update_preview)
            self.lower_limit_style_combo.currentIndexChanged.connect(self.update_preview)
            self.lower_limit_combo.currentIndexChanged.connect(self.update_preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        clear_button = QPushButton("清除绑定")
        buttons.addButton(clear_button, QDialogButtonBox.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        clear_button.clicked.connect(self.clear_binding)
        outer_layout.addWidget(buttons)

        self.set_active_slot("path")
        self.update_selection_fields()
        if self.fixed_ini_path:
            self.folder_browse_button.setEnabled(False)
            self.file_combo.setEnabled(False)
        self.refresh_ini_files()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.mode == "image" and self._preview_image_path:
            self.set_preview_image(self._preview_image_path)

    def clear_binding(self):
        self._clear_requested = True
        self.accept()

    def choose_folder(self):
        if self.fixed_ini_path:
            return
        start_dir = str(self.ini_dir or Path.cwd())
        selected = QFileDialog.getExistingDirectory(self, "选择 INI 文件夹", start_dir)
        if not selected:
            return
        self.ini_dir = Path(selected)
        self.folder_edit.setText(str(self.ini_dir))
        self.refresh_ini_files()
        self.update_preview()

    def current_limit_series_index(self, combo_box):
        if combo_box is None or combo_box.count() == 0:
            return None
        return combo_box.currentData()

    def populate_limit_color_combo(self, combo_box, current_value):
        if combo_box is None:
            return
        combo_box.blockSignals(True)
        combo_box.clear()
        selected_index = 0
        current_text = str(current_value or "").strip()
        matched = False
        for index, (label, color_value) in enumerate(get_curve_limit_color_options()):
            combo_box.addItem(label, color_value)
            if current_text and (str(color_value).lower() == current_text.lower() or label == current_text):
                selected_index = index
                matched = True
        if current_text and not matched and combo_box.findData(current_text) < 0:
            combo_box.addItem(current_text, current_text)
            selected_index = combo_box.count() - 1
        combo_box.setCurrentIndex(selected_index)
        combo_box.blockSignals(False)

    def populate_line_style_combo(self, combo_box, current_value):
        if combo_box is None:
            return
        combo_box.blockSignals(True)
        combo_box.clear()
        selected_index = 0
        current_text = str(current_value or "dash").strip().lower()
        for index, (label, style_value) in enumerate(get_curve_line_style_options()):
            combo_box.addItem(label, style_value)
            if style_value == current_text:
                selected_index = index
        combo_box.setCurrentIndex(selected_index)
        combo_box.blockSignals(False)

    def get_selected_limit_binding(self):
        if self.mode == "image":
            return {"section": "", "key": ""}
        return {
            "section": normalize_section_name(self.selection.get("limit", {}).get("section", "")),
            "key": str(self.selection.get("limit", {}).get("key", "") or "").strip(),
        }

    def current_limit_color_value(self, combo_box, fallback):
        if combo_box is None or combo_box.count() == 0:
            return resolve_indicator_color(fallback, fallback).name().upper()
        value = combo_box.currentData()
        text = str(value or fallback or "").strip() or fallback
        return resolve_indicator_color(text, fallback).name().upper()

    def current_limit_width_value(self, spin_box, fallback):
        if spin_box is None:
            return max(1, int(fallback or 1))
        try:
            return max(1, int(spin_box.value()))
        except Exception:
            return max(1, int(fallback or 1))

    def current_limit_style_value(self, combo_box, fallback):
        if combo_box is None or combo_box.count() == 0:
            return str(fallback or "dash").strip().lower() or "dash"
        value = combo_box.currentData()
        return str(value or fallback or "dash").strip().lower() or "dash"

    def read_spinbox_number(self, spin_box, fallback):
        if spin_box is None:
            return fallback
        try:
            spin_box.interpretText()
        except Exception:
            pass
        try:
            line_edit = spin_box.lineEdit()
            text_value = parse_numeric_value_from_text(line_edit.text() if line_edit is not None else "")
            if text_value is not None:
                return text_value
        except Exception:
            pass
        try:
            return spin_box.value()
        except Exception:
            return fallback

    def current_curve_y_axis_config(self):
        return normalize_curve_y_axis_config(
            self.read_spinbox_number(getattr(self, "y_axis_min_spin", None), None),
            self.read_spinbox_number(getattr(self, "y_axis_max_spin", None), None),
            self.read_spinbox_number(getattr(self, "y_axis_interval_spin", None), None),
            self.y_axis_edit.text().strip() if hasattr(self, "y_axis_edit") else self.default_y_axis_name,
        )

    def current_curve_y_axis_font_size(self):
        if not hasattr(self, "y_axis_font_size_spin"):
            return 9
        try:
            value = self.read_spinbox_number(self.y_axis_font_size_spin, self.y_axis_font_size_spin.value())
            return max(4, min(int(round(float(value))), 24))
        except Exception:
            return 9

    def clamp_y_axis_font_size_input(self):
        if not hasattr(self, "y_axis_font_size_spin"):
            return
        value = self.current_curve_y_axis_font_size()
        self.y_axis_font_size_spin.blockSignals(True)
        self.y_axis_font_size_spin.setValue(value)
        self.y_axis_font_size_spin.blockSignals(False)

    def refresh_limit_path_options(self, entries):
        del entries
        if self.mode == "image":
            return
        if str(self._pending_limit_path_key or "").strip():
            self.selection["limit"] = {
                "section": normalize_section_name(self._pending_limit_path_section),
                "key": str(self._pending_limit_path_key).strip(),
            }
            self._pending_limit_path_section = ""
            self._pending_limit_path_key = ""

    def resolve_limit_csv_path_from_lines(self, lines, file_path):
        if self.mode == "image":
            return ""

        limit_binding = self.get_selected_limit_binding()
        limit_key = limit_binding.get("key", "")
        if limit_key:
            limit_value = extract_value_from_lines(lines, limit_key, limit_binding.get("section"))
            if limit_value is None:
                return None
            return compose_image_path("", limit_value, file_path.parent)

        legacy_path = clean_path_text(self.limit_csv_path)
        return legacy_path or ""

    def refresh_limit_csv_rows(self, limit_path=""):
        if self.mode == "image":
            return

        self._limit_row_infos = []
        self._resolved_limit_csv_path = clean_path_text(limit_path)
        upper_target = self._pending_upper_limit_series_index
        if upper_target is None:
            upper_target = self.current_limit_series_index(self.upper_limit_combo)
        lower_target = self._pending_lower_limit_series_index
        if lower_target is None:
            lower_target = self.current_limit_series_index(self.lower_limit_combo)
        self.upper_limit_combo.blockSignals(True)
        self.lower_limit_combo.blockSignals(True)
        self.upper_limit_combo.clear()
        self.lower_limit_combo.clear()
        self.upper_limit_combo.addItem("不使用上限", None)
        self.lower_limit_combo.addItem("不使用下限", None)

        if self._resolved_limit_csv_path:
            path = Path(self._resolved_limit_csv_path)
            if path.exists():
                self._limit_row_infos, _raw_lines = extract_csv_numeric_rows(path)
                for row_info in self._limit_row_infos:
                    label = f"第{row_info['line_number']}行: {row_info['text']}"
                    self.upper_limit_combo.addItem(label, row_info["series_index"])
                    self.lower_limit_combo.addItem(label, row_info["series_index"])

        if upper_target is not None:
            idx = self.upper_limit_combo.findData(upper_target)
            self.upper_limit_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self.upper_limit_combo.setCurrentIndex(0)
        if lower_target is not None:
            idx = self.lower_limit_combo.findData(lower_target)
            self.lower_limit_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self.lower_limit_combo.setCurrentIndex(0)

        self._pending_upper_limit_series_index = None
        self._pending_lower_limit_series_index = None
        self.upper_limit_combo.blockSignals(False)
        self.lower_limit_combo.blockSignals(False)

    def get_current_file_value(self):
        if self.fixed_ini_path:
            if self.ini_dir:
                try:
                    return str(self.fixed_ini_path.relative_to(self.ini_dir))
                except Exception:
                    return str(self.fixed_ini_path)
            return str(self.fixed_ini_path)
        return self.file_combo.currentData()

    def get_current_file_path(self):
        if self.fixed_ini_path:
            return self.fixed_ini_path
        file_value = self.file_combo.currentData()
        if not file_value or not self.ini_dir:
            return None
        return self.ini_dir / file_value

    def set_active_slot(self, slot):
        self.active_slot = slot
        if self.mode == "image":
            if slot == "path":
                self.active_label.setText("当前点击列表将设置：图片路径键")
                self.path_button.setDefault(True)
                self.name_button.setDefault(False)
            else:
                self.active_label.setText("当前点击列表将设置：图片文件名键")
                self.path_button.setDefault(False)
                self.name_button.setDefault(True)

            self.path_button.setStyleSheet("border: 1px solid #58D4FF;" if slot == "path" else "")
            self.name_button.setStyleSheet("border: 1px solid #58D4FF;" if slot == "name" else "")
        else:
            if slot == "limit":
                self.active_label.setText("当前点击列表将设置：上下限CSV键")
            else:
                self.active_label.setText("当前点击列表将设置：主曲线CSV键")
            if hasattr(self, "target_path_button"):
                self.target_path_button.setStyleSheet("border: 1px solid #58D4FF;" if slot == "path" else "")
            if hasattr(self, "target_limit_button"):
                self.target_limit_button.setStyleSheet("border: 1px solid #58D4FF;" if slot == "limit" else "")

    def format_selection_text(self, slot_name):
        selected = self.selection[slot_name]
        key = selected.get("key", "").strip()
        if not key:
            return ""
        section = selected.get("section", "")
        return f"{format_section_title(section)} {key}"

    def update_selection_fields(self):
        self.path_edit.setText(self.format_selection_text("path"))
        if self.mode == "image":
            self.name_edit.setText(self.format_selection_text("name"))
        elif hasattr(self, "limit_edit"):
            self.limit_edit.setText(self.format_selection_text("limit"))

    def refresh_ini_files(self):
        self.file_combo.clear()
        if self.fixed_ini_path:
            file_value = self.get_current_file_value() if self.fixed_ini_path.exists() else ""
            self.file_combo.addItem(file_value or "当前目标配置不存在", file_value)
            self.refresh_entry_list_from_current_file()
            self.update_preview()
            return
        if not self.ini_dir or not self.ini_dir.exists():
            self.file_combo.addItem("请先选择 INI 文件夹", "")
            self.refresh_entry_list([])
            self.update_preview()
            return

        ini_files = sorted(str(path.relative_to(self.ini_dir)) for path in self.ini_dir.rglob("*.ini"))
        if not ini_files:
            self.file_combo.addItem("该文件夹下没有 INI 文件", "")
            self.refresh_entry_list([])
            self.update_preview()
            return

        self.file_combo.addItem("请选择 INI 文件", "")
        for rel_path in ini_files:
            self.file_combo.addItem(rel_path, rel_path)

        if self._pending_file:
            idx = self.file_combo.findData(self._pending_file)
            if idx >= 0:
                self.file_combo.setCurrentIndex(idx)
            self._pending_file = ""
        self.refresh_entry_list_from_current_file()
        self.update_preview()

    def handle_file_changed(self, *_args):
        self.refresh_entry_list_from_current_file()
        self.update_preview()

    def refresh_entry_list(self, entries):
        self.entry_list.clear()
        if not entries:
            placeholder = QListWidgetItem("当前没有带 ### 标记的可绑定键值行")
            placeholder.setFlags(Qt.NoItemFlags)
            self.entry_list.addItem(placeholder)
            return

        last_section = object()
        for entry in entries:
            section = normalize_section_name(entry["section"])
            if section != last_section:
                header = QListWidgetItem(format_section_title(section))
                header.setFlags(Qt.NoItemFlags)
                header.setForeground(QColor(COLORS["muted"]))
                self.entry_list.addItem(header)
                last_section = section

            item = QListWidgetItem(f"  {entry['key']} = {entry['value']}")
            item.setData(Qt.UserRole, entry)
            item.setToolTip(f"{format_section_title(section)}  {entry['key']} = {entry['value']}")
            self.entry_list.addItem(item)

    def refresh_entry_list_from_current_file(self):
        self._entries = []
        file_path = self.get_current_file_path()
        if not file_path or not file_path.exists():
            if self.mode != "image":
                self.refresh_limit_path_options([])
                self.refresh_limit_csv_rows("")
            self.refresh_entry_list([])
            return
        try:
            self._entries = parse_key_value_lines(read_text_with_fallback(file_path).splitlines())
        except Exception:
            self._entries = []
        bindable_entries = get_marked_entries(self._entries)
        if self.mode != "image":
            self.refresh_limit_path_options(bindable_entries)
        self.refresh_entry_list(bindable_entries)

    def handle_entry_clicked(self, item):
        entry = item.data(Qt.UserRole)
        if not entry:
            return
        selected_entry = {
            "section": normalize_section_name(entry.get("section", "")),
            "key": entry.get("key", ""),
        }
        if self.mode == "image":
            self.selection[self.active_slot] = selected_entry
        else:
            self.selection[self.active_slot if self.active_slot in {"path", "limit"} else "path"] = selected_entry
        self.update_selection_fields()
        self.update_preview()

    def handle_series_changed(self, current, _previous):
        if self.mode == "image":
            return
        if not current:
            self._selected_series_index = None
            self.update_preview()
            return
        self._selected_series_index = current.data(Qt.UserRole)
        self.update_preview()

    def clear_preview_image(self, text="缩略图预览"):
        self._preview_image_path = ""
        if not hasattr(self, "preview_image_label"):
            return
        self.preview_image_label.clear()
        self.preview_image_label.setPixmap(QPixmap())
        self.preview_image_label.setText(text)

    def set_preview_image(self, image_path):
        if not hasattr(self, "preview_image_label"):
            return
        path = Path(str(image_path))
        if not path.exists():
            self.clear_preview_image("未找到图片")
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.clear_preview_image("图片无法加载")
            return

        self._preview_image_path = str(path)
        scaled = pixmap.scaled(
            self.preview_image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_image_label.setText("")
        self.preview_image_label.setPixmap(scaled)

    def update_preview(self):
        if self.mode != "image" and hasattr(self, "series_list"):
            self.series_list.blockSignals(True)
            self.series_list.clear()
            self.series_list.blockSignals(False)
        if not self.ini_dir or not self.ini_dir.exists():
            self.preview_label.setText("预览结果：请先选择 INI 文件夹")
            if self.mode == "image":
                self.clear_preview_image("缩略图预览")
            return

        file_value = self.get_current_file_value()
        if not file_value:
            self.preview_label.setText("预览结果：请选择 INI 文件")
            if self.mode == "image":
                self.clear_preview_image("缩略图预览")
            return

        path_key = self.selection["path"].get("key", "").strip()
        name_key = self.selection["name"].get("key", "").strip() if self.mode == "image" else ""
        if not path_key:
            missing_text = "预览结果：请至少选择图片路径键" if self.mode == "image" else "预览结果：请至少选择CSV路径键"
            self.preview_label.setText(missing_text)
            if self.mode == "image":
                self.clear_preview_image("缩略图预览")
            return

        file_path = self.get_current_file_path()
        if not file_path:
            self.preview_label.setText("预览结果：未找到当前目标配置")
            if self.mode == "image":
                self.clear_preview_image("未找到当前目标配置")
            return
        try:
            lines = read_text_with_fallback(file_path).splitlines()
        except Exception as exc:
            self.preview_label.setText(f"预览结果：读取失败 - {exc}")
            if self.mode == "image":
                self.clear_preview_image("读取失败")
            return

        path_value = extract_value_from_lines(lines, path_key, self.selection["path"].get("section"))
        if path_value is None:
            not_found_text = "预览结果：未找到图片路径键对应的值" if self.mode == "image" else "预览结果：未找到CSV路径键对应的值"
            self.preview_label.setText(not_found_text)
            if self.mode == "image":
                self.clear_preview_image("未找到路径值")
            return

        name_value = ""
        if name_key:
            name_value = extract_value_from_lines(lines, name_key, self.selection["name"].get("section"))
            if name_value is None:
                not_found_text = "预览结果：未找到图片文件名键对应的值" if self.mode == "image" else "预览结果：未找到CSV文件名键对应的值"
                self.preview_label.setText(not_found_text)
                if self.mode == "image":
                    self.clear_preview_image("未找到图片名")
                return

        if self.mode == "image":
            final_path = compose_image_path(path_value, name_value, file_path.parent) if name_key else compose_image_path("", path_value, file_path.parent)
        else:
            final_path = compose_image_path("", path_value, file_path.parent)
        if self.mode == "image":
            exists_text = "已找到图片" if final_path and Path(final_path).exists() else "未找到图片文件"
            self.preview_label.setText(
                f"路径值：{path_value}\n"
                f"图片名：{name_value}\n"
                f"最终图片：{final_path or ''}\n"
                f"状态：{exists_text}"
            )
            if final_path and Path(final_path).exists():
                self.set_preview_image(final_path)
            else:
                self.clear_preview_image("未找到图片")
        else:
            limit_binding = self.get_selected_limit_binding()
            limit_path = self.resolve_limit_csv_path_from_lines(lines, file_path)
            self.refresh_limit_csv_rows("" if limit_path is None else limit_path)
            series_list, _raw_lines = parse_csv_curve_series(final_path) if final_path and Path(final_path).exists() else ([], [])
            status_text = "已找到CSV"
            if final_path and not Path(final_path).exists():
                status_text = "未找到CSV文件"
            elif final_path and not series_list:
                status_text = "CSV无有效曲线数据"
            limit_text = "未设置上下限CSV键"
            upper_index = self.current_limit_series_index(self.upper_limit_combo) if hasattr(self, "upper_limit_combo") else None
            lower_index = self.current_limit_series_index(self.lower_limit_combo) if hasattr(self, "lower_limit_combo") else None
            upper_color = self.current_limit_color_value(getattr(self, "upper_limit_color_combo", None), "#FFB020")
            lower_color = self.current_limit_color_value(getattr(self, "lower_limit_color_combo", None), "#FF4D4F")
            upper_width = self.current_limit_width_value(getattr(self, "upper_limit_width_spin", None), 1)
            lower_width = self.current_limit_width_value(getattr(self, "lower_limit_width_spin", None), 1)
            upper_style = get_curve_line_style_label(self.current_limit_style_value(getattr(self, "upper_limit_style_combo", None), "dash"))
            lower_style = get_curve_line_style_label(self.current_limit_style_value(getattr(self, "lower_limit_style_combo", None), "dash"))
            y_axis_config = self.current_curve_y_axis_config()
            y_axis_font_size = self.current_curve_y_axis_font_size()
            if limit_binding.get("key"):
                limit_head = f"{format_section_title(limit_binding.get('section', ''))} {limit_binding.get('key')}"
                if limit_path is None:
                    limit_text = f"{limit_head}\n状态: 未找到对应的路径值"
                elif limit_path and Path(limit_path).exists():
                    upper_label = f"第{int(upper_index) + 1}条" if upper_index is not None else "未选"
                    lower_label = f"第{int(lower_index) + 1}条" if lower_index is not None else "未选"
                    limit_text = (
                        f"{limit_head}\n{limit_path}\n"
                        f"上限: {upper_label} / {upper_color} / {upper_width}px / {upper_style}\n"
                        f"下限: {lower_label} / {lower_color} / {lower_width}px / {lower_style}"
                    )
                elif limit_path:
                    limit_text = f"{limit_head}\n{limit_path}\n状态: 未找到上下限CSV"
                else:
                    limit_text = f"{limit_head}\n状态: 未找到上下限CSV路径"
            elif clean_path_text(self.limit_csv_path):
                legacy_limit_path = clean_path_text(self.limit_csv_path)
                if Path(legacy_limit_path).exists():
                    upper_label = f"第{int(upper_index) + 1}条" if upper_index is not None else "未选"
                    lower_label = f"第{int(lower_index) + 1}条" if lower_index is not None else "未选"
                    limit_text = (
                        f"{legacy_limit_path}\n"
                        f"上限: {upper_label} / {upper_color} / {upper_width}px / {upper_style}\n"
                        f"下限: {lower_label} / {lower_color} / {lower_width}px / {lower_style}"
                    )
                else:
                    limit_text = f"{legacy_limit_path}\n状态: 未找到上下限CSV"
            selected_index = self._selected_series_index if self._selected_series_index is not None else self._pending_series_index
            if selected_index is None:
                selected_index = 0
            if series_list:
                selected_index = max(0, min(int(selected_index), len(series_list) - 1))
                self.series_list.blockSignals(True)
                for idx, points in enumerate(series_list, start=1):
                    item = QListWidgetItem(f"第{idx}条曲线: {len(points)}点")
                    item.setData(Qt.UserRole, idx - 1)
                    self.series_list.addItem(item)
                self.series_list.setCurrentRow(selected_index)
                self.series_list.blockSignals(False)
                self._selected_series_index = selected_index
                point_count = len(series_list[selected_index])
            else:
                point_count = 0
            self.preview_label.setText(
                f"CSV路径：{path_value}\n"
                f"最终CSV：{final_path or ''}\n"
                f"状态：{status_text}\n"
                f"曲线点数：{point_count}\n"
                f"曲线序号：第{(selected_index + 1) if series_list else 0}条\n"
                f"上下限：{limit_text}\n"
                f"纵轴名称：{self.y_axis_edit.text().strip() or self.default_y_axis_name}\n"
                f"竖轴范围：{format_axis_value(y_axis_config['min'])} ~ {format_axis_value(y_axis_config['max'])} / 间距 {format_axis_value(y_axis_config['interval'])} / 字号 {y_axis_font_size}"
            )

    def get_result(self):
        ini_dir_value = str(self.ini_dir) if self.ini_dir else ""
        if self._clear_requested:
            return {"ini_dir": ini_dir_value, "binding": None}

        file_value = self.get_current_file_value()
        path_key = self.selection["path"].get("key", "").strip()
        name_key = self.selection["name"].get("key", "").strip() if self.mode == "image" else ""
        if not file_value or not path_key:
            return {"ini_dir": ini_dir_value, "binding": None}

        binding = {
            "type": "image" if self.mode == "image" else "csv_curve",
            "file": file_value,
            "path_section": normalize_section_name(self.selection["path"].get("section", "")),
            "path_key": path_key,
        }
        if name_key:
            binding["name_section"] = normalize_section_name(self.selection["name"].get("section", ""))
            binding["name_key"] = name_key
        if self.mode != "image":
            selected_index = self._selected_series_index
            if selected_index is None and hasattr(self, "series_list") and self.series_list.count() > 0:
                selected_index = self.series_list.item(0).data(Qt.UserRole)
            binding["series_index"] = int(selected_index or 0)
            binding["y_axis_name"] = self.y_axis_edit.text().strip() or self.default_y_axis_name
            y_axis_config = self.current_curve_y_axis_config()
            binding["y_axis_min"] = y_axis_config["min"]
            binding["y_axis_max"] = y_axis_config["max"]
            binding["y_axis_tick_interval"] = y_axis_config["interval"]
            binding["y_axis_font_size"] = self.current_curve_y_axis_font_size()
            limit_binding = self.get_selected_limit_binding()
            limit_key = limit_binding.get("key", "")
            binding["upper_limit_color"] = self.current_limit_color_value(getattr(self, "upper_limit_color_combo", None), "#FFB020")
            binding["lower_limit_color"] = self.current_limit_color_value(getattr(self, "lower_limit_color_combo", None), "#FF4D4F")
            binding["upper_limit_width"] = self.current_limit_width_value(getattr(self, "upper_limit_width_spin", None), 1)
            binding["lower_limit_width"] = self.current_limit_width_value(getattr(self, "lower_limit_width_spin", None), 1)
            binding["upper_limit_style"] = self.current_limit_style_value(getattr(self, "upper_limit_style_combo", None), "dash")
            binding["lower_limit_style"] = self.current_limit_style_value(getattr(self, "lower_limit_style_combo", None), "dash")
            if limit_key:
                binding["limit_path_section"] = normalize_section_name(limit_binding.get("section", ""))
                binding["limit_path_key"] = limit_key
            else:
                limit_path = clean_path_text(self.limit_csv_path)
                if limit_path:
                    binding["limit_csv_path"] = limit_path
            if limit_key or clean_path_text(self.limit_csv_path):
                upper_index = self.current_limit_series_index(self.upper_limit_combo) if hasattr(self, "upper_limit_combo") else None
                lower_index = self.current_limit_series_index(self.lower_limit_combo) if hasattr(self, "lower_limit_combo") else None
                if upper_index is not None:
                    binding["upper_limit_series_index"] = int(upper_index)
                if lower_index is not None:
                    binding["lower_limit_series_index"] = int(lower_index)

        return {
            "ini_dir": ini_dir_value,
            "binding": binding,
        }


class CsvCurveBindingDialog(QDialog):
    def __init__(self, field_title, csv_dir, current_binding=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"CSV曲线绑定设置 - {field_title}")
        self.setModal(True)
        self.resize(620, 430)
        apply_compact_dialog_style(self, 8)
        self._clear_requested = False
        initial_dir = current_binding.get("csv_dir", "") if current_binding else ""
        self.csv_dir = Path(initial_dir or csv_dir) if (initial_dir or csv_dir) else None
        self._pending_file = current_binding.get("csv_file", "") if current_binding else ""
        self._pending_series_index = current_binding.get("series_index", 0) if current_binding else 0
        self._selected_series_index = None
        default_y_axis = current_binding.get("y_axis_name", "") if current_binding else ""
        self.default_y_axis_name = default_y_axis or infer_curve_axis_name(field_title)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)
        layout.addLayout(form)

        folder_host = QWidget()
        folder_layout = QHBoxLayout(folder_host)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(6)
        self.folder_edit = QLineEdit(str(self.csv_dir) if self.csv_dir else "")
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("请选择 CSV 文件夹")
        self.folder_edit.setStyleSheet(f"color: {COLORS['muted']};")
        folder_layout.addWidget(self.folder_edit, 1)
        browse_button = QPushButton("选择...")
        browse_button.clicked.connect(self.choose_folder)
        folder_layout.addWidget(browse_button)
        form.addRow("CSV目录", folder_host)

        self.file_combo = QComboBox()
        form.addRow("CSV文件", self.file_combo)

        self.y_axis_edit = QLineEdit(self.default_y_axis_name)
        self.y_axis_edit.setPlaceholderText("例如 亮度、斜率、电流")
        form.addRow("纵轴名称", self.y_axis_edit)

        self.preview_label = QLabel("预览结果：")
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(42)
        self.preview_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                padding: 8px;
            }}
            """
        )
        form.addRow("预览结果", self.preview_label)

        list_title = QLabel("CSV数据行预览")
        list_title.setStyleSheet(f"color: {COLORS['muted']};")
        layout.addWidget(list_title)

        self.preview_list = QListWidget()
        self.preview_list.setMinimumHeight(150)
        self.preview_list.setStyleSheet(
            f"""
            QListWidget {{
                color: {COLORS['text']};
                background: #081421;
                border: 1px solid {COLORS['blue_line']};
                outline: none;
            }}
            QListWidget::item {{
                padding: 3px 6px;
                border-bottom: 1px solid #143457;
            }}
            """
        )
        layout.addWidget(self.preview_list, 1)

        self.file_combo.currentIndexChanged.connect(self.handle_file_changed)
        self.preview_list.currentItemChanged.connect(self.handle_series_changed)
        self.y_axis_edit.textChanged.connect(lambda *_args: self.update_preview_text())

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        clear_button = QPushButton("清除绑定")
        buttons.addButton(clear_button, QDialogButtonBox.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        clear_button.clicked.connect(self.clear_binding)
        layout.addWidget(buttons)

        self.refresh_csv_files()

    def clear_binding(self):
        self._clear_requested = True
        self.accept()

    def choose_folder(self):
        start_dir = str(self.csv_dir or Path.cwd())
        selected = QFileDialog.getExistingDirectory(self, "选择 CSV 文件夹", start_dir)
        if not selected:
            return
        self.csv_dir = Path(selected)
        self.folder_edit.setText(str(self.csv_dir))
        self.refresh_csv_files()

    def refresh_csv_files(self):
        self.file_combo.clear()
        if not self.csv_dir or not self.csv_dir.exists():
            self.file_combo.addItem("请先选择 CSV 文件夹", "")
            self.refresh_preview()
            return

        csv_files = sorted(str(path.relative_to(self.csv_dir)) for path in self.csv_dir.rglob("*.csv"))
        if not csv_files:
            self.file_combo.addItem("该文件夹下没有 CSV 文件", "")
            self.refresh_preview()
            return

        self.file_combo.addItem("请选择 CSV 文件", "")
        for rel_path in csv_files:
            self.file_combo.addItem(rel_path, rel_path)

        if self._pending_file:
            idx = self.file_combo.findData(self._pending_file)
            if idx >= 0:
                self.file_combo.setCurrentIndex(idx)
            self._pending_file = ""
        self.refresh_preview()

    def handle_file_changed(self, *_args):
        self._selected_series_index = None
        self.refresh_preview()

    def handle_series_changed(self, current, _previous):
        if not current:
            self._selected_series_index = None
            self.update_preview_text()
            return
        self._selected_series_index = current.data(Qt.UserRole)
        self.update_preview_text()

    def refresh_preview(self):
        self.preview_list.clear()
        if not self.csv_dir or not self.csv_dir.exists():
            self.preview_label.setText("预览结果：请先选择 CSV 文件夹")
            return

        file_value = self.file_combo.currentData()
        if not file_value:
            self.preview_label.setText("预览结果：请选择 CSV 文件")
            return

        file_path = self.csv_dir / file_value
        if not file_path.exists():
            self.preview_label.setText("预览结果：未找到 CSV 文件")
            return

        try:
            raw_lines = read_text_with_fallback(file_path).splitlines()
        except Exception as exc:
            self.preview_label.setText(f"预览结果：读取失败 - {exc}")
            return

        series_list, _lines = parse_csv_curve_series(file_path)
        series_index = 0
        shown = 0
        for line_number, line in enumerate(raw_lines, start=1):
            if not extract_numeric_values_from_csv_line(line):
                continue
            text = line.strip()
            if len(text) > 180:
                text = text[:180] + "..."
            item = QListWidgetItem(f"第{line_number}行: {text}")
            item.setData(Qt.UserRole, series_index)
            self.preview_list.addItem(item)
            series_index += 1
            shown += 1

        if shown == 0:
            self.preview_list.addItem("(CSV文件为空)")
            self._selected_series_index = None
            self.preview_label.setText("预览结果：CSV中未找到可绘制的数据行")
            return

        target_index = self._pending_series_index if self._selected_series_index is None else self._selected_series_index
        if target_index is None:
            target_index = 0
        target_index = max(0, min(int(target_index), self.preview_list.count() - 1))
        self.preview_list.setCurrentRow(target_index)
        self._pending_series_index = target_index
        self.update_preview_text(file_value=file_value, series_list=series_list)

    def update_preview_text(self, file_value=None, series_list=None):
        if not self.csv_dir or not self.csv_dir.exists():
            self.preview_label.setText("预览结果：请先选择 CSV 文件夹")
            return

        current_file = file_value or self.file_combo.currentData()
        if not current_file:
            self.preview_label.setText("预览结果：请选择 CSV 文件")
            return

        file_path = self.csv_dir / current_file
        if series_list is None:
            series_list, _lines = parse_csv_curve_series(file_path)

        if not series_list:
            self.preview_label.setText(f"文件：{current_file}\n状态：CSV无有效曲线数据")
            return

        selected_index = self._selected_series_index
        if selected_index is None:
            selected_index = 0
        selected_index = max(0, min(int(selected_index), len(series_list) - 1))
        selected_points = series_list[selected_index]
        self.preview_label.setText(
            f"文件：{current_file}\n"
            f"数据行：第 {selected_index + 1} 条\n"
            f"有效曲线点数：{len(selected_points)}\n"
            f"总可选数据行：{len(series_list)}\n"
            f"纵轴名称：{self.y_axis_edit.text().strip() or self.default_y_axis_name}"
        )

    def get_result(self):
        csv_dir_value = str(self.csv_dir) if self.csv_dir else ""
        if self._clear_requested:
            return {"csv_dir": csv_dir_value, "binding": None}

        file_value = self.file_combo.currentData()
        if not file_value:
            return {"csv_dir": csv_dir_value, "binding": None}

        selected_index = self._selected_series_index
        if selected_index is None and self.preview_list.count() > 0:
            selected_index = self.preview_list.item(0).data(Qt.UserRole)
        if selected_index is None:
            selected_index = 0

        return {
            "csv_dir": csv_dir_value,
            "binding": {
                "type": "csv_curve_direct",
                "csv_dir": csv_dir_value,
                "csv_file": file_value,
                "series_index": int(selected_index),
                "y_axis_name": self.y_axis_edit.text().strip() or self.default_y_axis_name,
            },
        }


class SnDisplayLabel(QLabel):
    def __init__(self, caption, value="", parent=None):
        super().__init__(parent)
        self.caption = caption
        self.value_text = ""
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.set_value(value)

    def full_text(self):
        return f"{self.caption}  {self.value_text}"

    def set_value(self, value):
        self.value_text = "N/A" if is_missing_data_value(value) else str(value).strip()
        QLabel.setText(self, self.full_text())
        self.update()

    def needs_two_lines(self, width):
        metrics = QFontMetrics(self.font())
        return metrics.horizontalAdvance(self.full_text()) > max(1, width)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(self.foregroundRole()))

        metrics = QFontMetrics(self.font())
        prefix = f"{self.caption}  "
        prefix_w = metrics.horizontalAdvance(prefix)
        full_text_w = metrics.horizontalAdvance(self.full_text())
        rect = QRectF(self.rect())

        if full_text_w <= rect.width():
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, self.full_text())
            return

        line_h = metrics.lineSpacing()
        top = max(0, int((rect.height() - line_h * 2) / 2))
        prefix_rect = QRectF(0, top, prefix_w, line_h)
        value_rect = QRectF(prefix_w, top, max(1, rect.width() - prefix_w), rect.height() - top)
        painter.drawText(prefix_rect, Qt.AlignLeft | Qt.AlignTop, prefix)
        painter.drawText(value_rect, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap | Qt.TextWrapAnywhere, self.value_text)


class HeaderTag(QWidget):
    settingsDoubleClicked = pyqtSignal()
    settingsClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(76)

        self.time_label = QLabel("", self)
        self.time_label.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.left_sn = SnDisplayLabel("当前编号:", "ITEM-0001", self)
        self.left_sn.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")

        self.left_color = QLabel("颜色:  示例色", self)
        self.left_color.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        self.left_color.setAlignment(Qt.AlignCenter)

        self.main_title_text = DEFAULT_MAIN_TITLE
        self.title_label = QLabel("", self)
        self.title_label.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.set_main_title(DEFAULT_MAIN_TITLE)

        self.right_sn = SnDisplayLabel("待处理编号:", "ITEM-0002", self)
        self.right_sn.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")

        self.right_color = QLabel("颜色:  示例色", self)
        self.right_color.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        self.right_color.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.settings_button = SettingsButton("设置", self)
        apply_settings_button_style(self.settings_button)
        self.settings_button.clicked.connect(lambda: self.settingsClicked.emit())
        self.settings_button.doubleClicked.connect(self.settingsDoubleClicked)
        self.settings_button.hide()

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_current_time)
        self.clock_timer.start(1000)
        self.update_current_time()

    def _metrics(self):
        width = max(980, self.width())
        gap = 12
        center_w = min(620, max(380, int(width * 0.34)))
        side_w = int((width - center_w - gap * 2 - 16) / 2)
        return gap, side_w, center_w

    def _header_layout(self, rect=None):
        draw_rect = rect if rect is not None else self.rect().adjusted(2, 2, -2, -2)
        content_left = draw_rect.left() + 8
        content_right = draw_rect.right() - 8
        content_width = max(1, content_right - content_left)

        shape_y = 17
        shape_h = 40
        gap = 12
        slant = 58
        center_w = min(620, max(380, int(content_width * 0.34)))
        center_left = content_left + int((content_width - center_w) / 2)
        center_right = center_left + center_w

        return {
            "rect": draw_rect,
            "content_left": content_left,
            "content_right": content_right,
            "shape_y": shape_y,
            "shape_h": shape_h,
            "gap": gap,
            "slant": slant,
            "center_left": center_left,
            "center_right": center_right,
            "center_w": center_w,
            "left_top_left": content_left,
            "left_top_right": center_left - gap,
            "right_top_left": center_right + gap,
            "right_top_right": content_right,
        }

    def _apply_fonts(self):
        width = self.width()
        if width >= 1600:
            side_size, title_size, time_size = 10, 16, 9
        elif width >= 1360:
            side_size, title_size, time_size = 9, 13, 8
        else:
            side_size, title_size, time_size = 8, 11, 8
        if getattr(self, "info_font_size", 0):
            side_size = max(4, min(int(self.info_font_size), 24))

        self.left_sn.setFont(make_font(side_size, QFont.Bold))
        self.left_color.setFont(make_font(side_size, QFont.Bold))
        self.right_sn.setFont(make_font(side_size, QFont.Bold))
        self.right_color.setFont(make_font(side_size, QFont.Bold))
        self.title_label.setFont(make_font(title_size, QFont.Bold))
        self.time_label.setFont(make_font(time_size, QFont.Bold))

    def layout_header_children(self):
        width = self.width()
        layout = self._header_layout()

        side_pad = 18
        color_metrics = QFontMetrics(self.left_color.font())
        color_text_w = max(
            color_metrics.horizontalAdvance(self.left_color.text()),
            color_metrics.horizontalAdvance(self.right_color.text()),
        )
        side_top_w = layout["left_top_right"] - layout["left_top_left"]
        side_inner_w = max(150, side_top_w - side_pad * 2)
        color_w = min(max(color_text_w + 26, int(side_inner_w * 0.24)), max(110, side_inner_w - 150))
        sn_w = max(120, side_inner_w - color_w - 12)
        one_line_y = layout["shape_y"] + 13
        two_line_y = layout["shape_y"] + 4
        one_line_h = 20
        two_line_h = layout["shape_h"] - 8
        left_sn_two_lines = self.left_sn.needs_two_lines(sn_w)
        right_sn_two_lines = self.right_sn.needs_two_lines(sn_w)
        left_sn_y = two_line_y if left_sn_two_lines else one_line_y
        right_sn_y = two_line_y if right_sn_two_lines else one_line_y
        left_sn_h = two_line_h if left_sn_two_lines else one_line_h
        right_sn_h = two_line_h if right_sn_two_lines else one_line_h

        self.time_label.setGeometry(width - 250, 0, 230, 18)
        self.settings_button.setGeometry(width - 312, 20, 52, 20)
        self.left_sn.setGeometry(layout["left_top_left"] + side_pad, left_sn_y, sn_w, left_sn_h)
        self.left_color.setGeometry(layout["left_top_left"] + side_pad + sn_w + 12, one_line_y, color_w, 20)
        self.title_label.setGeometry(
            layout["center_left"] + 18,
            layout["shape_y"],
            layout["center_w"] - 36,
            layout["shape_h"],
        )
        self.right_color.setGeometry(layout["right_top_right"] - side_pad - color_w, one_line_y, color_w, 20)
        self.right_sn.setGeometry(
            layout["right_top_right"] - side_pad - color_w - 12 - sn_w,
            right_sn_y,
            sn_w,
            right_sn_h,
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_fonts()
        self.layout_header_children()

    def set_settings_mode(self, enabled):
        self.settings_button.setText("设置中" if enabled else "设置")

    def set_info_font_size(self, value):
        try:
            self.info_font_size = max(0, min(int(value or 0), 24))
        except Exception:
            self.info_font_size = 0
        self._apply_fonts()
        self.layout_header_children()
        self.update()

    def set_main_title(self, value):
        clean_value = str(value or "").strip() or DEFAULT_MAIN_TITLE
        self.main_title_text = clean_value
        self.title_label.setText(f">>  {clean_value}  <<")

    def update_current_time(self):
        self.time_label.setText(QDateTime.currentDateTime().toString("yyyy年MM月dd日 HH:mm:ss"))

    def set_online_sn(self, value):
        if is_missing_data_value(value):
            display_value = "N/A"
        else:
            display_value = extract_curve_match_sn_text(value) or str(value).strip()
        self.left_sn.set_value(display_value)

    def set_pending_sn(self, value):
        self.right_sn.set_value(value)

    def set_online_color(self, value):
        display_value = "N/A" if is_missing_data_value(value) else str(value).strip()
        self.left_color.setText(f"颜色:  {display_value}")

    def set_pending_color(self, value):
        display_value = "N/A" if is_missing_data_value(value) else str(value).strip()
        self.right_color.setText(f"颜色:  {display_value}")

    def set_part_color(self, value):
        self.set_online_color(value)
        self.set_pending_color(value)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(2, 2, -2, -2)
        layout = self._header_layout(rect)
        bg_grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg_grad.setColorAt(0, QColor("#244AA0"))
        bg_grad.setColorAt(0.28, QColor("#16326E"))
        bg_grad.setColorAt(1, QColor("#0A1324"))
        painter.fillRect(rect, bg_grad)

        top_strip = QRectF(rect.left(), rect.top(), rect.width(), 18)
        top_grad = QLinearGradient(top_strip.topLeft(), top_strip.bottomLeft())
        top_grad.setColorAt(0, QColor("#3A63BD"))
        top_grad.setColorAt(1, QColor("#284B9F"))
        painter.fillRect(top_strip, top_grad)

        base_y = layout["shape_y"]
        h = layout["shape_h"]
        slant = layout["slant"]

        left_poly = QPolygonF(
            [
                QPointF(layout["left_top_left"], base_y),
                QPointF(layout["left_top_right"], base_y),
                QPointF(layout["left_top_right"] + slant, base_y + h),
                QPointF(layout["left_top_left"], base_y + h),
            ]
        )
        center_poly = QPolygonF(
            [
                QPointF(layout["center_left"], base_y),
                QPointF(layout["center_right"], base_y),
                QPointF(layout["center_right"] - slant, base_y + h),
                QPointF(layout["center_left"] + slant, base_y + h),
            ]
        )
        right_poly = QPolygonF(
            [
                QPointF(layout["right_top_left"] - slant, base_y + h),
                QPointF(layout["right_top_left"], base_y),
                QPointF(layout["right_top_right"], base_y),
                QPointF(layout["right_top_right"], base_y + h),
            ]
        )

        for poly, strong_a, strong_b in (
            (left_poly, "#264FA8", "#112456"),
            (center_poly, "#325DC0", "#234B9E"),
            (right_poly, "#264FA8", "#112456"),
        ):
            path = QPainterPath()
            path.addPolygon(poly)
            grad = QLinearGradient(poly.boundingRect().topLeft(), poly.boundingRect().topRight())
            grad.setColorAt(0, QColor(strong_a))
            grad.setColorAt(1, QColor(strong_b))
            painter.fillPath(path, grad)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#000000"), 5, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
            painter.drawPolygon(poly)
            painter.setPen(QPen(QColor("#55C6FF"), 2, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
            painter.drawPolygon(poly)

        painter.setPen(QPen(QColor("#5BC7FF"), 2))
        painter.drawRect(rect)


class PanelWidget(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.header = QLabel(title)
        self.header.setFixedHeight(38)
        self.header.setFont(make_font(12, QFont.Bold))
        self.header.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.header.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS['text']};
                padding-left: 10px;
                border: 1px solid {COLORS['blue_line']};
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['header_a']}, stop:1 #06111E);
            }}
            """
        )
        layout.addWidget(self.header)

        self.content = QWidget()
        self.content.setObjectName("panelContent")
        self.content.setStyleSheet("background: transparent;")
        layout.addWidget(self.content, 1)

        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(6)

        add_shadow(self, "#1F98FF", 18)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)

        bg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg.setColorAt(0, QColor("#081421"))
        bg.setColorAt(1, QColor("#030913"))
        painter.setBrush(bg)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 4, 4)

        painter.setPen(QPen(QColor("#46C8FF"), 2))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)

        painter.setPen(QPen(QColor("#0A0F18"), 4))
        painter.drawRoundedRect(rect.adjusted(6, 6, -6, -6), 3, 3)


class StatusBarWidget(QWidget):
    def __init__(self, text, status_color, parent=None):
        super().__init__(parent)
        self.text = text
        self.status_color = QColor(status_color)
        self.setMinimumHeight(34)

    def set_status_text(self, text):
        self.text = "N/A" if is_missing_data_value(text) else str(text).strip()
        kind = normalize_status_kind(self.text)
        if kind == "ok":
            self.status_color = QColor(COLORS["green"])
        elif kind == "warn":
            self.status_color = QColor(COLORS["yellow"])
        elif kind == "na":
            self.status_color = QColor("#6E7782")
        else:
            self.status_color = QColor(COLORS["red"])
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)

        outer = QPainterPath()
        outer.addRoundedRect(QRectF(rect), 4, 4)
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, self.status_color.lighter(120))
        grad.setColorAt(0.52, self.status_color)
        grad.setColorAt(1, self.status_color.darker(160))
        painter.fillPath(outer, grad)

        painter.setPen(QPen(self.status_color.lighter(160), 2))
        painter.drawRoundedRect(rect, 4, 4)

        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(make_font(13, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, self.text)


class ResultRow(QWidget):
    def __init__(self, index, text, status_text, status_kind="ok", parent=None):
        super().__init__(parent)
        self.index = index
        self.label_text = text
        self.current_status_text = str(status_text)
        self.current_status_kind = status_kind
        self.left_padding = 12
        self.font_size = 9
        self.status_min_width = 86
        self.setMinimumHeight(24)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.left_label = QLabel(f"{index} {text}")
        self.left_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        layout.addWidget(self.left_label, 12)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label, 3)
        self.refresh_left_style()
        self.set_status_text(status_text, status_kind)

    def set_label_text(self, text):
        self.label_text = str(text or "").strip()
        self.left_label.setText(f"{self.index} {self.label_text}")

    def refresh_left_style(self):
        self.left_label.setFont(make_font(self.font_size, QFont.Bold))
        self.left_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS['text']};
                padding-left: {self.left_padding}px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4B81B4, stop:0.5 #3B6B99, stop:1 #30587E);
                border-top: 1px solid #6CC9FF;
                border-left: 1px solid #3979AE;
                border-bottom: 1px solid #20405D;
            }}
            """
        )

    def refresh_status_style(self, base, bright):
        self.status_label.setFont(make_font(self.font_size, QFont.Bold))
        self.status_label.setMinimumWidth(self.status_min_width)
        self.status_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS['text']};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {bright}, stop:0.18 {base}, stop:1 {base});
                border: 1px solid {bright};
                min-width: {self.status_min_width}px;
            }}
            """
        )

    def apply_density(self, row_count, configured_font_size=0):
        if row_count <= 10:
            self.font_size = 9
            self.left_padding = 12
            self.status_min_width = 86
            self.setMinimumHeight(24)
        elif row_count <= 14:
            self.font_size = 8
            self.left_padding = 10
            self.status_min_width = 74
            self.setMinimumHeight(20)
        elif row_count <= 18:
            self.font_size = 7
            self.left_padding = 8
            self.status_min_width = 62
            self.setMinimumHeight(18)
        else:
            self.font_size = 6
            self.left_padding = 6
            self.status_min_width = 54
            self.setMinimumHeight(16)
        try:
            configured_size = max(0, min(int(configured_font_size or 0), 24))
        except Exception:
            configured_size = 0
        if configured_size > 0:
            self.font_size = configured_size
            self.setMinimumHeight(max(self.minimumHeight(), configured_size + 10))
        self.refresh_left_style()
        self.set_status_text(self.current_status_text, self.current_status_kind)

    def set_status_text(self, status_text, status_kind=None):
        if status_kind is None:
            status_kind = normalize_status_kind(status_text)
        self.current_status_text = str(status_text)
        self.current_status_kind = status_kind
        status_map = {
            "ok": ("#17965D", "#41E08F"),
            "warn": ("#967A0B", "#F1D143"),
            "bad": ("#A3070E", "#FF2F3B"),
            "na": ("#5D6670", "#9AA4AE"),
        }
        base, bright = status_map.get(status_kind, status_map["na"])
        self.status_label.setText(self.current_status_text)
        self.refresh_status_style(base, bright)


class MetricCell(QLabel):
    def __init__(self, text, large=False, wrap=True, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(wrap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFont(make_font(13 if large else 11, QFont.Bold))
        self.setMinimumHeight(48 if large else 42)
        self.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS['text']};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5D90C0, stop:1 #39658D);
                border: 1px solid #5FD5FF;
                padding: 6px;
            }}
            """
        )


class PieChartWidget(QWidget):
    def __init__(self, good=2, bad=4, parent=None):
        super().__init__(parent)
        self.good = good
        self.bad = bad
        self.setMinimumWidth(150)
        self.setMaximumWidth(210)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

    def sizeHint(self):
        return QSize(190, 120)

    def minimumSizeHint(self):
        return QSize(150, 110)

    def set_values(self, good, bad):
        try:
            self.good = int(str(good).strip())
        except Exception:
            self.good = 0
        try:
            self.bad = int(str(bad).strip())
        except Exception:
            self.bad = 0
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))

        title_font = make_font(10, QFont.Bold)
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(title_font)
        painter.drawText(QRectF(0, 6, self.width(), 22), Qt.AlignHCenter | Qt.AlignVCenter, "生产统计图")

        pie_size = min(int(self.width() * 0.60), int(self.height() * 0.40), 116)
        pie_x = max(10, int((self.width() - pie_size) / 2))
        pie_y = 34
        pie_rect = QRectF(pie_x, pie_y, pie_size, pie_size)
        total = max(1, self.good + self.bad)
        start = 90 * 16
        green_span = -int(360 * 16 * (self.good / total))
        red_span = -int(360 * 16 * (self.bad / total))

        painter.setBrush(QColor("#42D68E"))
        painter.setPen(QPen(QColor("#1B1B1B"), 2))
        painter.drawPie(pie_rect, start, green_span)

        painter.setBrush(QColor("#C70C10"))
        painter.drawPie(pie_rect, start + green_span, red_span)

        value_font = make_font(9, QFont.Bold)
        painter.setFont(value_font)
        painter.setPen(QColor(COLORS["text"]))
        metrics = QFontMetrics(value_font)

        def draw_slice_value(value, start_angle_16, span_angle_16):
            mid_deg = (start_angle_16 + span_angle_16 / 2) / 16.0
            theta = math.radians(mid_deg)
            radius = pie_rect.width() * 0.27
            cx = pie_rect.center().x()
            cy = pie_rect.center().y()
            x = cx + radius * math.cos(theta)
            y = cy - radius * math.sin(theta)
            text = str(value)
            text_rect = QRectF(
                x - metrics.horizontalAdvance(text) / 2 - 2,
                y - metrics.height() / 2 - 1,
                metrics.horizontalAdvance(text) + 4,
                metrics.height() + 2,
            )
            painter.drawText(text_rect, Qt.AlignCenter, text)

        draw_slice_value(self.good, start, green_span)
        draw_slice_value(self.bad, start + green_span, red_span)

        legend_y = self.height() - 20
        items = [("合格数", "#42D68E"), ("不合格数", "#C70C10")]
        legend_font = make_font(8 if self.width() < 220 else 9, QFont.Bold)
        painter.setFont(legend_font)
        metrics = QFontMetrics(legend_font)
        widths = [12 + 6 + metrics.horizontalAdvance(label) for label, _ in items]
        gap = 12
        total_width = sum(widths) + gap
        x = max(8, int((self.width() - total_width) / 2))
        for label, color in items:
            painter.setBrush(QColor(color))
            painter.setPen(Qt.NoPen)
            painter.drawRect(x, legend_y, 12, 12)
            painter.setPen(QColor(COLORS["text"]))
            painter.drawText(x + 18, legend_y + 11, label)
            x += 18 + metrics.horizontalAdvance(label) + gap


class SignalStatusWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(150)
        self.setMaximumWidth(210)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.fill_color = resolve_indicator_color("绿色")
        self.border_color = self.fill_color.darker(240)

    def set_indicator_color(self, value):
        self.fill_color = resolve_indicator_color("N/A" if is_missing_data_value(value) else value)
        self.border_color = self.fill_color.darker(240)
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))

        title_rect = QRectF(0, 6, self.width(), 22)
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(make_font(10, QFont.Bold))
        painter.drawText(title_rect, Qt.AlignHCenter | Qt.AlignVCenter, "设备状态")

        center = QPointF(self.width() * 0.5, self.height() * 0.60)
        radius = min(self.width(), self.height()) * 0.25
        painter.setPen(QPen(self.border_color, 3))
        painter.setBrush(self.fill_color)
        painter.drawEllipse(center, radius, radius)

 

class GlobalStatusLegend(QWidget):
    settingsDoubleClicked = pyqtSignal()
    settingsClicked = pyqtSignal()
    pollIntervalChanged = pyqtSignal(int)
    topMostChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(20)
        self.settings_mode = False
        self.settings_button = SettingsButton("设置", self)
        apply_settings_button_style(self.settings_button)
        self.settings_button.clicked.connect(lambda: self.settingsClicked.emit())
        self.settings_button.doubleClicked.connect(self.settingsDoubleClicked)

        self.interval_label = QLabel("轮询(ms)", self)
        self.interval_label.setStyleSheet(f"color: {COLORS['muted']}; background: transparent;")
        self.interval_label.setFont(make_font(8, QFont.Bold))

        self.interval_spin = QSpinBox(self)
        self.interval_spin.setRange(50, 600000)
        self.interval_spin.setSingleStep(50)
        self.interval_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.interval_spin.setAlignment(Qt.AlignCenter)
        self.interval_spin.setKeyboardTracking(False)
        self.interval_spin.setStyleSheet(
            f"""
            QSpinBox {{
                color: {COLORS['text']};
                background: #10243C;
                border: 1px solid {COLORS['blue_line']};
                padding: 0 4px;
            }}
            """
        )
        self.interval_spin.valueChanged.connect(self.pollIntervalChanged)

        self.top_most_check = QCheckBox("页面置顶", self)
        self.top_most_check.setFont(make_font(8, QFont.Bold))
        self.top_most_check.setStyleSheet(
            f"""
            QCheckBox {{
                color: {COLORS['muted']};
                background: transparent;
                spacing: 4px;
            }}
            QCheckBox::indicator {{
                width: 12px;
                height: 12px;
            }}
            """
        )
        self.top_most_check.setEnabled(False)
        self.top_most_check.setToolTip("进入设置模式后可修改页面置顶")
        self.top_most_check.stateChanged.connect(self.handle_top_most_state_changed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.settings_button.setGeometry(8, 2, 58, max(14, self.height() - 4))
        self.interval_label.setGeometry(78, 2, 52, max(14, self.height() - 4))
        self.interval_spin.setGeometry(132, 2, 76, max(14, self.height() - 4))
        self.top_most_check.setGeometry(220, 2, 78, max(14, self.height() - 4))

    def set_settings_mode(self, enabled):
        self.settings_mode = bool(enabled)
        self.settings_button.setText("设置中" if enabled else "设置")
        self.top_most_check.setEnabled(self.settings_mode)
        self.top_most_check.setToolTip("页面置顶已可修改" if self.settings_mode else "进入设置模式后可修改页面置顶")

    def handle_top_most_state_changed(self, state):
        if not self.settings_mode:
            return
        self.topMostChanged.emit(state == Qt.Checked)

    def set_poll_interval_ms(self, value):
        safe_value = max(50, min(int(value), 600000))
        self.interval_spin.blockSignals(True)
        self.interval_spin.setValue(safe_value)
        self.interval_spin.blockSignals(False)

    def set_top_most_enabled(self, enabled):
        self.top_most_check.blockSignals(True)
        self.top_most_check.setChecked(bool(enabled))
        self.top_most_check.blockSignals(False)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)

        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, QColor("#0A1322"))
        grad.setColorAt(1, QColor("#050B14"))
        painter.fillRect(rect, grad)

        painter.setPen(QPen(QColor("#1D4F85"), 1))
        painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
        divider_x = self.top_most_check.geometry().right() + 10
        painter.drawLine(divider_x, rect.top() + 3, divider_x, rect.bottom() - 2)

        items = [("正常", "#42D68E"), ("告警", "#E8D338"), ("过期", "#D61C2B")]
        font = make_font(9, QFont.Bold)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        widths = [10 + 5 + metrics.horizontalAdvance(label) for label, _ in items]
        gap = 18
        total_width = sum(widths) + gap * (len(items) - 1)
        x = max(divider_x + 12, rect.right() - total_width - 18)
        y = rect.center().y() - 5

        for label, color in items:
            painter.setBrush(QColor(color))
            painter.setPen(Qt.NoPen)
            painter.drawRect(x, y, 10, 10)
            painter.setPen(QColor(COLORS["text"]))
            painter.drawText(x + 15, y + 9, label)
            x += 15 + metrics.horizontalAdvance(label) + gap


class DemoCanvas(QWidget):
    imageTransformChanged = pyqtSignal(dict)

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.image_source_path = ""
        self.image_pixmap = QPixmap()
        self.scaled_image_pixmap = QPixmap()
        self.scaled_image_cache_key = None
        self.curve_source_path = ""
        self.curve_points = []
        self.curve_series_index = 0
        self.curve_limit_source_path = ""
        self.curve_upper_limit_points = []
        self.curve_lower_limit_points = []
        self.curve_upper_limit_index = None
        self.curve_lower_limit_index = None
        self.curve_upper_limit_color = QColor("#FFB020")
        self.curve_lower_limit_color = QColor("#FF4D4F")
        self.curve_upper_limit_width = 1
        self.curve_lower_limit_width = 1
        self.curve_upper_limit_style = Qt.DashLine
        self.curve_lower_limit_style = Qt.DashLine
        self.curve_x_axis_name = "点数"
        self.default_curve_y_axis_name = "数值"
        self.curve_y_axis_name = self.default_curve_y_axis_name
        self.curve_fixed_axis = None
        self.curve_y_axis_font_size = 9
        self.curve_error_text = ""
        self.image_view_scale = 1.0
        self.image_view_offset_x = 0.0
        self.image_view_offset_y = 0.0
        self.image_view_rotation = 0
        self.image_editing_enabled = False
        self.image_dragging = False
        self.image_last_drag_pos = None
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def get_image_transform_state(self):
        return {
            "scale": round(float(self.image_view_scale), 4),
            "offset_x": round(float(self.image_view_offset_x), 2),
            "offset_y": round(float(self.image_view_offset_y), 2),
            "rotation": int(self.image_view_rotation) % 360,
        }

    def set_image_transform_state(self, state, emit_signal=False):
        state = state if isinstance(state, dict) else {}
        self.image_view_scale = max(0.2, min(safe_float_value(state.get("scale", 1.0), 1.0), 8.0))
        self.image_view_offset_x = safe_float_value(state.get("offset_x", 0.0), 0.0)
        self.image_view_offset_y = safe_float_value(state.get("offset_y", 0.0), 0.0)
        try:
            self.image_view_rotation = int(state.get("rotation", 0)) % 360
        except Exception:
            self.image_view_rotation = 0
        self.update()
        if emit_signal:
            self.imageTransformChanged.emit(self.get_image_transform_state())

    def set_settings_mode(self, enabled):
        self.image_editing_enabled = bool(enabled) and self.kind != "curve"
        if self.image_editing_enabled:
            self.setCursor(Qt.OpenHandCursor)
            self.setToolTip("设置模式：滚轮缩放，左键拖动，右键旋转")
        else:
            self.image_dragging = False
            self.image_last_drag_pos = None
            self.setCursor(Qt.ArrowCursor)
            self.setToolTip("")

    def paint_na_placeholder(self, painter, rect):
        painter.fillRect(rect, QColor("#303842"))
        painter.setPen(QPen(QColor("#8F9AA6"), 1))
        painter.drawRect(rect)
        painter.setPen(QColor("#D2D8DE"))
        painter.setFont(make_font(18, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, "N/A")

    def set_image_path(self, image_path):
        path_text = clean_path_text(image_path)
        self.image_source_path = path_text
        self.scaled_image_pixmap = QPixmap()
        self.scaled_image_cache_key = None
        self.curve_source_path = ""
        self.curve_points = []
        self.curve_series_index = 0
        self.curve_limit_source_path = ""
        self.curve_upper_limit_points = []
        self.curve_lower_limit_points = []
        self.curve_upper_limit_index = None
        self.curve_lower_limit_index = None
        self.curve_upper_limit_color = QColor("#FFB020")
        self.curve_lower_limit_color = QColor("#FF4D4F")
        self.curve_upper_limit_width = 1
        self.curve_lower_limit_width = 1
        self.curve_upper_limit_style = Qt.DashLine
        self.curve_lower_limit_style = Qt.DashLine
        self.curve_error_text = ""
        self.image_pixmap = QPixmap(path_text) if path_text and Path(path_text).exists() else QPixmap()
        self.update()

    def clear_display(self):
        self.image_source_path = ""
        self.image_pixmap = QPixmap()
        self.scaled_image_pixmap = QPixmap()
        self.scaled_image_cache_key = None
        self.curve_source_path = ""
        self.curve_points = []
        self.curve_limit_source_path = ""
        self.curve_upper_limit_points = []
        self.curve_lower_limit_points = []
        self.curve_error_text = ""
        self.update()

    def draw_image_pixmap(self, painter, rect):
        painter.fillRect(rect, QColor("#09111D"))
        if self.image_pixmap.isNull():
            self.paint_na_placeholder(painter, rect)
            return

        display_info = self.get_image_display_info(rect)
        if not display_info:
            self.paint_na_placeholder(painter, rect)
            return
        self.clamp_image_view_offset(rect, display_info)
        display_info = self.get_image_display_info(rect)
        image_w = max(1.0, float(self.image_pixmap.width()))
        image_h = max(1.0, float(self.image_pixmap.height()))
        rotation = display_info["rotation"]
        total_scale = display_info["total_scale"]
        center = rect.center() + QPointF(self.image_view_offset_x, self.image_view_offset_y)

        painter.save()
        painter.setClipRect(rect)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.translate(center)
        painter.rotate(rotation)
        painter.scale(total_scale, total_scale)
        painter.drawPixmap(QPointF(-image_w / 2.0, -image_h / 2.0), self.image_pixmap)
        painter.restore()

    def get_image_display_info(self, rect):
        if self.image_pixmap.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return None
        image_w = max(1.0, float(self.image_pixmap.width()))
        image_h = max(1.0, float(self.image_pixmap.height()))
        rotation = int(self.image_view_rotation) % 360
        rotated_w = image_h if rotation in {90, 270} else image_w
        rotated_h = image_w if rotation in {90, 270} else image_h
        base_scale = min(rect.width() / rotated_w, rect.height() / rotated_h)
        total_scale = max(0.01, base_scale * float(self.image_view_scale))
        return {
            "rotation": rotation,
            "total_scale": total_scale,
            "display_w": rotated_w * total_scale,
            "display_h": rotated_h * total_scale,
        }

    def clamp_image_view_offset(self, rect, display_info=None):
        display_info = display_info or self.get_image_display_info(rect)
        if not display_info:
            return False
        min_visible = max(12.0, min(36.0, min(float(rect.width()), float(rect.height())) * 0.25))
        center = rect.center()
        display_w = max(1.0, float(display_info["display_w"]))
        display_h = max(1.0, float(display_info["display_h"]))
        min_offset_x = rect.left() + min_visible - display_w / 2.0 - center.x()
        max_offset_x = rect.right() - min_visible + display_w / 2.0 - center.x()
        min_offset_y = rect.top() + min_visible - display_h / 2.0 - center.y()
        max_offset_y = rect.bottom() - min_visible + display_h / 2.0 - center.y()
        new_offset_x = max(min_offset_x, min(float(self.image_view_offset_x), max_offset_x))
        new_offset_y = max(min_offset_y, min(float(self.image_view_offset_y), max_offset_y))
        changed = abs(new_offset_x - self.image_view_offset_x) > 0.01 or abs(new_offset_y - self.image_view_offset_y) > 0.01
        self.image_view_offset_x = new_offset_x
        self.image_view_offset_y = new_offset_y
        return changed

    def get_scaled_image_pixmap(self, rect):
        if self.image_pixmap.isNull():
            return QPixmap()
        dpr = max(1.0, float(self.devicePixelRatioF()))
        target_w = max(1, int(rect.width() * dpr))
        target_h = max(1, int(rect.height() * dpr))
        cache_key = (self.image_pixmap.cacheKey(), target_w, target_h, round(dpr, 3))
        if self.scaled_image_cache_key != cache_key:
            scaled = self.image_pixmap.scaled(
                QSize(target_w, target_h),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            scaled.setDevicePixelRatio(dpr)
            self.scaled_image_pixmap = scaled
            self.scaled_image_cache_key = cache_key
        return self.scaled_image_pixmap

    def set_curve_axis_labels(self, y_axis_text=None, x_axis_text="点数"):
        self.curve_x_axis_name = str(x_axis_text or "点数").strip() or "点数"
        y_text = str(y_axis_text or "").strip()
        self.curve_y_axis_name = y_text or self.default_curve_y_axis_name
        self.update()

    def set_curve_fixed_axis(self, x_min, x_max, x_ticks, y_min, y_max, y_ticks):
        self.curve_fixed_axis = {
            "x_min": float(x_min),
            "x_max": float(x_max),
            "x_ticks": [float(value) for value in x_ticks],
            "y_min": float(y_min),
            "y_max": float(y_max),
            "y_ticks": [float(value) for value in y_ticks],
        }
        self.update()

    def set_curve_csv_path(
        self,
        csv_path,
        series_index=0,
        y_axis_text=None,
        limit_csv_path=None,
        upper_limit_series_index=None,
        lower_limit_series_index=None,
        upper_limit_color=None,
        lower_limit_color=None,
        upper_limit_width=None,
        lower_limit_width=None,
        upper_limit_style=None,
        lower_limit_style=None,
        match_sn_text=None,
        curve_value_segment=None,
        y_axis_min=None,
        y_axis_max=None,
        y_axis_tick_interval=None,
        y_axis_font_size=None,
    ):
        path_text = clean_path_text(csv_path)
        self.curve_source_path = path_text
        self.curve_series_index = int(series_index) if str(series_index).strip() else 0
        self.curve_limit_source_path = clean_path_text(limit_csv_path)
        self.curve_upper_limit_index = upper_limit_series_index
        self.curve_lower_limit_index = lower_limit_series_index
        self.curve_upper_limit_color = resolve_indicator_color(upper_limit_color, "#FFB020")
        self.curve_lower_limit_color = resolve_indicator_color(lower_limit_color, "#FF4D4F")
        self.curve_upper_limit_width = max(1, int(upper_limit_width or 1))
        self.curve_lower_limit_width = max(1, int(lower_limit_width or 1))
        self.curve_upper_limit_style = resolve_curve_pen_style(upper_limit_style)
        self.curve_lower_limit_style = resolve_curve_pen_style(lower_limit_style)
        if y_axis_text is not None:
            self.set_curve_axis_labels(y_axis_text=y_axis_text)
        if y_axis_min is not None or y_axis_max is not None or y_axis_tick_interval is not None:
            y_axis_config = normalize_curve_y_axis_config(y_axis_min, y_axis_max, y_axis_tick_interval, self.curve_y_axis_name)
            self.set_curve_fixed_axis(
                0,
                260,
                range(0, 261, 10),
                y_axis_config["min"],
                y_axis_config["max"],
                build_curve_axis_ticks(y_axis_config["min"], y_axis_config["max"], y_axis_config["interval"]),
            )
        if y_axis_font_size is not None:
            try:
                self.curve_y_axis_font_size = max(4, min(int(y_axis_font_size), 24))
            except Exception:
                self.curve_y_axis_font_size = 9
        self.image_source_path = ""
        self.image_pixmap = QPixmap()
        self.scaled_image_pixmap = QPixmap()
        self.scaled_image_cache_key = None
        self.curve_points = []
        self.curve_upper_limit_points = []
        self.curve_lower_limit_points = []
        self.curve_error_text = ""
        error_parts = []

        if self.curve_limit_source_path:
            limit_path = Path(self.curve_limit_source_path)
            if limit_path.exists():
                if self.curve_upper_limit_index is not None:
                    self.curve_upper_limit_points = parse_csv_curve_points(limit_path, self.curve_upper_limit_index)
                if self.curve_lower_limit_index is not None:
                    self.curve_lower_limit_points = parse_csv_curve_points(limit_path, self.curve_lower_limit_index)
            else:
                error_parts.append("未找到上下限CSV")

        if path_text:
            path = Path(path_text)
            if path.exists():
                curve_match_sn = extract_curve_match_sn_text(match_sn_text)
                if curve_match_sn:
                    self.curve_points, matched = parse_csv_curve_points_by_sn(path, curve_match_sn)
                    if not matched:
                        error_parts.append("未匹配当前编号曲线")
                else:
                    self.curve_points = parse_csv_curve_points(path, self.curve_series_index)
                self.curve_points = select_curve_points_segment(self.curve_points, curve_value_segment)
                if len(self.curve_points) < 2:
                    error_parts.append("CSV无有效数据")
            else:
                error_parts.append("未找到CSV")

        self.curve_error_text = " / ".join(error_parts)
        self.update()

    def can_edit_image_view(self):
        return self.image_editing_enabled and bool(self.image_source_path) and not self.image_pixmap.isNull()

    def wheelEvent(self, event):
        if not self.can_edit_image_view():
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if delta == 0:
            event.accept()
            return
        factor = 1.12 if delta > 0 else 1 / 1.12
        self.image_view_scale = max(0.2, min(self.image_view_scale * factor, 8.0))
        self.clamp_image_view_offset(self.rect().adjusted(4, 4, -4, -4))
        self.imageTransformChanged.emit(self.get_image_transform_state())
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if self.can_edit_image_view() and event.button() == Qt.RightButton:
            self.image_view_rotation = (int(self.image_view_rotation) + 90) % 360
            self.clamp_image_view_offset(self.rect().adjusted(4, 4, -4, -4))
            self.imageTransformChanged.emit(self.get_image_transform_state())
            self.update()
            event.accept()
            return
        if self.can_edit_image_view() and event.button() == Qt.LeftButton:
            self.image_dragging = True
            self.image_last_drag_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.image_dragging and self.image_last_drag_pos is not None:
            delta = event.pos() - self.image_last_drag_pos
            self.image_last_drag_pos = event.pos()
            self.image_view_offset_x += delta.x()
            self.image_view_offset_y += delta.y()
            self.clamp_image_view_offset(self.rect().adjusted(4, 4, -4, -4))
            self.imageTransformChanged.emit(self.get_image_transform_state())
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.image_dragging and event.button() == Qt.LeftButton:
            self.image_dragging = False
            self.image_last_drag_pos = None
            if self.image_editing_enabled:
                self.setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.can_edit_image_view() and event.button() == Qt.RightButton:
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        if self.image_editing_enabled:
            event.accept()
            return
        super().contextMenuEvent(event)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)

        if self.image_source_path:
            self.draw_image_pixmap(painter, rect)
            return

        if self.kind != "curve":
            self.paint_na_placeholder(painter, rect)
            return

        if self.kind == "curve":
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0, QColor("#4C77A6"))
            grad.setColorAt(1, QColor("#406B98"))
            painter.fillRect(rect, grad)

            compact_curve = rect.height() <= 90
            plot_left = rect.left() + (44 if compact_curve else 62)
            plot_right = rect.right() - 12
            plot_top = rect.top() + (8 if compact_curve else 14)
            plot_bottom = rect.bottom() - (18 if compact_curve else 30)
            plot_width = max(1.0, plot_right - plot_left)
            plot_height = max(1.0, plot_bottom - plot_top)
            fixed_axis = self.curve_fixed_axis if isinstance(self.curve_fixed_axis, dict) else None

            painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
            if fixed_axis:
                fixed_x_min = fixed_axis["x_min"]
                fixed_x_max = fixed_axis["x_max"]
                fixed_y_min = fixed_axis["y_min"]
                fixed_y_max = fixed_axis["y_max"]
                for tick in fixed_axis.get("y_ticks", []):
                    if fixed_y_max == fixed_y_min:
                        continue
                    y = plot_bottom - (tick - fixed_y_min) / (fixed_y_max - fixed_y_min) * plot_height
                    painter.drawLine(QPointF(plot_left, y), QPointF(plot_right, y))
                for tick in fixed_axis.get("x_ticks", []):
                    if fixed_x_max == fixed_x_min:
                        continue
                    x = plot_left + (tick - fixed_x_min) / (fixed_x_max - fixed_x_min) * plot_width
                    painter.drawLine(QPointF(x, plot_top), QPointF(x, plot_bottom))
            else:
                for i in range(5):
                    y = plot_top + i * plot_height / 4
                    painter.drawLine(QPointF(plot_left, y), QPointF(plot_right, y))
                for i in range(1, 4):
                    x = plot_left + i * plot_width / 4
                    painter.drawLine(QPointF(x, plot_top), QPointF(x, plot_bottom))

            axis_pen = QPen(QColor("#C9F2FF"), 1.1)
            painter.setPen(axis_pen)
            painter.drawLine(QPointF(plot_left, plot_bottom), QPointF(plot_right, plot_bottom))
            painter.drawLine(QPointF(plot_left, plot_bottom), QPointF(plot_left, plot_top))

            points = []
            upper_limit_points = []
            lower_limit_points = []
            has_source_points = len(self.curve_points) >= 2
            has_upper_limit_points = len(self.curve_upper_limit_points) >= 2
            has_lower_limit_points = len(self.curve_lower_limit_points) >= 2
            has_curve_data = has_source_points or has_upper_limit_points or has_lower_limit_points
            if has_curve_data:
                source_points = self.curve_points if has_source_points else []
                upper_limit_points = self.curve_upper_limit_points if has_upper_limit_points else []
                lower_limit_points = self.curve_lower_limit_points if has_lower_limit_points else []
                axis_points = list(source_points) + list(upper_limit_points) + list(lower_limit_points)
                max_points = 240
                if len(source_points) > max_points:
                    step = max(1, len(source_points) // max_points)
                    source_points = source_points[::step]
                    if source_points and source_points[-1] != self.curve_points[-1]:
                        source_points.append(self.curve_points[-1])
                if len(upper_limit_points) > max_points:
                    step = max(1, len(upper_limit_points) // max_points)
                    upper_limit_points = upper_limit_points[::step]
                    if upper_limit_points and upper_limit_points[-1] != self.curve_upper_limit_points[-1]:
                        upper_limit_points.append(self.curve_upper_limit_points[-1])
                if len(lower_limit_points) > max_points:
                    step = max(1, len(lower_limit_points) // max_points)
                    lower_limit_points = lower_limit_points[::step]
                    if lower_limit_points and lower_limit_points[-1] != self.curve_lower_limit_points[-1]:
                        lower_limit_points.append(self.curve_lower_limit_points[-1])

                all_points = axis_points
                if fixed_axis:
                    min_x, max_x = fixed_axis["x_min"], fixed_axis["x_max"]
                    min_y, max_y = fixed_axis["y_min"], fixed_axis["y_max"]
                else:
                    xs = [point[0] for point in all_points]
                    ys = [point[1] for point in all_points]
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                if max_x == min_x:
                    max_x = min_x + 1.0
                if max_y == min_y:
                    max_y = min_y + 1.0

                if source_points:
                    for x_value, y_value in source_points:
                        mapped_x_value = float(x_value) - 1.0 if fixed_axis and min_x == 0 else float(x_value)
                        x = plot_left + (mapped_x_value - min_x) / (max_x - min_x) * plot_width
                        y = plot_bottom - (y_value - min_y) / (max_y - min_y) * plot_height
                        points.append(QPointF(x, y))
            elif not self.curve_source_path and not self.curve_limit_source_path:
                self.paint_na_placeholder(painter, rect)
                return
            else:
                if fixed_axis:
                    min_x, max_x = fixed_axis["x_min"], fixed_axis["x_max"]
                    min_y, max_y = fixed_axis["y_min"], fixed_axis["y_max"]
                else:
                    min_x, max_x = 0.0, 1.0
                    min_y, max_y = 0.0, 1.0

            def map_curve_points(source_points):
                mapped = []
                for x_value, y_value in source_points:
                    mapped_x_value = float(x_value) - 1.0 if fixed_axis and min_x == 0 else float(x_value)
                    x = plot_left + (mapped_x_value - min_x) / (max_x - min_x) * plot_width
                    y = plot_bottom - (y_value - min_y) / (max_y - min_y) * plot_height
                    mapped.append(QPointF(x, y))
                return mapped

            painter.save()
            painter.setClipRect(QRectF(plot_left, plot_top, plot_width, plot_height))
            if len(upper_limit_points) >= 2:
                mapped_upper_points = map_curve_points(upper_limit_points)
                painter.setPen(QPen(self.curve_upper_limit_color, float(self.curve_upper_limit_width), self.curve_upper_limit_style, Qt.RoundCap, Qt.RoundJoin))
                upper_path = QPainterPath(mapped_upper_points[0])
                for point in mapped_upper_points[1:]:
                    upper_path.lineTo(point)
                painter.drawPath(upper_path)

            if len(lower_limit_points) >= 2:
                mapped_lower_points = map_curve_points(lower_limit_points)
                painter.setPen(QPen(self.curve_lower_limit_color, float(self.curve_lower_limit_width), self.curve_lower_limit_style, Qt.RoundCap, Qt.RoundJoin))
                lower_path = QPainterPath(mapped_lower_points[0])
                for point in mapped_lower_points[1:]:
                    lower_path.lineTo(point)
                painter.drawPath(lower_path)

            if len(points) >= 2:
                painter.setPen(QPen(QColor("#2F8CFF"), 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                path = QPainterPath(points[0])
                for point in points[1:]:
                    path.lineTo(point)
                painter.drawPath(path)
            painter.restore()

            tick_font = make_font(4 if compact_curve else 5, QFont.Bold)
            axis_label_font = make_font(6 if compact_curve else 7, QFont.Bold)
            y_axis_title_font = make_font(8 if compact_curve else 9, QFont.Bold)
            painter.setFont(tick_font)
            painter.setPen(QColor("#D4EEFF"))
            tick_top = plot_bottom + (4 if compact_curve else 5)
            axis_title_top = plot_bottom + (11 if compact_curve else 16)
            if fixed_axis:
                x_ticks = list(fixed_axis.get("x_ticks", []))
                label_step = 1
                if len(x_ticks) > 1:
                    labels = [
                        str(int(round(tick))) if abs(tick - round(tick)) < 1e-6 else format_axis_value(tick)
                        for tick in x_ticks
                    ]
                    max_label_w = max(QFontMetrics(tick_font).horizontalAdvance(label) for label in labels)
                    tick_px = plot_width / max(1, len(x_ticks) - 1)
                    label_step = max(1, int(math.ceil((max_label_w + 8) / max(1.0, tick_px))))
                max_tick = max(x_ticks) if x_ticks else None
                for tick_index, tick in enumerate(x_ticks):
                    if max_x == min_x:
                        continue
                    should_draw_label = (
                        tick_index == 0
                        or tick == max_tick
                        or tick_index % label_step == 0
                    )
                    if not should_draw_label:
                        continue
                    x = plot_left + (tick - min_x) / (max_x - min_x) * plot_width
                    label = str(int(round(tick))) if abs(tick - round(tick)) < 1e-6 else format_axis_value(tick)
                    align = Qt.AlignHCenter | Qt.AlignTop
                    label_rect = QRectF(x - 14, tick_top, 28, 12)
                    if abs(tick - min_x) < 1e-6:
                        align = Qt.AlignLeft | Qt.AlignTop
                        label_rect = QRectF(x, tick_top, 28, 12)
                    elif abs(tick - max_x) < 1e-6:
                        align = Qt.AlignRight | Qt.AlignTop
                        label_rect = QRectF(x - 28, tick_top, 28, 12)
                    painter.drawText(label_rect, align, label)
            else:
                x_mid = round((min_x + max_x) / 2.0)
                painter.drawText(QRectF(plot_left + 3, tick_top, 36, 12), Qt.AlignLeft | Qt.AlignTop, str(int(round(min_x))))
                painter.drawText(QRectF(plot_left + plot_width / 2 - 24, tick_top, 48, 12), Qt.AlignHCenter | Qt.AlignTop, str(int(x_mid)))
                painter.drawText(QRectF(plot_right - 18, tick_top, 36, 12), Qt.AlignRight | Qt.AlignTop, str(int(round(max_x))))
            painter.setFont(axis_label_font)
            painter.drawText(QRectF(plot_left - 12, axis_title_top, plot_width + 24, 12), Qt.AlignCenter, self.curve_x_axis_name)

            painter.setFont(tick_font)
            painter.setFont(y_axis_title_font)
            painter.drawText(QRectF(rect.left() + 2, rect.top() + 1, plot_left - rect.left() - 6, 9), Qt.AlignLeft | Qt.AlignVCenter, self.curve_y_axis_name)
            painter.setFont(tick_font)
            y_tick_left = rect.left() + 2
            y_tick_width = max(16, plot_left - y_tick_left - 4)
            if fixed_axis:
                y_ticks = list(fixed_axis.get("y_ticks", []))
                y_tick_font = make_font(self.curve_y_axis_font_size, QFont.Bold)
                painter.setFont(y_tick_font)
                y_label_height = max(6, QFontMetrics(y_tick_font).height() + 1)
                for tick in y_ticks:
                    if max_y == min_y:
                        continue
                    y = plot_bottom - (tick - min_y) / (max_y - min_y) * plot_height
                    painter.drawText(QRectF(y_tick_left, y - y_label_height / 2, y_tick_width, y_label_height), Qt.AlignRight | Qt.AlignVCenter, format_axis_value(tick))
            else:
                y_mid = (min_y + max_y) / 2.0
                painter.drawText(QRectF(y_tick_left, plot_top - 2, y_tick_width, 8), Qt.AlignRight | Qt.AlignVCenter, format_axis_value(max_y))
                if not compact_curve:
                    painter.drawText(QRectF(y_tick_left, plot_top + plot_height / 2 - 5, y_tick_width, 10), Qt.AlignRight | Qt.AlignVCenter, format_axis_value(y_mid))
                painter.drawText(QRectF(y_tick_left, plot_bottom - 3, y_tick_width, 8), Qt.AlignRight | Qt.AlignVCenter, format_axis_value(min_y))
            if self.curve_source_path and self.curve_error_text:
                painter.setPen(QColor(COLORS["muted"]))
                painter.setFont(make_font(8, QFont.Bold))
                painter.drawText(rect.adjusted(8, 6, -8, -6), Qt.AlignRight | Qt.AlignTop, self.curve_error_text)
            return

        if self.kind == "split":
            upper = QRectF(rect.left(), rect.top(), rect.width(), rect.height() * 0.48)
            lower = QRectF(rect.left(), rect.top() + rect.height() * 0.48, rect.width(), rect.height() * 0.52)
            painter.fillRect(upper, QColor("#756C5D"))
            painter.fillRect(lower, QColor("#98654C"))
            highlight = QRectF(rect.left(), rect.top(), rect.width() * 0.92, rect.height() * 0.92)
            painter.fillRect(highlight, QColor(255, 255, 255, 18))
            return

        if self.kind == "lines":
            painter.fillRect(rect, QColor("#8A593E"))
            strip_h = rect.height() / 3
            for i in range(3):
                r = QRectF(rect.left(), rect.top() + i * strip_h + 3, rect.width(), strip_h - 6)
                painter.fillRect(r, QColor("#9A6545"))
                painter.setPen(QPen(QColor("#48E48D"), 3))
                painter.drawLine(QPointF(r.left() + 8, r.center().y()), QPointF(r.right() - 8, r.center().y()))
                painter.setPen(QPen(QColor("#D32129"), 1))
                painter.drawLine(
                    QPointF(r.left() + 8, r.center().y() - 10),
                    QPointF(r.right() - 8, r.center().y() - 10),
                )
                painter.setPen(QPen(QColor("#9EE9FF"), 1))
                painter.drawLine(
                    QPointF(r.left() + 8, r.center().y() + 10),
                    QPointF(r.right() - 8, r.center().y() + 10),
                )
            return

        if self.kind in {"lens_left", "lens_right"}:
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0, QColor("#4D5B61"))
            grad.setColorAt(0.5, QColor("#B9C2C5"))
            grad.setColorAt(1, QColor("#6A767B"))
            painter.fillRect(rect, grad)
            center = QPointF(rect.center().x() + (-18 if self.kind == "lens_left" else 16), rect.center().y() - 8)
            painter.setBrush(QColor("#0D0E11"))
            painter.setPen(QPen(QColor("#272B31"), 6))
            painter.drawEllipse(center, rect.width() * 0.18, rect.width() * 0.18)
            painter.setBrush(QColor("#272B31"))
            painter.setPen(QPen(QColor("#565D63"), 2))
            painter.drawEllipse(center, rect.width() * 0.10, rect.width() * 0.10)
            painter.setBrush(QColor("#121318"))
            painter.drawEllipse(center, rect.width() * 0.045, rect.width() * 0.045)
            block = QRectF(
                rect.left() + rect.width() * (0.10 if self.kind == "lens_left" else 0.70),
                rect.bottom() - rect.height() * 0.28,
                rect.width() * 0.16,
                rect.height() * 0.14,
            )
            painter.save()
            painter.translate(block.center())
            painter.rotate(-25 if self.kind == "lens_left" else 25)
            painter.translate(-block.center())
            painter.setBrush(QColor("#2C3135"))
            painter.setPen(QPen(QColor("#59656C"), 3))
            painter.drawRect(block)
            painter.restore()
            return

        if self.kind == "dark_line":
            painter.fillRect(rect, QColor("#030408"))
            line_rect = QRectF(rect.left() + 24, rect.center().y() - 4, rect.width() - 48, 8)
            painter.fillRect(line_rect, QColor("#F5F6F8"))
            painter.setPen(QPen(QColor("#909090"), 1))
            painter.drawRect(rect)
            return

        if self.kind in {"arm_center", "arm_left", "arm_right"}:
            painter.fillRect(rect, QColor("#365E87"))
            base_rect = QRectF(rect.left(), rect.top() + rect.height() * 0.30, rect.width(), rect.height() * 0.36)
            painter.fillRect(base_rect, QColor("#1D2328"))
            body = QRectF(rect.left() + rect.width() * 0.18, rect.top() + rect.height() * 0.16, rect.width() * 0.62, rect.height() * 0.72)
            painter.setBrush(QColor("#3A2323"))
            painter.setPen(QPen(QColor("#191818"), 2))
            painter.drawRoundedRect(body, 14, 14)
            metal = QRectF(rect.left() + rect.width() * (0.08 if self.kind != "arm_right" else 0.68), rect.top() + rect.height() * 0.14, rect.width() * 0.18, rect.height() * 0.72)
            painter.fillRect(metal, QColor("#E0ECEF"))
            groove = QRectF(metal.left() + metal.width() * 0.35, metal.top(), metal.width() * 0.25, metal.height())
            painter.fillRect(groove, QColor("#23333D"))
            if self.kind == "arm_center":
                hole = QRectF(body.left() + body.width() * 0.05, body.center().y() - 14, 24, 28)
                painter.setBrush(QColor("#12181B"))
                painter.drawEllipse(hole)
            elif self.kind == "arm_left":
                painter.setBrush(QColor("#101518"))
                painter.drawEllipse(QPointF(body.right() - 12, body.center().y()), 12, 12)
            else:
                painter.setBrush(QColor("#101518"))
                painter.drawEllipse(QPointF(body.left() + 12, body.center().y()), 12, 12)
            return

        painter.fillRect(rect, QColor("#415E7A"))


class InspectionTile(QWidget):
    def __init__(self, title, state, state_kind, canvas_kind, parent=None):
        super().__init__(parent)
        self.default_title = title
        self.title = title
        self.state_text = str(state)
        self.state_kind = state_kind
        self.show_state_text = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(4)

        self.header_label = QLabel()
        self.header_label.setFont(make_font(10, QFont.Bold))
        self.header_label.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        self.refresh_header()
        layout.addWidget(self.header_label)

        self.canvas = DemoCanvas(canvas_kind)
        if canvas_kind == "curve":
            self.canvas.default_curve_y_axis_name = infer_curve_axis_name(title)
            self.canvas.set_curve_axis_labels(self.canvas.default_curve_y_axis_name, "点数")
            if "亮度" in title:
                self.canvas.set_curve_fixed_axis(0, 260, range(0, 261, 10), 0, 150, [0, 50, 100, 150])
            elif "斜率" in title:
                self.canvas.set_curve_fixed_axis(0, 260, range(0, 261, 10), -10, 10, [-10, -5, 0, 5, 10])
        self.canvas.setStyleSheet("background: transparent;")
        layout.addWidget(self.canvas, 1)

    def set_title(self, title):
        self.title = str(title or "").strip() or self.default_title
        self.refresh_header()

    def set_state_visibility(self, visible):
        self.show_state_text = bool(visible)
        self.refresh_header()

    def set_image_path(self, image_path):
        self.canvas.set_image_path(image_path)

    def clear_display(self):
        self.canvas.clear_display()

    def set_curve_csv_path(
        self,
        csv_path,
        series_index=0,
        y_axis_text=None,
        limit_csv_path=None,
        upper_limit_series_index=None,
        lower_limit_series_index=None,
        upper_limit_color=None,
        lower_limit_color=None,
        upper_limit_width=None,
        lower_limit_width=None,
        upper_limit_style=None,
        lower_limit_style=None,
        match_sn_text=None,
        curve_value_segment=None,
        y_axis_min=None,
        y_axis_max=None,
        y_axis_tick_interval=None,
        y_axis_font_size=None,
    ):
        self.canvas.set_curve_csv_path(
            csv_path,
            series_index,
            y_axis_text,
            limit_csv_path,
            upper_limit_series_index,
            lower_limit_series_index,
            upper_limit_color,
            lower_limit_color,
            upper_limit_width,
            lower_limit_width,
            upper_limit_style,
            lower_limit_style,
            match_sn_text,
            curve_value_segment,
            y_axis_min,
            y_axis_max,
            y_axis_tick_interval,
            y_axis_font_size,
        )

    def refresh_header(self):
        if not self.show_state_text or not self.state_text:
            self.header_label.setText(self.title)
            return

        state_map = {
            "ok": "#36E17E",
            "warn": "#F1D143",
            "bad": "#FF333C",
            "na": "#D2D8DE",
        }
        state_color = state_map.get(self.state_kind, state_map["na"])
        self.header_label.setText(f"{self.title} <font color='{state_color}'>{self.state_text}</font>")

    def set_status_text(self, text):
        self.state_text = "N/A" if is_missing_data_value(text) else str(text).strip()
        self.state_kind = normalize_status_kind(self.state_text)
        self.refresh_header()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, QColor("#4C7AAA"))
        grad.setColorAt(1, QColor("#456F9E"))
        painter.fillRect(rect, grad)
        painter.setPen(QPen(QColor("#12283A"), 2))
        painter.drawRect(rect)


class DashboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE_TEXT)
        self.setMinimumSize(900, 520)
        self.settings_mode = False
        self.binding_config = self.load_binding_config()
        self.binding_targets = {}
        self.bindable_widgets = []
        self.result_rows = {}
        self.production_values = {}
        self.red_rabbit_values = {}
        self.inspection_tiles = {}
        self.rabbit_signal_widget = None
        self.production_chart = None
        self.total_result_widget = None
        self._handling_fullscreen_state = False
        self._cover_taskbar_mode = False
        self._suppress_auto_fullscreen = False

        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(
            f"""
            QWidget {{
                background: {COLORS['bg']};
                color: {COLORS['text']};
            }}
            """
        )

        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 6, 6)
        root.setSpacing(8)

        self.header = HeaderTag()
        self.header.set_main_title(self.get_main_title())
        self.header.set_info_font_size(self.get_header_info_font_size())
        self.header.title_label.setProperty("main_title_action", True)
        self.header.title_label.installEventFilter(self)
        root.addWidget(self.header)
        self.register_binding_target("online_sn", "当前编号", self.header.left_sn, self.header.set_online_sn)
        self.register_binding_target("pending_sn", "待处理编号", self.header.right_sn, self.header.set_pending_sn)
        self.register_binding_target("online_color", "当前颜色", self.header.left_color, self.header.set_online_color)
        self.register_binding_target("pending_color", "待处理颜色", self.header.right_color, self.header.set_pending_color)

        upper = QHBoxLayout()
        upper.setSpacing(8)
        root.addLayout(upper, 1)

        left_col = QVBoxLayout()
        left_col.setSpacing(8)
        upper.addLayout(left_col, 37)

        right_col = QVBoxLayout()
        right_col.setSpacing(8)
        upper.addLayout(right_col, 63)

        left_col.addWidget(self.build_total_result_panel(), 1)
        left_col.addWidget(self.build_item_results_panel(), 1)

        right_col.addWidget(self.build_inspection_panel(), 1)

        lower = QHBoxLayout()
        lower.setSpacing(8)
        root.addLayout(lower)
        lower.addWidget(self.build_production_panel(), 1)
        lower.addWidget(self.build_red_rabbit_panel(), 1)
        self.status_legend = GlobalStatusLegend()
        self.status_legend.settingsDoubleClicked.connect(self.toggle_settings_mode)
        self.status_legend.settingsClicked.connect(self.handle_settings_button_clicked)
        self.status_legend.pollIntervalChanged.connect(self.set_poll_interval_ms)
        self.status_legend.topMostChanged.connect(self.set_top_most_enabled)
        root.addWidget(self.status_legend)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_bound_values)
        self.status_legend.set_poll_interval_ms(self.get_poll_interval_ms())
        self.status_legend.set_top_most_enabled(self.get_top_most_enabled())
        self.apply_top_most_flag(self.get_top_most_enabled())
        self.refresh_timer.start(self.get_poll_interval_ms())

        self.escape_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.escape_shortcut.setContext(Qt.ApplicationShortcut)
        self.escape_shortcut.activated.connect(self.exit_cover_taskbar_mode)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self.apply_settings_mode_ui()
        self.refresh_bound_values()
        self.fit_to_screen()

    def fit_to_screen(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1440, 820)
            return

        available = screen.availableGeometry()
        target_width = min(1600, int(available.width() * 0.96))
        target_height = min(900, int(available.height() * 0.94))

        target_width = max(900, min(target_width, available.width()))
        target_height = max(520, min(target_height, available.height()))

        self.resize(target_width, target_height)

        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() != QEvent.WindowStateChange:
            return
        if self._handling_fullscreen_state:
            return
        if self.isFullScreen():
            QTimer.singleShot(0, self.apply_cover_taskbar_geometry)
        elif self.windowState() & Qt.WindowMaximized and not self._suppress_auto_fullscreen:
            QTimer.singleShot(0, self.enter_cover_taskbar_fullscreen)

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._handling_fullscreen_state:
            return
        if self.isFullScreen():
            QTimer.singleShot(0, self.apply_cover_taskbar_geometry)
        elif self.windowState() & Qt.WindowMaximized and not self._suppress_auto_fullscreen:
            QTimer.singleShot(0, self.enter_cover_taskbar_fullscreen)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._handling_fullscreen_state:
            return
        if self.isFullScreen():
            QTimer.singleShot(0, self.apply_cover_taskbar_geometry)
        elif self.windowState() & Qt.WindowMaximized and not self._suppress_auto_fullscreen:
            QTimer.singleShot(0, self.enter_cover_taskbar_fullscreen)

    def get_current_screen_geometry(self):
        center = self.frameGeometry().center()
        screen = None
        try:
            screen = QApplication.screenAt(center)
        except Exception:
            screen = None
        if screen is None and self.windowHandle() is not None:
            screen = self.windowHandle().screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        return screen.geometry() if screen is not None else None

    def apply_cover_taskbar_geometry(self):
        if self._handling_fullscreen_state or not self.isFullScreen():
            return
        self._handling_fullscreen_state = True
        self.raise_()
        self.activateWindow()
        self._handling_fullscreen_state = False

    def enter_cover_taskbar_fullscreen(self):
        if self._handling_fullscreen_state or self.isFullScreen():
            return
        self._handling_fullscreen_state = True
        self.showFullScreen()
        self._cover_taskbar_mode = True
        self.raise_()
        self._handling_fullscreen_state = False
        QTimer.singleShot(0, self.apply_cover_taskbar_geometry)
        QTimer.singleShot(80, self.apply_cover_taskbar_geometry)
        QTimer.singleShot(260, self.apply_cover_taskbar_geometry)

    def exit_cover_taskbar_mode(self):
        if not self._cover_taskbar_mode and not self.isFullScreen():
            return
        self._handling_fullscreen_state = True
        self._suppress_auto_fullscreen = True
        self._cover_taskbar_mode = False
        self.showNormal()
        self.setWindowState(Qt.WindowNoState)
        self.fit_to_screen()
        self._handling_fullscreen_state = False
        self.apply_top_most_flag(self.get_top_most_enabled())
        QTimer.singleShot(600, lambda: setattr(self, "_suppress_auto_fullscreen", False))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and (self._cover_taskbar_mode or self.isFullScreen()):
            self.exit_cover_taskbar_mode()
            event.accept()
            return
        super().keyPressEvent(event)

    def load_binding_config(self):
        default = {
            "ini_dir": "",
            "csv_dir": "",
            "main_title": DEFAULT_MAIN_TITLE,
            "header_info_font_size": 0,
            "fields": {},
            "poll_interval_ms": 1200,
            "top_most_enabled": True,
            "result_item_font_size": 0,
            "custom_titles": {},
            "tile_title_links": {},
            "tile_status_links": {},
            "tile_custom_titles": {},
            "image_view_states": {},
            "result_items": [],
        }
        self.config_path = None
        data = None
        for candidate in get_config_path_candidates():
            if not candidate.exists():
                continue
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                self.config_path = candidate
                break
            except Exception:
                continue
        if data is None:
            candidates = get_config_path_candidates()
            self.config_path = candidates[0] if candidates else None
            return default
        if not isinstance(data, dict):
            return default
        data.setdefault("ini_dir", "")
        data.setdefault("csv_dir", "")
        data.setdefault("main_title", DEFAULT_MAIN_TITLE)
        data.setdefault("header_info_font_size", 0)
        data.setdefault("fields", {})
        data.setdefault("poll_interval_ms", 1200)
        data.setdefault("top_most_enabled", True)
        data.setdefault("result_item_font_size", 0)
        data.setdefault("custom_titles", {})
        data.setdefault("tile_title_links", {})
        data.setdefault("tile_status_links", {})
        data.setdefault("tile_custom_titles", {})
        data.setdefault("image_view_states", {})
        data.setdefault("result_items", [])
        fields = data.get("fields") if isinstance(data.get("fields"), dict) else {}
        custom_titles = data.get("custom_titles") if isinstance(data.get("custom_titles"), dict) else {}
        tile_title_links = data.get("tile_title_links") if isinstance(data.get("tile_title_links"), dict) else {}
        tile_status_links = data.get("tile_status_links") if isinstance(data.get("tile_status_links"), dict) else {}
        tile_custom_titles = data.get("tile_custom_titles") if isinstance(data.get("tile_custom_titles"), dict) else {}
        image_view_states = data.get("image_view_states") if isinstance(data.get("image_view_states"), dict) else {}
        result_items = data.get("result_items") if isinstance(data.get("result_items"), list) else None
        legacy_color = fields.get("part_color")
        if isinstance(legacy_color, dict):
            if "online_color" not in fields:
                fields["online_color"] = dict(legacy_color)
            if "pending_color" not in fields:
                fields["pending_color"] = dict(legacy_color)
        for field_id, binding in fields.items():
            if not str(field_id).startswith("result_") or not isinstance(binding, dict):
                continue
            legacy_display_name = str(binding.pop("display_name", "") or "").strip()
            if legacy_display_name and field_id not in custom_titles:
                custom_titles[field_id] = legacy_display_name
        if result_items is None:
            result_items = []
            for field_id, default_title, _state, _kind in DEFAULT_RESULT_ROW_SPECS:
                result_items.append(
                    {
                        "id": field_id,
                        "title": custom_titles.get(field_id, default_title),
                        "limit_enabled": False,
                        "lower_limit": "",
                        "lower_operator": DEFAULT_LOWER_LIMIT_OPERATOR,
                        "upper_limit": "",
                        "upper_operator": DEFAULT_UPPER_LIMIT_OPERATOR,
                    }
                )
        else:
            normalized_items = []
            for item in result_items:
                if not isinstance(item, dict):
                    continue
                field_id = str(item.get("id", "") or "").strip()
                title = str(item.get("title", "") or "").strip()
                if not field_id:
                    continue
                if not title:
                    title = custom_titles.get(field_id, DEFAULT_RESULT_ROW_TITLES.get(field_id, field_id))
                normalized_items.append(
                    {
                        "id": field_id,
                        "title": title,
                        "limit_enabled": bool(item.get("limit_enabled")),
                        "lower_limit": str(item.get("lower_limit", "") or "").strip(),
                        "lower_operator": normalize_lower_limit_operator(item.get("lower_operator")),
                        "upper_limit": str(item.get("upper_limit", "") or "").strip(),
                        "upper_operator": normalize_upper_limit_operator(item.get("upper_operator")),
                    }
                )
            result_items = normalized_items
        data["custom_titles"] = custom_titles
        data["tile_title_links"] = tile_title_links
        data["tile_status_links"] = tile_status_links
        data["tile_custom_titles"] = tile_custom_titles
        data["image_view_states"] = image_view_states
        data["result_items"] = result_items
        return data

    def save_binding_config(self):
        serialized = json.dumps(self.binding_config, ensure_ascii=False, indent=2)
        candidates = []
        current = getattr(self, "config_path", None)
        if current:
            candidates.append(Path(current))
        for candidate in get_config_path_candidates():
            if candidate not in candidates:
                candidates.append(candidate)

        last_error = None
        for candidate in candidates:
            try:
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_text(serialized, encoding="utf-8")
                self.config_path = candidate
                return
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            QMessageBox.warning(
                self,
                "保存失败",
                f"参数修改后未能写入配置文件，请检查程序目录或用户配置目录权限。\n最后错误：{last_error}",
            )

    def get_ini_dir(self):
        value = self.binding_config.get("ini_dir", "")
        return Path(value) if value else None

    def get_csv_dir(self):
        value = self.binding_config.get("csv_dir", "")
        return Path(value) if value else None

    def get_config_font_size(self, key):
        try:
            return max(0, min(int(self.binding_config.get(key, 0) or 0), 24))
        except Exception:
            return 0

    def get_header_info_font_size(self):
        return self.get_config_font_size("header_info_font_size")

    def get_result_item_font_size(self):
        return self.get_config_font_size("result_item_font_size")

    def get_main_title(self):
        title = str(self.binding_config.get("main_title", "") or "").strip()
        if not title or title in LEGACY_MAIN_TITLES:
            return DEFAULT_MAIN_TITLE
        return title

    def configure_main_title(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("主标题设置")
        dialog.setModal(True)
        dialog.resize(420, 150)
        apply_compact_dialog_style(dialog, 8)

        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        form.setSpacing(8)
        layout.addLayout(form)

        title_edit = QLineEdit(self.get_main_title())
        form.addRow("主标题", title_edit)

        info_font_spin = QSpinBox()
        info_font_spin.setRange(0, 24)
        info_font_spin.setSpecialValueText("自动")
        info_font_spin.setValue(self.get_header_info_font_size())
        info_font_spin.setMaximumWidth(86)
        form.addRow("编号/颜色字体", info_font_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() != QDialog.Accepted:
            return
        clean_title = str(title_edit.text() or "").strip() or DEFAULT_MAIN_TITLE
        info_font_size = max(0, min(int(info_font_spin.value()), 24))
        self.binding_config["main_title"] = clean_title
        self.binding_config["header_info_font_size"] = info_font_size
        self.header.set_main_title(clean_title)
        self.header.set_info_font_size(info_font_size)
        self.save_binding_config()

    def use_sn_filename_target_file(self, field_id):
        if field_id == "total_result":
            return True
        if str(field_id).startswith("result_"):
            return True
        if str(field_id).startswith("inspect_image_"):
            return True
        return False

    def get_default_sn_target_binding(self, field_id):
        text_defaults = {
            "total_result": {"key": "总结果", "section": "Total_Results"},
            "result_1": {"key": "指标1", "section": "InspectionData"},
            "result_2": {"key": "指标2", "section": "InspectionData"},
            "result_3": {"key": "指标3", "section": "InspectionData"},
            "result_4": {"key": "指标4", "section": "InspectionData"},
            "result_5": {"key": "指标5", "section": "InspectionData"},
            "result_6": {"key": "指标6", "section": "InspectionData"},
            "result_7": {"key": "指标7", "section": "InspectionData"},
            "result_8": {"key": "指标8", "section": "InspectionData"},
            "result_9": {"key": "指标9", "section": "InspectionData"},
            "result_10": {"key": "指标10", "section": "InspectionData"},
        }
        image_defaults = {
            "inspect_image_3": {"type": "image", "path_section": "Patch", "path_key": "示例图像1"},
            "inspect_image_4": {"type": "image", "path_section": "Patch", "path_key": "示例图像2"},
            "inspect_image_5": {"type": "image", "path_section": "Patch", "path_key": "示例图像3"},
            "inspect_image_6": {"type": "image", "path_section": "Patch", "path_key": "示例图像4"},
            "inspect_image_7": {"type": "image", "path_section": "Patch", "path_key": "示例图像5"},
            "inspect_image_8": {"type": "image", "path_section": "Patch", "path_key": "示例图像6"},
            "inspect_image_9": {"type": "image", "path_section": "Patch", "path_key": "示例图像7"},
            "inspect_image_10": {"type": "image", "path_section": "Patch", "path_key": "示例图像8"},
        }
        curve_defaults = {
            "inspect_image_1": {"type": "csv_curve", "path_section": "LedData", "path_key": "数据路径", "series_index": 0, "y_axis_name": "亮度"},
            "inspect_image_2": {"type": "csv_curve", "path_section": "LedData", "path_key": "数据路径", "series_index": 1, "y_axis_name": "斜率"},
        }

        if field_id in text_defaults:
            return dict(text_defaults[field_id])
        if field_id in image_defaults:
            return dict(image_defaults[field_id])
        if field_id in curve_defaults:
            return dict(curve_defaults[field_id])
        return None

    def get_poll_interval_ms(self):
        try:
            value = int(self.binding_config.get("poll_interval_ms", 1200))
        except Exception:
            value = 1200
        return max(50, min(value, 600000))

    def set_poll_interval_ms(self, value):
        safe_value = max(50, min(int(value), 600000))
        self.binding_config["poll_interval_ms"] = safe_value
        if hasattr(self, "refresh_timer"):
            self.refresh_timer.setInterval(safe_value)
        if hasattr(self, "status_legend"):
            self.status_legend.set_poll_interval_ms(safe_value)
        self.save_binding_config()

    def get_top_most_enabled(self):
        value = self.binding_config.get("top_most_enabled", True)
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "off", "否", "关闭"}
        return bool(value)

    def apply_top_most_flag(self, enabled):
        geometry = self.geometry()
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(enabled))
        self.setGeometry(geometry)
        if was_visible:
            self.show()
            self.raise_()

    def set_top_most_enabled(self, enabled):
        top_most = bool(enabled)
        self.binding_config["top_most_enabled"] = top_most
        if hasattr(self, "status_legend"):
            self.status_legend.set_top_most_enabled(top_most)
        self.apply_top_most_flag(top_most)
        self.save_binding_config()

    def get_image_view_state(self, field_id):
        states = self.binding_config.setdefault("image_view_states", {})
        if not isinstance(states, dict):
            states = {}
            self.binding_config["image_view_states"] = states
        state = states.get(field_id, {})
        if not isinstance(state, dict):
            return {}
        return {
            "scale": max(0.2, min(safe_float_value(state.get("scale", 1.0), 1.0), 8.0)),
            "offset_x": safe_float_value(state.get("offset_x", 0.0), 0.0),
            "offset_y": safe_float_value(state.get("offset_y", 0.0), 0.0),
            "rotation": int(safe_float_value(state.get("rotation", 0), 0)) % 360,
        }

    def set_image_view_state(self, field_id, state):
        if not str(field_id).startswith("inspect_image_") or not isinstance(state, dict):
            return
        states = self.binding_config.setdefault("image_view_states", {})
        if not isinstance(states, dict):
            states = {}
            self.binding_config["image_view_states"] = states
        states[field_id] = {
            "scale": max(0.2, min(safe_float_value(state.get("scale", 1.0), 1.0), 8.0)),
            "offset_x": safe_float_value(state.get("offset_x", 0.0), 0.0),
            "offset_y": safe_float_value(state.get("offset_y", 0.0), 0.0),
            "rotation": int(safe_float_value(state.get("rotation", 0), 0)) % 360,
        }
        self.save_binding_config()

    def choose_ini_folder(self):
        start_dir = str(self.get_ini_dir() or Path.cwd())
        selected = QFileDialog.getExistingDirectory(self, "选择 INI 文件夹", start_dir)
        if not selected:
            return False
        self.binding_config["ini_dir"] = selected
        self.save_binding_config()
        return True

    def toggle_settings_mode(self):
        self.settings_mode = not self.settings_mode
        self.apply_settings_mode_ui()
        if self.settings_mode:
            QMessageBox.information(
                self,
                "设置模式",
                "已进入设置模式。\n请双击需要绑定的数据项，再选择 INI 文件夹和带 ### 标记的 INI 键值行。\n中上方主标题可双击修改；左侧“分项结果”双击后可修改显示名称；右侧图块标题双击后可绑定左侧名称或自定义名称。",
            )

    def handle_settings_button_clicked(self):
        pass

    def apply_settings_mode_ui(self):
        self.header.set_settings_mode(self.settings_mode)
        self.status_legend.set_settings_mode(self.settings_mode)
        cursor = Qt.PointingHandCursor if self.settings_mode else Qt.ArrowCursor
        tooltip = "设置模式下双击进行 INI 绑定；左侧分项可改名，右侧标题可绑定左侧或自定义" if self.settings_mode else ""
        self.header.title_label.setCursor(cursor)
        self.header.title_label.setToolTip("设置模式下双击可修改中上方主标题" if self.settings_mode else "")
        for widget in self.bindable_widgets:
            widget.setCursor(cursor)
            widget.setToolTip(tooltip)
        for tile in self.inspection_tiles.values():
            if hasattr(tile, "canvas"):
                tile.canvas.set_settings_mode(self.settings_mode)
        if hasattr(self, "item_results_panel"):
            self.item_results_panel.header.setCursor(cursor)
            self.item_results_panel.header.setToolTip("设置模式下点击可新增或删除左侧分项结果" if self.settings_mode else "")

    def get_default_result_row_title(self, field_id):
        return DEFAULT_RESULT_ROW_TITLES.get(str(field_id), "")

    def is_result_row_setup_title(self, field_id, title_text):
        clean_title = str(title_text or "").strip()
        if not clean_title:
            return True
        if is_builtin_result_title(clean_title):
            return True
        binding = self.binding_config.get("fields", {}).get(field_id, {})
        if isinstance(binding, dict):
            binding_key = str(binding.get("key", "") or "").strip()
            if binding_key and clean_title == binding_key:
                return True
        return False

    def format_result_row_display_title(self, field_id, title_text):
        clean_title = str(title_text or "").strip()
        if self.is_result_row_setup_title(field_id, clean_title):
            return DEFAULT_SETUP_TITLE
        return clean_title

    def get_default_result_row_spec(self, field_id):
        for spec_field_id, title, state, kind in DEFAULT_RESULT_ROW_SPECS:
            if spec_field_id == field_id:
                return {"id": spec_field_id, "title": title, "state": state, "kind": kind}
        return {"id": str(field_id), "title": self.get_default_result_row_title(field_id) or str(field_id), "state": "OK", "kind": "ok"}

    def get_result_item_entries(self):
        entries = self.binding_config.setdefault("result_items", [])
        if not isinstance(entries, list):
            entries = []
            self.binding_config["result_items"] = entries
        for item in entries:
            if not isinstance(item, dict):
                continue
            item.setdefault("title", "")
            item.setdefault("limit_enabled", False)
            item.setdefault("lower_limit", "")
            item["lower_operator"] = normalize_lower_limit_operator(item.get("lower_operator"))
            item.setdefault("upper_limit", "")
            item["upper_operator"] = normalize_upper_limit_operator(item.get("upper_operator"))
        return entries

    def find_result_item_entry(self, field_id):
        for item in self.get_result_item_entries():
            if str(item.get("id", "") or "").strip() == str(field_id):
                return item
        return None

    def get_result_row_display_name(self, field_id, fallback_text=""):
        item = self.find_result_item_entry(field_id)
        if isinstance(item, dict):
            item_title = str(item.get("title", "") or "").strip()
            if item_title:
                return self.format_result_row_display_title(field_id, item_title)
        custom_titles = self.binding_config.get("custom_titles", {})
        if isinstance(custom_titles, dict):
            custom_value = str(custom_titles.get(field_id, "") or "").strip()
            if custom_value:
                return self.format_result_row_display_title(field_id, custom_value)
        fallback = str(fallback_text or "").strip()
        return self.format_result_row_display_title(field_id, fallback or self.get_default_result_row_title(field_id))

    def apply_result_row_display_name(self, field_id):
        row = self.result_rows.get(field_id)
        display_name = self.get_result_row_display_name(field_id, row.label_text if row is not None else "")
        if row is not None:
            row.set_label_text(display_name)
        target = self.binding_targets.get(field_id)
        if target and str(field_id).startswith("result_"):
            try:
                index = int(str(field_id).split("_", 1)[1])
            except Exception:
                index = 0
            target["title"] = f"分项结果/{index} {display_name}"

    def set_result_row_custom_title(self, field_id, title_text):
        if not str(field_id).startswith("result_"):
            return
        custom_titles = self.binding_config.setdefault("custom_titles", {})
        clean_title = str(title_text or "").strip()
        default_title = self.get_default_result_row_title(field_id)
        entry = self.find_result_item_entry(field_id)
        if isinstance(entry, dict) and clean_title:
            entry["title"] = clean_title
        if not clean_title or clean_title == default_title:
            custom_titles.pop(field_id, None)
        else:
            custom_titles[field_id] = clean_title
        self.apply_result_row_display_name(field_id)
        self.apply_all_inspection_tile_title_bindings()

    def get_result_row_binding_options(self):
        options = []
        for index, item in enumerate(self.get_result_item_entries(), start=1):
            field_id = str(item.get("id", "") or "").strip()
            if not field_id:
                continue
            display_name = self.get_result_row_display_name(field_id, self.get_default_result_row_title(field_id))
            options.append((field_id, f"{index} {display_name}"))
        return options

    def get_result_item_limit_config(self, field_id):
        item = self.find_result_item_entry(field_id)
        if not isinstance(item, dict) or not item.get("limit_enabled"):
            return None
        lower_value = parse_numeric_value_from_text(item.get("lower_limit", ""))
        upper_value = parse_numeric_value_from_text(item.get("upper_limit", ""))
        if lower_value is None and upper_value is None:
            return None
        return {
            "lower": lower_value,
            "lower_operator": normalize_lower_limit_operator(item.get("lower_operator")),
            "upper": upper_value,
            "upper_operator": normalize_upper_limit_operator(item.get("upper_operator")),
        }

    def evaluate_result_status_kind(self, field_id, value):
        if is_missing_data_value(value):
            return "na"
        limit_config = self.get_result_item_limit_config(field_id)
        if limit_config:
            numeric_value = parse_numeric_value_from_text(value)
            if numeric_value is not None:
                lower_limit = limit_config.get("lower")
                upper_limit = limit_config.get("upper")
                lower_operator = normalize_lower_limit_operator(limit_config.get("lower_operator"))
                upper_operator = normalize_upper_limit_operator(limit_config.get("upper_operator"))
                lower_failed = lower_limit is not None and (
                    numeric_value <= lower_limit if lower_operator == "<" else numeric_value < lower_limit
                )
                upper_failed = upper_limit is not None and (
                    numeric_value >= upper_limit if upper_operator == ">" else numeric_value > upper_limit
                )
                if lower_failed or upper_failed:
                    return "bad"
                return "ok"
        return normalize_status_kind(value)

    def apply_result_row_value(self, field_id, value):
        row = self.result_rows.get(field_id)
        status_kind = self.evaluate_result_status_kind(field_id, value)
        display_value = "N/A" if status_kind == "na" else str(value).strip()
        if row is not None:
            row.set_status_text(display_value, status_kind)

        linked_tile_map = {
            "result_3": "inspect_image_3",
            "result_4": "inspect_image_4",
            "result_5": "inspect_image_5",
            "result_6": "inspect_image_6",
            "result_7": "inspect_image_7",
        }
        tile_id = linked_tile_map.get(field_id)
        if tile_id:
            tile = self.inspection_tiles.get(tile_id)
            if tile is not None:
                tile.state_text = display_value
                tile.state_kind = status_kind
                tile.refresh_header()
        self.apply_tile_status_bindings_for_field(field_id)

    def generate_result_item_id(self):
        existing = {str(item.get("id", "") or "").strip() for item in self.get_result_item_entries()}
        index = 1
        while True:
            candidate = f"result_extra_{index}"
            if candidate not in existing:
                return candidate
            index += 1

    def remove_binding_target(self, field_id):
        target = self.binding_targets.pop(field_id, None)
        if not target:
            return
        for widget in target.get("widgets", []):
            if widget in self.bindable_widgets:
                try:
                    self.bindable_widgets.remove(widget)
                except Exception:
                    pass
            try:
                widget.removeEventFilter(self)
            except Exception:
                pass
            try:
                widget.setProperty("binding_target_id", None)
            except Exception:
                pass

    def clear_layout_widgets(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self.clear_layout_widgets(child_layout)

    def rebuild_item_result_rows(self):
        if not hasattr(self, "item_results_panel"):
            return
        existing_ids = list(self.result_rows.keys())
        for field_id in existing_ids:
            self.remove_binding_target(field_id)
        self.result_rows = {}
        self.clear_layout_widgets(self.item_results_panel.content_layout)

        entries = self.get_result_item_entries()
        row_count = max(1, len(entries))
        for index, item in enumerate(entries, start=1):
            field_id = str(item.get("id", "") or "").strip()
            if not field_id:
                continue
            spec = self.get_default_result_row_spec(field_id)
            display_text = self.get_result_row_display_name(field_id, str(item.get("title", "") or "").strip() or spec["title"])
            row = ResultRow(index, display_text, spec["state"], spec["kind"])
            row.apply_density(row_count, self.get_result_item_font_size())
            self.result_rows[field_id] = row
            self.item_results_panel.content_layout.addWidget(row, 1)
            setter = lambda value, field_id=field_id: self.apply_result_row_value(field_id, value)
            self.register_binding_target(
                field_id,
                f"分项结果/{index} {display_text}",
                [row, row.left_label, row.status_label],
                setter,
            )
        self.apply_all_inspection_tile_title_bindings()

    def configure_result_items_panel(self):
        current_items = self.get_result_item_entries()
        dialog = ResultItemsManagerDialog(current_items, self.get_result_item_font_size(), self)
        if dialog.exec_() != QDialog.Accepted:
            return
        result_items = dialog.get_result()
        new_items = []
        seen_ids = set()
        for item in result_items:
            title = str(item.get("title", "") or "").strip()
            if not title:
                continue
            field_id = str(item.get("id", "") or "").strip()
            if not field_id:
                field_id = self.generate_result_item_id()
            if field_id in seen_ids:
                continue
            seen_ids.add(field_id)
            new_items.append(
                {
                    "id": field_id,
                    "title": title,
                    "limit_enabled": bool(item.get("limit_enabled")),
                    "lower_limit": str(item.get("lower_limit", "") or "").strip(),
                    "lower_operator": normalize_lower_limit_operator(item.get("lower_operator")),
                    "upper_limit": str(item.get("upper_limit", "") or "").strip(),
                    "upper_operator": normalize_upper_limit_operator(item.get("upper_operator")),
                }
            )

        old_ids = {str(item.get("id", "") or "").strip() for item in current_items}
        new_ids = {str(item.get("id", "") or "").strip() for item in new_items}
        removed_ids = {field_id for field_id in old_ids if field_id and field_id not in new_ids}

        self.binding_config["result_items"] = new_items
        self.binding_config["result_item_font_size"] = dialog.get_font_size()
        custom_titles = self.binding_config.setdefault("custom_titles", {})
        fields = self.binding_config.setdefault("fields", {})
        tile_links = self.binding_config.setdefault("tile_title_links", {})
        tile_status_links = self.binding_config.setdefault("tile_status_links", {})
        for field_id in removed_ids:
            fields.pop(field_id, None)
            custom_titles.pop(field_id, None)
            for tile_id, linked_field_id in list(tile_links.items()):
                if linked_field_id == field_id:
                    tile_links.pop(tile_id, None)
            for tile_id, linked_field_ids in list(tile_status_links.items()):
                if not isinstance(linked_field_ids, list):
                    continue
                filtered = [linked_id for linked_id in linked_field_ids if linked_id != field_id]
                if filtered:
                    tile_status_links[tile_id] = filtered
                else:
                    tile_status_links.pop(tile_id, None)

        self.rebuild_item_result_rows()
        self.save_binding_config()
        self.refresh_bound_values()

    def get_default_inspection_tile_title(self, field_id):
        default_title = DEFAULT_INSPECTION_TILE_TITLES.get(str(field_id), "")
        if is_builtin_tile_title(default_title):
            return default_tile_setup_title(field_id)
        return default_title

    def get_inspection_tile_custom_title(self, tile_id):
        custom_titles = self.binding_config.get("tile_custom_titles", {})
        if not isinstance(custom_titles, dict):
            return ""
        return str(custom_titles.get(tile_id, "") or "").strip()

    def get_inspection_tile_status_links(self, tile_id):
        tile_status_links = self.binding_config.get("tile_status_links", {})
        if not isinstance(tile_status_links, dict):
            return []
        linked_ids = tile_status_links.get(tile_id, [])
        if isinstance(linked_ids, str):
            linked_ids = [linked_ids]
        if not isinstance(linked_ids, list):
            return []
        return [str(field_id).strip() for field_id in linked_ids if str(field_id).strip()]

    def get_aggregated_tile_status(self, tile_id):
        linked_ids = self.get_inspection_tile_status_links(tile_id)
        if not linked_ids:
            return None
        kinds = []
        for field_id in linked_ids:
            row = self.result_rows.get(field_id)
            if row is None:
                kinds.append("na")
            else:
                kinds.append(row.current_status_kind)
        if any(kind == "bad" for kind in kinds):
            return "NG", "bad"
        if kinds and all(kind == "ok" for kind in kinds):
            return "OK", "ok"
        if any(kind == "warn" for kind in kinds):
            return "NG", "bad"
        return "N/A", "na"

    def apply_tile_status_binding(self, tile_id):
        tile = self.inspection_tiles.get(tile_id)
        if tile is None:
            return False
        status = self.get_aggregated_tile_status(tile_id)
        if status is None:
            return False
        tile.state_text, tile.state_kind = status
        tile.refresh_header()
        return True

    def apply_tile_status_bindings_for_field(self, field_id):
        tile_status_links = self.binding_config.get("tile_status_links", {})
        if not isinstance(tile_status_links, dict):
            return
        for tile_id, linked_ids in tile_status_links.items():
            if isinstance(linked_ids, str):
                linked_ids = [linked_ids]
            if isinstance(linked_ids, list) and field_id in linked_ids:
                self.apply_tile_status_binding(tile_id)

    def apply_inspection_tile_title_binding(self, tile_id):
        tile = self.inspection_tiles.get(tile_id)
        if tile is None:
            return
        custom_title = self.get_inspection_tile_custom_title(tile_id)
        tile_links = self.binding_config.get("tile_title_links", {})
        status_links = self.get_inspection_tile_status_links(tile_id)
        linked_field_id = tile_links.get(tile_id, "") if isinstance(tile_links, dict) else ""
        if custom_title:
            title_text = custom_title
        elif linked_field_id and linked_field_id in self.result_rows:
            title_text = self.result_rows[linked_field_id].left_label.text().strip()
        else:
            title_text = self.get_default_inspection_tile_title(tile_id) or tile.default_title
        show_state_text = bool(status_links) or bool(linked_field_id and linked_field_id in self.result_rows)
        tile.set_title(title_text)
        tile.set_state_visibility(show_state_text)
        if status_links:
            self.apply_tile_status_binding(tile_id)
        target = self.binding_targets.get(tile_id)
        if target:
            binding_kind = "数据曲线" if target.get("binding_type") == "csv_curve" else "数据图像"
            target["title"] = f"{binding_kind}/{title_text}"

    def apply_all_inspection_tile_title_bindings(self):
        for tile_id in self.inspection_tiles:
            self.apply_inspection_tile_title_binding(tile_id)

    def configure_inspection_tile_title_binding(self, tile_id):
        tile = self.inspection_tiles.get(tile_id)
        if tile is None:
            return
        current_link = ""
        tile_links = self.binding_config.setdefault("tile_title_links", {})
        tile_custom_titles = self.binding_config.setdefault("tile_custom_titles", {})
        tile_status_links = self.binding_config.setdefault("tile_status_links", {})
        if isinstance(tile_links, dict):
            current_link = str(tile_links.get(tile_id, "") or "").strip()
        current_display_name = ""
        if isinstance(tile_custom_titles, dict):
            current_display_name = str(tile_custom_titles.get(tile_id, "") or "").strip()
        current_status_links = []
        if isinstance(tile_status_links, dict):
            raw_status_links = tile_status_links.get(tile_id, [])
            if isinstance(raw_status_links, str):
                current_status_links = [raw_status_links]
            elif isinstance(raw_status_links, list):
                current_status_links = raw_status_links
        dialog = TileTitleLinkDialog(
            tile.title,
            self.get_result_row_binding_options(),
            current_link,
            current_display_name,
            current_status_links,
            self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        result = dialog.get_result()
        linked_field_id = result.get("linked_field_id")
        custom_name = str(result.get("display_name", "") or "").strip() if result.get("display_name", "") is not None else None
        status_linked_field_ids = result.get("status_linked_field_ids", [])
        if linked_field_id is None or not str(linked_field_id).strip():
            tile_links.pop(tile_id, None)
        else:
            tile_links[tile_id] = str(linked_field_id).strip()
        if custom_name is None or not custom_name:
            tile_custom_titles.pop(tile_id, None)
        else:
            tile_custom_titles[tile_id] = custom_name
        if isinstance(status_linked_field_ids, list) and status_linked_field_ids:
            tile_status_links[tile_id] = [str(field_id).strip() for field_id in status_linked_field_ids if str(field_id).strip()]
        else:
            tile_status_links.pop(tile_id, None)
        self.apply_inspection_tile_title_binding(tile_id)
        self.save_binding_config()

    def register_binding_target(self, field_id, title, widgets, setter, binding_type="text"):
        if not isinstance(widgets, (list, tuple)):
            widgets = [widgets]
        self.binding_targets[field_id] = {
            "title": title,
            "widgets": widgets,
            "setter": setter,
            "binding_type": binding_type,
        }
        for widget in widgets:
            widget.setProperty("binding_target_id", field_id)
            widget.installEventFilter(self)
            self.bindable_widgets.append(widget)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            if self._cover_taskbar_mode or self.isFullScreen():
                self.exit_cover_taskbar_mode()
                return True
        if event.type() == QEvent.MouseButtonPress and self.settings_mode:
            if obj.property("result_items_header_action") and getattr(event, "button", lambda: None)() == Qt.LeftButton:
                self.configure_result_items_panel()
                return True
        if event.type() == QEvent.MouseButtonDblClick:
            if getattr(event, "button", lambda: None)() != Qt.LeftButton:
                return super().eventFilter(obj, event)
            if obj.property("main_title_action") and self.settings_mode:
                self.configure_main_title()
                return True
            tile_title_target_id = obj.property("tile_title_target_id")
            if tile_title_target_id and self.settings_mode:
                self.configure_inspection_tile_title_binding(tile_title_target_id)
                return True
            field_id = obj.property("binding_target_id")
            if field_id and self.settings_mode:
                self.configure_binding(field_id)
                return True
        return super().eventFilter(obj, event)

    def collect_ini_files(self):
        ini_dir = self.get_ini_dir()
        if not ini_dir or not ini_dir.exists():
            return []
        return sorted(str(path.relative_to(ini_dir)) for path in ini_dir.rglob("*.ini"))

    def configure_online_sn_binding(self):
        current = self.binding_config["fields"].get("online_sn") or {}
        dialog = OnlineSnBindingDialog("当前编号", self.get_ini_dir(), current, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        result = dialog.get_result()
        ini_dir_value = result.get("ini_dir", "")
        if ini_dir_value:
            self.binding_config["ini_dir"] = ini_dir_value

        binding = result.get("binding")
        if binding is None:
            if dialog._clear_requested:
                self.binding_config["fields"].pop("online_sn", None)
                self.save_binding_config()
                self.refresh_bound_values()
                return
            QMessageBox.warning(self, "配置不完整", "请先完成当前编号的绑定。")
            return

        self.binding_config["fields"]["online_sn"] = binding
        self.save_binding_config()
        self.refresh_bound_values()

    def configure_binding(self, field_id):
        if field_id == "online_sn":
            self.configure_online_sn_binding()
            return
        target = self.binding_targets[field_id]
        cache = {}
        current = self.binding_config["fields"].get(field_id)
        fixed_ini_path = None
        if self.use_sn_filename_target_file(field_id):
            current, _ = self.get_effective_binding(field_id, cache)
            fixed_ini_path = self.resolve_sn_target_ini_path(cache)
            if not fixed_ini_path or not Path(fixed_ini_path).exists():
                QMessageBox.warning(
                    self,
                    "目标配置未就绪",
                    "请先在“当前编号”设置里配置编号映射 INI，并保证当前编号能解析到有效的目标配置文件。",
                )
                return
        if target.get("binding_type") == "image":
            dialog = ImageBindingDialog(target["title"], self.get_ini_dir(), current, self, mode="image", fixed_ini_path=fixed_ini_path)
        elif target.get("binding_type") == "csv_curve":
            dialog = ImageBindingDialog(target["title"], self.get_ini_dir(), current, self, mode="csv_curve", fixed_ini_path=fixed_ini_path)
        elif field_id == "rabbit_count":
            dialog = RabbitCountBindingDialog(target["title"], self.get_ini_dir(), current, self)
        elif str(field_id).startswith("result_"):
            dialog = ResultItemBindingDialog(
                target["title"],
                self.get_ini_dir(),
                current,
                self.get_result_row_display_name(field_id, self.get_default_result_row_title(field_id)),
                self,
                fixed_ini_path=fixed_ini_path,
            )
        else:
            dialog = BindingDialog(target["title"], self.get_ini_dir(), current, self, fixed_ini_path=fixed_ini_path)
        if dialog.exec_() != QDialog.Accepted:
            return
        result = dialog.get_result()
        ini_dir_value = result.get("ini_dir", "")
        if ini_dir_value:
            self.binding_config["ini_dir"] = ini_dir_value
        csv_dir_value = result.get("csv_dir", "")
        if csv_dir_value:
            self.binding_config["csv_dir"] = csv_dir_value
        if str(field_id).startswith("result_"):
            self.set_result_row_custom_title(field_id, result.get("display_name", ""))
        binding = result.get("binding")
        if binding is None:
            if dialog._clear_requested:
                self.binding_config["fields"].pop(field_id, None)
                self.save_binding_config()
                self.refresh_bound_values()
                return
            warning_text = "请在绑定窗口中选择 INI 文件夹、INI 文件，并选择带 ### 标记的匹配项。"
            if target.get("binding_type") == "image":
                warning_text = "请在绑定窗口中选择 INI 文件夹、INI 文件，并指定图片路径键；如果图片路径和值分开存，再额外指定图片文件名键。"
            elif target.get("binding_type") == "csv_curve":
                warning_text = "请在绑定窗口中选择 INI 文件夹、INI 文件，并指定CSV路径键，再选择要绘制的曲线行。"
            elif field_id == "rabbit_count":
                warning_text = "请在绑定窗口中选择 INI 文件夹、INI 文件，并填写点检匹配文字和总数匹配文字。"
            QMessageBox.warning(self, "配置不完整", warning_text)
            return
        self.binding_config["fields"][field_id] = binding
        self.save_binding_config()
        self.refresh_bound_values()

    def resolve_sn_target_ini_path(self, cache):
        cache_key = "__sn_target_ini_path__"
        if cache_key in cache:
            return cache[cache_key]

        result = None
        online_binding = self.binding_config["fields"].get("online_sn") or {}
        if isinstance(online_binding, dict):
            lookup_file = online_binding.get("sn_lookup_file", "")
            if lookup_file:
                lookup_ini_dir = self.get_ini_dir()
                lookup_file_path = None
                if lookup_ini_dir:
                    lookup_file_path = lookup_ini_dir / lookup_file
                if lookup_file_path and lookup_file_path.exists():
                    lookup_key = online_binding.get("sn_lookup_key", "")
                    lookup_section = online_binding.get("sn_lookup_section")
                    target_name = None
                    if str(lookup_key or "").strip():
                        target_name = self.read_key_value(
                            lookup_file_path,
                            lookup_key,
                            lookup_section,
                            cache,
                        )
                    else:
                        source_file_path = self.resolve_binding_path(online_binding, None, cache)
                        if source_file_path and source_file_path.exists():
                            current_sn_value = self.read_key_value(
                                source_file_path,
                                online_binding.get("key", ""),
                                online_binding.get("section"),
                                cache,
                            )
                            current_sn_text = clean_path_text(current_sn_value)
                            if current_sn_text:
                                resolved = str(lookup_file_path)
                                if resolved not in cache:
                                    try:
                                        cache[resolved] = read_text_with_fallback(lookup_file_path).splitlines()
                                    except Exception:
                                        cache[resolved] = None
                                lookup_lines = cache.get(resolved)
                                if lookup_lines:
                                    target_name = extract_value_from_lines(lookup_lines, current_sn_text, None)
                    result = resolve_target_ini_path(target_name, lookup_file_path, lookup_ini_dir)

        if result is None:
            sn_file_binding = online_binding.get("sn_file_binding") if isinstance(online_binding, dict) else None
            if sn_file_binding:
                source_file_path = self.resolve_binding_path(sn_file_binding, None, cache)
                if source_file_path and source_file_path.exists():
                    target_name = self.read_key_value(
                        source_file_path,
                        sn_file_binding.get("key", ""),
                        sn_file_binding.get("section"),
                        cache,
                    )
                    result = resolve_target_ini_path(target_name, source_file_path, self.get_ini_dir())
        cache[cache_key] = result
        return result

    def resolve_binding_path(self, binding, field_id=None, cache=None):
        if cache is not None and field_id and self.use_sn_filename_target_file(field_id):
            target_file = self.resolve_sn_target_ini_path(cache)
            if target_file is not None:
                return target_file
        file_value = binding.get("file", "")
        if not file_value:
            return None
        candidate = Path(file_value)
        if candidate.is_absolute():
            return candidate
        ini_dir = self.get_ini_dir()
        if not ini_dir:
            return None
        return ini_dir / file_value

    def read_key_value(self, file_path, key_text, section_name, cache):
        resolved = str(file_path)
        if resolved not in cache:
            try:
                cache[resolved] = read_text_with_fallback(file_path).splitlines()
            except Exception:
                cache[resolved] = None
        lines = cache[resolved]
        if not lines:
            return None
        return extract_value_from_lines(lines, key_text, section_name)

    def resolve_image_binding_path(self, file_path, binding, cache):
        path_value = self.read_key_value(file_path, binding.get("path_key", ""), binding.get("path_section"), cache)
        if path_value is None:
            return None
        if binding.get("type") == "csv_curve":
            return compose_image_path("", path_value, file_path.parent)
        name_key = binding.get("name_key", "")
        if not str(name_key or "").strip():
            return compose_image_path("", path_value, file_path.parent)
        name_value = self.read_key_value(file_path, binding.get("name_key", ""), binding.get("name_section"), cache)
        if name_value is None:
            return None
        return compose_image_path(path_value, name_value, file_path.parent)

    def resolve_curve_limit_path(self, file_path, binding, cache):
        limit_key = str(binding.get("limit_path_key", "") or "").strip()
        if limit_key:
            limit_value = self.read_key_value(file_path, limit_key, binding.get("limit_path_section"), cache)
            if limit_value is None:
                return None
            return compose_image_path("", limit_value, file_path.parent)
        return clean_path_text(binding.get("limit_csv_path", ""))

    def resolve_curve_csv_direct_path(self, binding):
        csv_file = binding.get("csv_file", "")
        if not csv_file:
            return None

        path = Path(csv_file)
        if path.is_absolute():
            return path

        csv_dir = binding.get("csv_dir", "") or self.binding_config.get("csv_dir", "")
        if not csv_dir:
            return None
        return Path(csv_dir) / csv_file

    def binding_can_resolve(self, field_id, binding, cache):
        if not isinstance(binding, dict) or not binding:
            return False
        if binding.get("type") == "csv_curve_direct":
            if self.use_sn_filename_target_file(field_id):
                return False
            return self.resolve_curve_csv_direct_path(binding) is not None
        file_path = self.resolve_binding_path(binding, field_id, cache)
        if not file_path or not file_path.exists():
            return False
        if binding.get("type") == "image" or self.binding_targets.get(field_id, {}).get("binding_type") == "image":
            return self.resolve_image_binding_path(file_path, binding, cache) is not None
        if binding.get("type") == "csv_curve":
            return self.resolve_image_binding_path(file_path, binding, cache) is not None
        value = self.read_key_value(file_path, binding.get("key", ""), binding.get("section"), cache)
        return value is not None

    def get_effective_binding(self, field_id, cache):
        binding = self.binding_config["fields"].get(field_id)
        if not self.use_sn_filename_target_file(field_id):
            return binding, False

        if self.binding_can_resolve(field_id, binding, cache):
            return binding, False

        if isinstance(binding, dict) and binding:
            return binding, False

        default_binding = self.get_default_sn_target_binding(field_id)
        if self.binding_can_resolve(field_id, default_binding, cache):
            return default_binding, default_binding != binding

        return binding or default_binding, False

    def get_curve_value_segment(self, field_id):
        if field_id == "inspect_image_1":
            return "first_half"
        if field_id == "inspect_image_2":
            return "second_half"
        return None

    def reset_missing_display_values(self):
        if self.header is not None:
            self.header.set_online_sn(None)
            self.header.set_pending_sn(None)
            self.header.set_online_color(None)
            self.header.set_pending_color(None)
        for field_id in self.result_rows:
            self.apply_result_row_value(field_id, None)
        if self.total_result_widget is not None:
            self.total_result_widget.set_status_text("N/A")
        for cell in self.production_values.values():
            cell.setText("N/A")
        for field_id, cell in self.red_rabbit_values.items():
            cell.setText("N/A/N/A" if field_id == "rabbit_count" else "N/A")
        if self.rabbit_signal_widget is not None:
            self.rabbit_signal_widget.set_indicator_color("N/A")
        for tile in self.inspection_tiles.values():
            tile.clear_display()

    def refresh_bound_values(self):
        cache = {}
        changed = False
        curve_match_sn_text = ""
        self.reset_missing_display_values()
        for field_id, info in self.binding_targets.items():
            binding, migrated = self.get_effective_binding(field_id, cache)
            if migrated:
                self.binding_config["fields"][field_id] = dict(binding)
                changed = True
            if not binding:
                continue
            if binding.get("type") == "csv_curve_direct":
                curve_path = self.resolve_curve_csv_direct_path(binding)
                info["setter"](
                    str(curve_path) if curve_path else "",
                    binding.get("series_index", 0),
                    binding.get("y_axis_name"),
                    binding.get("limit_csv_path"),
                    binding.get("upper_limit_series_index"),
                    binding.get("lower_limit_series_index"),
                    binding.get("upper_limit_color"),
                    binding.get("lower_limit_color"),
                    binding.get("upper_limit_width"),
                    binding.get("lower_limit_width"),
                    binding.get("upper_limit_style"),
                    binding.get("lower_limit_style"),
                    curve_match_sn_text,
                    self.get_curve_value_segment(field_id),
                    binding.get("y_axis_min"),
                    binding.get("y_axis_max"),
                    binding.get("y_axis_tick_interval"),
                    binding.get("y_axis_font_size"),
                )
                continue
            file_path = self.resolve_binding_path(binding, field_id, cache)
            if not file_path or not file_path.exists():
                if field_id == "rabbit_count" and str(binding.get("total_key", "") or "").strip():
                    info["setter"]("N/A/N/A")
                continue
            if binding.get("type") == "image" or info.get("binding_type") == "image":
                info["setter"](self.resolve_image_binding_path(file_path, binding, cache))
                continue
            if binding.get("type") == "csv_curve":
                limit_path = self.resolve_curve_limit_path(file_path, binding, cache)
                info["setter"](
                    self.resolve_image_binding_path(file_path, binding, cache),
                    binding.get("series_index", 0),
                    binding.get("y_axis_name"),
                    limit_path,
                    binding.get("upper_limit_series_index"),
                    binding.get("lower_limit_series_index"),
                    binding.get("upper_limit_color"),
                    binding.get("lower_limit_color"),
                    binding.get("upper_limit_width"),
                    binding.get("lower_limit_width"),
                    binding.get("upper_limit_style"),
                    binding.get("lower_limit_style"),
                    curve_match_sn_text,
                    self.get_curve_value_segment(field_id),
                    binding.get("y_axis_min"),
                    binding.get("y_axis_max"),
                    binding.get("y_axis_tick_interval"),
                    binding.get("y_axis_font_size"),
                )
                continue
            if field_id == "rabbit_count" and str(binding.get("total_key", "") or "").strip():
                count_value = self.read_key_value(file_path, binding.get("key", ""), binding.get("section"), cache)
                total_value = self.read_key_value(file_path, binding.get("total_key", ""), binding.get("section"), cache)
                info["setter"](self.format_red_rabbit_count_value(count_value, total_value))
                continue
            value = self.read_key_value(file_path, binding.get("key", ""), binding.get("section"), cache)
            if is_missing_data_value(value):
                continue
            if field_id == "online_sn":
                curve_match_sn_text = str(value or "")
            info["setter"](value)
        if changed:
            self.save_binding_config()
        self.update_production_chart()

    def update_production_chart(self):
        if not self.production_chart:
            return
        good = self.production_values.get("production_good")
        bad = self.production_values.get("production_bad")
        if not good or not bad:
            return
        self.production_chart.set_values(good.text(), bad.text())

    def set_result_and_related_status(self, field_id, value):
        self.apply_result_row_value(field_id, value)

    def format_red_rabbit_count_value(self, count_value, total_value):
        count_text = "N/A" if is_missing_data_value(count_value) else str(count_value).strip()
        total_text = "N/A" if is_missing_data_value(total_value) else str(total_value).strip()
        return f"{count_text}/{total_text}"

    def build_total_result_panel(self):
        panel = PanelWidget("总结果")
        panel.setFixedHeight(102)
        panel.content_layout.setSpacing(0)
        self.total_result_widget = StatusBarWidget("OK", COLORS["green"])
        panel.content_layout.addWidget(self.total_result_widget, 1)
        self.register_binding_target(
            "total_result",
            "总结果",
            self.total_result_widget,
            self.total_result_widget.set_status_text,
        )
        return panel

    def build_item_results_panel(self):
        panel = PanelWidget("分项结果")
        panel.content_layout.setSpacing(1)
        self.item_results_panel = panel
        panel.header.setProperty("result_items_header_action", True)
        panel.header.installEventFilter(self)
        self.rebuild_item_result_rows()
        return panel

    def build_production_panel(self):
        panel = PanelWidget("当日生产统计")
        panel.setFixedHeight(176)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        panel.content_layout.addLayout(layout)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        headers = ["总数", "合格数", "不合格数", "通过率"]
        values = ["6", "2", "4", "33.33%"]
        field_ids = ["production_total", "production_good", "production_bad", "production_rate"]
        for col, label in enumerate(headers):
            grid.setColumnStretch(col, 1)
            grid.addWidget(MetricCell(label, large=True, wrap=False), 0, col)
        for col, (field_id, value) in enumerate(zip(field_ids, values)):
            cell = MetricCell(value, large=True, wrap=False)
            self.production_values[field_id] = cell
            grid.addWidget(cell, 1, col)
            self.register_binding_target(field_id, f"当日生产统计/{headers[col]}", cell, cell.setText)
        chart = PieChartWidget()
        self.production_chart = chart
        layout.addWidget(grid_host, 1)
        layout.addWidget(chart, 0)
        return panel

    def build_red_rabbit_panel(self):
        panel = PanelWidget("点检统计")
        panel.setFixedHeight(176)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        panel.content_layout.addLayout(layout)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        headers = ["状态", "是否完成", "点检数量", "到期时间"]
        values = ["禁用", "是", "0/7", "2026:12:28\n0:00:00"]
        field_ids = ["rabbit_status", "rabbit_done", "rabbit_count", "rabbit_due"]
        for col, label in enumerate(headers):
            grid.setColumnStretch(col, 1)
            grid.addWidget(MetricCell(label, large=True, wrap=False), 0, col)
        for col, (field_id, value) in enumerate(zip(field_ids, values)):
            cell = MetricCell(value, large=True, wrap=False)
            self.red_rabbit_values[field_id] = cell
            grid.addWidget(cell, 1, col)
            self.register_binding_target(field_id, f"点检统计/{headers[col]}", cell, cell.setText)
        self.rabbit_signal_widget = SignalStatusWidget()
        self.register_binding_target(
            "rabbit_signal_color",
            "状态指示/圆灯颜色",
            self.rabbit_signal_widget,
            self.rabbit_signal_widget.set_indicator_color,
        )
        layout.addWidget(grid_host, 11)
        layout.addWidget(self.rabbit_signal_widget, 3)
        return panel

    def build_inspection_panel(self):
        panel = PanelWidget("曲线及图像")
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)
        panel.content_layout.addLayout(grid)

        tiles = [
            ("1 指标 1 曲线", "", "ok", "curve", 0, 0, 1, 2),
            ("2 指标 2 曲线", "", "ok", "curve", 0, 2, 1, 2),
            ("3 示例图像 1", "OK", "ok", "split", 1, 0, 1, 1),
            ("4 示例图像 2", "OK", "ok", "lines", 1, 1, 1, 1),
            ("5 示例图像 3", "OK", "ok", "lens_left", 1, 2, 1, 1),
            ("6 示例图像 4", "OK", "ok", "lens_right", 1, 3, 1, 1),
            ("7 示例图像 5", "NG", "bad", "dark_line", 2, 0, 1, 1),
            ("示例图像 6", "", "ok", "arm_center", 2, 1, 1, 1),
            ("示例图像 7", "", "ok", "arm_left", 2, 2, 1, 1),
            ("示例图像 8", "", "ok", "arm_right", 2, 3, 1, 1),
        ]
        for index, (title, state, kind, canvas, row, col, row_span, col_span) in enumerate(tiles, start=1):
            tile = InspectionTile(title, state, kind, canvas)
            tile_id = f"inspect_image_{index}"
            self.inspection_tiles[tile_id] = tile
            grid.addWidget(tile, row, col, row_span, col_span)
            binding_type = "csv_curve" if canvas == "curve" else "image"
            setter = tile.set_curve_csv_path if canvas == "curve" else tile.set_image_path
            self.register_binding_target(
                tile_id,
                f"{'数据曲线' if canvas == 'curve' else '数据图像'}/{title}",
                [tile, tile.header_label, tile.canvas],
                setter,
                binding_type=binding_type,
            )
            tile.header_label.setProperty("tile_title_target_id", tile_id)
            tile.header_label.installEventFilter(self)
            if binding_type == "image":
                tile.canvas.set_image_transform_state(self.get_image_view_state(tile_id))
                tile.canvas.imageTransformChanged.connect(
                    lambda state, current_tile_id=tile_id: self.set_image_view_state(current_tile_id, state)
                )

        grid.setRowStretch(0, 3)
        grid.setRowStretch(1, 4)
        grid.setRowStretch(2, 4)
        for col in range(4):
            grid.setColumnStretch(col, 1)
        self.apply_all_inspection_tile_title_bindings()
        return panel


def export_preview(app, window, export_path):
    def grab():
        app.processEvents()
        window.grab().save(export_path)
        app.quit()

    window.show()
    QTimer.singleShot(180, grab)


def acquire_single_instance_lock(app):
    shared_memory = QSharedMemory(SINGLE_INSTANCE_KEY)
    if not shared_memory.create(1):
        QMessageBox.warning(None, "提示", "软件已在运行，请勿重复启动。")
        return False
    app._single_instance_memory = shared_memory
    return True


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setFont(make_font(11))
    if not acquire_single_instance_lock(app):
        return 0

    window = DashboardWindow()

    if "--export" in sys.argv:
        export_index = sys.argv.index("--export")
        export_path = sys.argv[export_index + 1] if export_index + 1 < len(sys.argv) else "preview.png"
        export_preview(app, window, export_path)
        return app.exec_()

    window.showMaximized()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
