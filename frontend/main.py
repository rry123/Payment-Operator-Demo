import sys
import requests
import reportlab
import pyqtgraph as pg
import openpyxl

from openpyxl import Workbook

from PyQt5.QtWidgets import QFileDialog
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QLabel, QLineEdit, QFormLayout, QHBoxLayout, QHeaderView, QHBoxLayout , QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from datetime import datetime


API_BASE = 'http://localhost:5000/api'

# --- Thread for login ---
class LoginThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, username, password):
        super().__init__()
        self.username = username
        self.password = password

    def run(self):
        try:
            r = requests.post(API_BASE + '/login', json={'username': self.username, 'password': self.password}, timeout=5)
            self.finished.emit(r.json())
        except Exception as e:
            self.error.emit(str(e))

# --- Login Dialog ---
class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Operator Login')
        self.setFixedSize(350, 200)   # Larger fixed size
        self.setStyleSheet("""
            QDialog {
                background-color: #f9f9f9;
            }
            QLabel {
                font-size: 14px;
            }
            QLineEdit {
                padding: 6px;
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #2c7be5;
                color: white;
                font-size: 14px;
                padding: 8px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1a5bb8;
            }
        """)

        # Title label
        title = QLabel("Operator Login")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")

        # Fields
        self.username = QLineEdit()
        self.username.setPlaceholderText("Enter username")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Enter password")
        self.password.setEchoMode(QLineEdit.Password)

        form = QFormLayout()
        form.addRow('Username:', self.username)
        form.addRow('Password:', self.password)

        # Login button
        btn = QPushButton('Login')
        btn.setDefault(True)  # pressing Enter triggers this
        btn.clicked.connect(self.do_login)

        # Main layout
        v = QVBoxLayout()
        v.addWidget(title)
        v.addLayout(form)
        v.addWidget(btn, alignment=Qt.AlignCenter)
        v.setContentsMargins(20, 20, 20, 20)  # padding inside dialog
        self.setLayout(v)

        self.result = None

        # Center the dialog on screen
        self.setGeometry(
            QApplication.desktop().screen().rect().center().x() - self.width() // 2,
            QApplication.desktop().screen().rect().center().y() - self.height() // 2,
            self.width(),
            self.height()
        )

    def do_login(self):
        u = self.username.text()
        p = self.password.text()
        self.thread = LoginThread(u, p)
        self.thread.finished.connect(self.on_login_result)
        self.thread.error.connect(lambda e: QMessageBox.critical(self, 'Error', e))
        self.thread.start()

    def on_login_result(self, data):
        if data.get('ok'):
            self.result = self.username.text()
            self.accept()
        else:
            QMessageBox.warning(self, 'Login failed', data.get('error', 'Unknown'))

