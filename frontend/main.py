import sys
import requests
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QLabel, QLineEdit, QFormLayout, QHBoxLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

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
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        form = QFormLayout()
        form.addRow('Username', self.username)
        form.addRow('Password', self.password)

        btn = QPushButton('Login')
        btn.clicked.connect(self.do_login)

        v = QVBoxLayout()
        v.addLayout(form)
        v.addWidget(btn)
        self.setLayout(v)

        self.result = None

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
        self.tx = tx
        self.operator = operator
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()
        self.fn = QLineEdit(self.tx.get('message_type', ''))
        self.sender = QLineEdit(self.tx.get('sender', ''))
        self.receiver = QLineEdit(self.tx.get('receiver', ''))
        self.benef = QLineEdit(self.tx.get('beneficiary_name', ''))
        self.iban = QLineEdit(self.tx.get('iban', ''))
        self.amount = QLineEdit(str(self.tx.get('amount', '')))
        self.currency = QLineEdit(self.tx.get('currency', ''))

        layout.addRow('MT', self.fn)
        layout.addRow('Sender', self.sender)
        layout.addRow('Receiver', self.receiver)
        layout.addRow('Beneficiary', self.benef)
        layout.addRow('IBAN', self.iban)
        layout.addRow('Amount', self.amount)
        layout.addRow('Currency', self.currency)

        btn_h = QHBoxLayout()
        save_btn = QPushButton('Submit Fix')
        save_btn.clicked.connect(self.submit_fix)
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        btn_h.addWidget(save_btn)
        btn_h.addWidget(cancel_btn)

        v = QVBoxLayout()
        v.addLayout(layout)
        v.addLayout(btn_h)
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
        self.resize(900, 500)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['ID', 'Sender', 'Receiver', 'Beneficiary', 'Amount', 'Error'])

        v = QVBoxLayout()
        btn_reload = QPushButton('Load Exceptions')
        btn_reload.clicked.connect(self.load_exceptions)
        btn_processed = QPushButton('Show Processed')
        btn_processed.clicked.connect(self.show_processed)
        btn_seed = QPushButton('Seed Sample Data')
        btn_seed.clicked.connect(self.seed_data)
        btn_edit = QPushButton('Edit Selected')
        btn_edit.clicked.connect(self.edit_selected)

        h = QHBoxLayout()
        h.addWidget(btn_reload)
        h.addWidget(btn_edit)
        h.addWidget(btn_processed)
        h.addWidget(btn_seed)
        v.addLayout(h)
        v.addWidget(self.table)
        self.setLayout(v)

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
            s = '\n'.join([f"{a.get('processed_by')} | {a.get('message_type')} | {a.get('beneficiary_name')} | {a.get('amount')} {a.get('currency')}" for a in arr])
            if not s:
                s = 'No processed transactions'
            QMessageBox.information(self, 'Processed', s)
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))

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
