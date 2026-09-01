APP_STYLE = """
QWidget {
    background: #11151b;
    color: #e8edf3;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QDialog, QWizard { background: #11151b; }
QFrame#card {
    background: #181e27;
    border: 1px solid #273141;
    border-radius: 12px;
}
QLabel#sectionTitle {
    color: #f8fafc;
    font-size: 12pt;
    font-weight: 600;
}
QLabel#muted { color: #96a2b2; }
QLabel#preview {
    background: #07090c;
    border: 1px solid #273141;
    border-radius: 12px;
    color: #768397;
}
QComboBox, QSpinBox, QDoubleSpinBox {
    background: #202936;
    border: 1px solid #344155;
    border-radius: 7px;
    min-height: 30px;
    padding: 2px 9px;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #3dd6d0; }
QComboBox QAbstractItemView {
    background: #202936;
    selection-background-color: #176b70;
    border: 1px solid #344155;
}
QPushButton {
    background: #263140;
    border: 1px solid #3a485d;
    border-radius: 8px;
    min-height: 32px;
    padding: 2px 13px;
}
QPushButton:hover { background: #303d4e; border-color: #4fd1cc; }
QPushButton:pressed { background: #1f2935; }
QPushButton:disabled { color: #697586; background: #1b222c; border-color: #293240; }
QPushButton#primary {
    background: #13a7a2;
    color: #071212;
    border-color: #35d8d1;
    font-weight: 600;
}
QPushButton#primary:hover { background: #31c3bd; }
QPushButton#danger { color: #ffb4b4; border-color: #6f3f47; }
QSlider::groove:horizontal { height: 5px; background: #303b4b; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #25bcb6; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #e8fffe; border: 2px solid #25bcb6; width: 15px; margin: -6px 0; border-radius: 8px;
}
QCheckBox::indicator { width: 18px; height: 18px; }
QProgressBar { border: 1px solid #344155; border-radius: 6px; text-align: center; }
QProgressBar::chunk { background: #25bcb6; border-radius: 5px; }
QMenuBar, QMenu { background: #181e27; }
QMenu::item:selected { background: #24545a; }
"""