# --- Editor Dialog ---
class EditorDialog(QDialog):
    def __init__(self, tx, operator):
        super().__init__()
        self.setWindowTitle('Edit Transaction')
        self.setFixedSize(400, 400)  # Bigger dialog
        self.tx = tx
        self.operator = operator
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f9f9f9;
            }
            QLabel {
                font-size: 14px;
            }
            QLineEdit {
                padding: 6px;
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QPushButton {
                font-size: 14px;
                padding: 8px 14px;
                border-radius: 6px;
            }
            QPushButton#submitBtn {
                background-color: #2c7be5;
                color: white;
                font-weight: bold;
            }
            QPushButton#submitBtn:hover {
                background-color: #1a5bb8;
            }
            QPushButton#cancelBtn {
                background-color: #e0e0e0;
                color: #333;
            }
            QPushButton#cancelBtn:hover {
                background-color: #c9c9c9;
            }
        """)

        # Title
        title = QLabel("Edit Transaction")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")

        # Form fields
        layout = QFormLayout()
        self.fn = QLineEdit(self.tx.get('message_type', ''))
        self.sender = QLineEdit(self.tx.get('sender', ''))
        self.receiver = QLineEdit(self.tx.get('receiver', ''))
        self.benef = QLineEdit(self.tx.get('beneficiary_name', ''))
        self.iban = QLineEdit(self.tx.get('iban', ''))
        self.amount = QLineEdit(str(self.tx.get('amount', '')))
        self.currency = QLineEdit(self.tx.get('currency', ''))

        layout.addRow('MT:', self.fn)
        layout.addRow('Sender:', self.sender)
        layout.addRow('Receiver:', self.receiver)
        layout.addRow('Beneficiary:', self.benef)
        layout.addRow('IBAN:', self.iban)
        layout.addRow('Amount:', self.amount)
        layout.addRow('Currency:', self.currency)

        # Buttons
        btn_h = QHBoxLayout()
        save_btn = QPushButton('Submit Fix')
        save_btn.setObjectName("submitBtn")
        save_btn.clicked.connect(self.submit_fix)

        cancel_btn = QPushButton('Cancel')
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)

        btn_h.addStretch()
        btn_h.addWidget(save_btn)
        btn_h.addWidget(cancel_btn)
        btn_h.addStretch()

        # Main layout
        v = QVBoxLayout()
        v.addWidget(title)
        v.addLayout(layout)
        v.addStretch()
        v.addLayout(btn_h)
        v.setContentsMargins(20, 20, 20, 20)
        self.setLayout(v)

    def submit_fix(self):
        new_tx = {
            'message_type': self.fn.text(),
            'sender': self.sender.text(),
            'receiver': self.receiver.text(),
            'beneficiary_name': self.benef.text(),
            'iban': self.iban.text(),
            'amount': self.amount.text(),
            'currency': self.currency.text()
        }
        try:
            r = requests.post(API_BASE + '/fix', json={'tx_id': self.tx.get('_id'), 'operator': self.operator, 'tx': new_tx}, timeout=5)
            data = r.json()
            if r.status_code == 200 and data.get('ok'):
                QMessageBox.information(self, 'Success', 'Transaction processed successfully')
                self.accept()
            else:
                errs = data.get('errors') or data.get('error') or 'Unknown error'
                QMessageBox.warning(self, 'Validation failed', str(errs))
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))

# --- Main Window ---
class MainWindow(QWidget):
    def __init__(self, operator):
        super().__init__()
        self.operator = operator
        self.setWindowTitle(f'Exception Queue - Operator: {operator}')
        self.resize(1000, 600)

        self.setup_ui()

    def setup_ui(self):
        # --- Table Setup ---
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ['ID', 'Sender', 'Receiver', 'Beneficiary', 'Amount', 'Error']
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # --- Buttons ---
        btn_reload = QPushButton('🔄 Load Exceptions')
        btn_reload.clicked.connect(self.load_exceptions)

        btn_edit = QPushButton('✏️ Edit Selected')
        btn_edit.clicked.connect(self.edit_selected)

        btn_processed = QPushButton('✅ Show Processed')
        btn_processed.clicked.connect(self.show_processed)

        btn_seed = QPushButton('🌱 Seed Sample Data')
        btn_seed.clicked.connect(self.seed_data)
        
        btn_dashboard = QPushButton('📊 Show Dashboard')
        btn_dashboard.clicked.connect(self.show_dashboard)
        
        
        btn_export_pdf = QPushButton('📝 Export to PDF')
        btn_export_pdf.clicked.connect(self.export_to_pdf)
        
        btn_export_excel = QPushButton('📊 Export to Excel')
        btn_export_excel.clicked.connect(self.export_to_excel)
        
        btn_operator_stats = QPushButton('📈 Operator Stats')
        btn_operator_stats.clicked.connect(self.show_operator_stats)

        # --- Layout for buttons ---
        btn_row1 = QHBoxLayout()
        btn_row1.addWidget(btn_reload)
        btn_row1.addWidget(btn_seed)
        btn_row1.addWidget(btn_operator_stats)
        btn_row1.addStretch(1)  # push right

        btn_row2 = QHBoxLayout()
        btn_row2.addWidget(btn_edit)
        btn_row2.addWidget(btn_processed)
        btn_row2.addWidget(btn_dashboard)
        btn_row2.addWidget(btn_export_pdf)
        btn_row2.addWidget(btn_export_excel)
        btn_row2.addStretch(1)

        btn_layout = QVBoxLayout()
        btn_layout.addLayout(btn_row1)
        btn_layout.addLayout(btn_row2)

        # --- Splitter (Resizable UI) ---
        splitter = QSplitter(Qt.Vertical)
        button_container = QWidget()
        button_container.setLayout(btn_layout)
        splitter.addWidget(button_container)
        splitter.addWidget(self.table)
        splitter.setSizes([100, 500])  # initial size ratio

        # --- Main Layout ---
        main_layout = QVBoxLayout()
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def seed_data(self):
        try:
            r = requests.post(API_BASE + '/seed', timeout=5)
            data = r.json()
            QMessageBox.information(self, 'Seed', f"Inserted: {data.get('inserted_count')}")
            self.load_exceptions()
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))

    def load_exceptions(self):
        try:
            r = requests.get(API_BASE + '/exceptions', timeout=5)
            data = r.json()
            arr = data.get('exceptions', [])
            self.table.setRowCount(0)
            for tx in arr:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(tx.get('_id')))
                self.table.setItem(row, 1, QTableWidgetItem(tx.get('sender', '')))
                self.table.setItem(row, 2, QTableWidgetItem(tx.get('receiver', '')))
                self.table.setItem(row, 3, QTableWidgetItem(tx.get('beneficiary_name', '')))
                self.table.setItem(row, 4, QTableWidgetItem(str(tx.get('amount', ''))))
                self.table.setItem(row, 5, QTableWidgetItem(tx.get('error', '')))
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))

    def edit_selected(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.warning(self, 'Select', 'Please select a transaction')
            return
        tx_id = self.table.item(r, 0).text()
        try:
            resp = requests.get(API_BASE + '/exceptions', timeout=5)
            data = resp.json()
            tx = next((x for x in data.get('exceptions', []) if x.get('_id') == tx_id), None)
            if not tx:
                QMessageBox.warning(self, 'Not found', 'Transaction not found')
                return
            dlg = EditorDialog(tx, self.operator)
            if dlg.exec_():
                self.load_exceptions()
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))

    def show_processed(self):
        try:
            r = requests.get(API_BASE + '/processed', timeout=5)
            data = r.json()
            arr = data.get('processed', [])
            if not arr:
                QMessageBox.information(self, 'Processed', 'No processed transactions')
                return

            # Create a dialog
            dlg = QDialog(self)
            dlg.setWindowTitle("Processed Transactions")
            dlg.resize(800, 400)
            layout = QVBoxLayout()
            dlg.setLayout(layout)

            # Table setup
            table = QTableWidget(len(arr), 5)
            table.setHorizontalHeaderLabels(['Processed By', 'Message Type', 'Beneficiary', 'Amount', 'Currency'])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

            # Populate table
            for row, a in enumerate(arr):
                table.setItem(row, 0, QTableWidgetItem(a.get('processed_by', '')))
                table.setItem(row, 1, QTableWidgetItem(a.get('message_type', '')))
                table.setItem(row, 2, QTableWidgetItem(a.get('beneficiary_name', '')))
                table.setItem(row, 3, QTableWidgetItem(str(a.get('amount', ''))))
                table.setItem(row, 4, QTableWidgetItem(a.get('currency', '')))

            layout.addWidget(table)

            # Close button
            btn_close = QPushButton("Close")
            btn_close.clicked.connect(dlg.close)
            layout.addWidget(btn_close)

            dlg.exec_()

        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))
            
    def show_operator_stats(self):
        try:
            url = f"{API_BASE}/operator_stats"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()

                if not data.get("ok") or "stats" not in data:
                    QMessageBox.warning(self, "No Data", "No stats available.")
                    return

                stats = data["stats"]

                # Create popup window
                stats_win = QWidget()
                stats_win.setWindowTitle("📈 Operator Stats")
                stats_win.resize(600, 400)

                # Table with 3 columns: Operator, Count, Avg Resolution (hours)
                table = QTableWidget(len(stats), 3)
                table.setHorizontalHeaderLabels(["Operator", "Processed Count", "Avg Resolution (hrs)"])
                table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

                for row, entry in enumerate(stats):
                    operator = entry.get("operator", "-")
                    count = entry.get("count", 0)
                    avg_res_seconds = entry.get("avg_resolution_seconds", 0)

                    # convert seconds → hours with 2 decimals
                    avg_res_hours = round(avg_res_seconds / 3600, 2)

                    table.setItem(row, 0, QTableWidgetItem(str(operator)))
                    table.setItem(row, 1, QTableWidgetItem(str(count)))
                    table.setItem(row, 2, QTableWidgetItem(f"{avg_res_hours} hrs"))

                layout = QVBoxLayout()
                layout.addWidget(table)
                stats_win.setLayout(layout)
                stats_win.show()

                # Keep reference so it doesn’t close immediately
                self.stats_window = stats_win

            else:
                QMessageBox.critical(self, "Error", f"Failed to fetch stats! ({response.status_code})")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load operator stats:\n{e}")

            
    def show_dashboard(self):
        dlg = DashboardDialog()
        dlg.exec_()  # This opens the dashboard as a modal dialog


            
    def export_to_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save to PDF", "", "PDF Files (*.pdf)")
        if not path:
            return

        c = canvas.Canvas(path, pagesize=letter)
        width, height = letter
        y = height - 40

        # Write headers
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        c.drawString(40, y, " | ".join(headers))
        y -= 20

        # Write table data
        for row in range(self.table.rowCount()):
            row_data = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                row_data.append(item.text() if item else "")
            c.drawString(40, y, " | ".join(row_data))
            y -= 20
            if y < 40:  # new page if space runs out
                c.showPage()
                y = height - 40

        c.save()
    
    def export_to_excel(self):
        # Open save file dialog
        path, _ = QFileDialog.getSaveFileName(self, "Save to Excel", "", "Excel Files (*.xlsx)")
        if not path:
            return

        wb = Workbook()
        ws = wb.active
        ws.title = "Exceptions"

        # Write headers
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        ws.append(headers)

        # Write table data
        for row in range(self.table.rowCount()):
            row_data = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                row_data.append(item.text() if item else "")
            ws.append(row_data)

        # Save workbook
        wb.save(path)
        print(f"✅ Data exported to {path}")



import pyqtgraph as pg
from PyQt5.QtWidgets import QVBoxLayout, QDialog, QLabel, QPushButton, QMessageBox
import requests
from reportlab.lib.utils import ImageReader
from pyqtgraph.exporters import ImageExporter
import tempfile


API_BASE = "http://localhost:5000/api"



class DashboardDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dashboard")
        self.resize(900, 700)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # --- Summary Labels ---
        self.total_exceptions_label = QLabel()
        self.total_processed_label = QLabel()
        self.processed_today_label = QLabel()
        self.processed_recent_label = QLabel()
        self.avg_resolution_label = QLabel()

        for lbl in [self.total_exceptions_label, self.total_processed_label,
                    self.processed_today_label, self.processed_recent_label,
                    self.avg_resolution_label]:
            lbl.setStyleSheet("font-size: 14px; font-weight: bold;")
            self.layout.addWidget(lbl)

        # --- Charts ---
        self.top_errors_plot = pg.PlotWidget(title="Top Errors")
        self.exceptions_by_type_plot = pg.PlotWidget(title="Exceptions by Message Type")
        self.exceptions_trend_plot = pg.PlotWidget(title="Exceptions Trend (Last 30 Days)")
        self.processed_by_operator_plot = pg.PlotWidget(title="Processed by Operator")

        for chart in [self.top_errors_plot, self.exceptions_by_type_plot,
                      self.exceptions_trend_plot, self.processed_by_operator_plot]:
            chart.setBackground('w')
            chart.showGrid(x=True, y=True)
            chart.getAxis('left').setStyle(tickFont=pg.QtGui.QFont("Arial", 10))
            chart.getAxis('bottom').setStyle(tickFont=pg.QtGui.QFont("Arial", 10))

        self.layout.addWidget(self.top_errors_plot)
        self.layout.addWidget(self.exceptions_by_type_plot)
        self.layout.addWidget(self.exceptions_trend_plot)
        self.layout.addWidget(self.processed_by_operator_plot)

        # --- Buttons ---
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)

        
        self.layout.addWidget(btn_close)

        self.load_data()

    def load_data(self):
        try:
            r = requests.get(f"{API_BASE}/dashboard", timeout=5)
            self.data = r.json()  # store data for report generation
            if not self.data.get("ok"):
                QMessageBox.warning(self, "Error", "Could not load dashboard")
                return

            # --- Summary Labels ---
            self.total_exceptions_label.setText(f"Total Exceptions: {self.data.get('total_exceptions', 0)}")
            self.total_processed_label.setText(f"Total Processed: {self.data.get('total_processed', 0)}")
            self.processed_today_label.setText(f"Processed Today: {self.data.get('processed_today', 0)}")
            self.processed_recent_label.setText(f"Processed Last 30 Days: {self.data.get('processed_recent_days', 0)}")
            avg_sec = int(self.data.get('avg_resolution_seconds', 0))
            self.avg_resolution_label.setText(f"Avg Resolution Time: {avg_sec} sec")

            # --- Top Errors Bar Chart ---
            self.top_errors_plot.clear()
            top_errors = self.data.get('top_errors', [])
            if top_errors:
                errors = [e['error'] for e in top_errors]
                counts = [e['count'] for e in top_errors]
                bar = pg.BarGraphItem(x=range(len(errors)), height=counts, width=0.6, brush='r')
                self.top_errors_plot.addItem(bar)
                self.top_errors_plot.getAxis('bottom').setTicks([list(enumerate(errors))])

            # --- Exceptions by Message Type ---
            self.exceptions_by_type_plot.clear()
            types = self.data.get('exceptions_by_message_type', [])
            if types:
                msg_types = [t['message_type'] for t in types]
                counts = [t['count'] for t in types]
                bar = pg.BarGraphItem(x=range(len(msg_types)), height=counts, width=0.6, brush='b')
                self.exceptions_by_type_plot.addItem(bar)
                self.exceptions_by_type_plot.getAxis('bottom').setTicks([list(enumerate(msg_types))])
                 # --- Processed by Operator ---
            self.processed_by_operator_plot.clear()
            processed = self.data.get('processed_by_operator', [])
            if processed:
                names = [p['operator'] for p in processed]
                counts = [p['count'] for p in processed]
                bar = pg.BarGraphItem(x=range(len(names)), height=counts, width=0.6, brush='m')
                self.processed_by_operator_plot.addItem(bar)
                self.processed_by_operator_plot.getAxis('bottom').setTicks([list(enumerate(names))])

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load dashboard: {e}")
            


    

    
            
# --- Main ---
def main():
    app = QApplication(sys.argv)
    login = LoginDialog()
    if login.exec_() != QDialog.Accepted:
        sys.exit(0)
    operator = login.result
    w = MainWindow(operator)
    w.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
