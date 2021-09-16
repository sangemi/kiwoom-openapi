import sys
import time
import sqlite3
from datetime import datetime

from PyQt5.QtWidgets import *
from PyQt5.QAxContainer import *
from PyQt5.QtGui import *
from PyQt5.QtCore import pyqtSignal, QObject

# DEBUG:0 (disabled) or DEBUG:1 (enabled)
DEBUG = 1
def debug_print(x):
	if DEBUG == 0:
		return
	print(x)

codeDataName = ["종목코드", "종목명", "결산월", "액면가", "자본금",
				"상장주식", "신용비율", "연중최고", "연중최저", "시가총액",
				"시가총액비중", "외인소진률", "대용가", "PER", "EPS",
				"ROE", "PBR", "EV", "BPS", "매출액",
				"영업이익", "당기순이익", "D250최고", "D250최저", "시가",
				"고가", "저가", "상한가", "하한가", "기준가",
				"예상체결가", "예상체결수량", "D250최고가일", "D250최고가대비율", "D250최저가일",
				"D250최저가대비율", "현재가", "대비기호", "전일대비", "등락율",
				"거래량", "거래대비", "액면가단위", "유통주식", "유통비율", "입력일"]
codeDataType = ["text", "text", "text", "int", "int",
				"int", "real", "int", "int", "int",
				"real", "real", "int", "real", "real",
				"real", "real", "real", "real", "int",
				"int", "int", "int", "int", "int",
				"int", "int", "int", "int", "int",
				"int", "int", "text", "real", "text",
				"real", "int", "int", "int", "real",
				"int", "real", "text", "int", "real", "text"]

dbPath = "C:/Dev/Server/Git-Lawfirmy/kiwoom-openapi/" # "c:/StockDB/"

stockDb = "myStock.db"
kospiTable = "kospi"
kosdaqTable = "kosdaq"

class Communicate(QObject):
	codelist_work = pyqtSignal()

class Kiwoom(QMainWindow):
	def __init__(self):
		super().__init__()
		self.getToday()
		self.initUI()
		self.initSignal()
		self.initDB()
		self.login()
		self.sMarket = "0" # default: kospi
		self.curMarketTable = kospiTable
		self.code_list = []
		self.code_data = {} # dictionary ex) code_data['005930']
		self.transaction = 0

	def initUI(self):
		self.setWindowTitle("종목DB구축")
		self.setGeometry(300, 300, 2000, 800)

		self.statusBar().showMessage("Not Connected")

		self.Market_combo = QComboBox(self)
		self.Market_combo.addItem('코스피')
		self.Market_combo.addItem('코스닥')
		self.Market_combo.setGeometry(20, 20, 130, 30)
		self.Market_combo.activated[str].connect(self.market_combo_activated)

		# 가져오기 버튼: DB를 검색해서 코드가 존재하면 스킵, 존재하지 않으면 정보를 테이블에 입력한다.
		self.JongMok_button = QPushButton('가져오기', self)
		self.JongMok_button.move(160, 20)
		self.JongMok_button.clicked.connect(self.jongmok_button_clicked)
		self.JongMok_button.setFocus()
		self.JongMok_button.setEnabled(False)

		# 업데이트 버튼: 오늘 날짜가 아닌 레코드를 모두 찾아 업데이트 한다.
		self.Update_button = QPushButton('업데이트', self)
		self.Update_button.move(280, 20)
		self.Update_button.clicked.connect(self.update_button_clicked)
		self.Update_button.setEnabled(False)

		self.JongMok_result = QTextEdit(self)
		self.JongMok_result.setGeometry(10, 60, 1980, 700)
		self.JongMok_result.setEnabled(True)

	def initSignal(self):
		self.c = Communicate()
		self.c.codelist_work.connect(self.get_codelist)

	def getToday(self):
		self.today = datetime.today().strftime("%Y-%m-%d")
		debug_print(self.today)

	def createMarketField(self):
		field = "("
		for i in range(len(codeDataName)):
			field = field + codeDataName[i] + " " + codeDataType[i]
			if i == 0:
				field = field + " NOT NULL PRIMARY KEY, "
			elif i == len(codeDataName) - 1:
				field = field + ");"
			else:
				field = field + ", "
		return field

	def createMarketTable(self, market):
		self.stock_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='" + market + "'")
		exist = self.stock_cur.fetchall()
		if len(exist) == 0:
			# create tables
			field = self.createMarketField()
			create_market_tbl_sql = "CREATE TABLE " + market + field
			self.stock_cur.execute(create_market_tbl_sql)
			self.stock_con.commit()
			print("마켓 테이블 생성: " + market)
		else:
			print("마켓 테이블 존재: " + market)

	def initDB(self):
		self.stock_con = sqlite3.connect(dbPath + stockDb)
		self.stock_cur = self.stock_con.cursor()

		# check & create kospi table
		self.createMarketTable(kospiTable)
		# check & create kosdaq table
		self.createMarketTable(kosdaqTable)

	def login(self):
		# Connect
		self.kiwoom = QAxWidget()
		self.kiwoom.setControl("KHOPENAPI.KHOpenAPICtrl.1")
		self.kiwoom.dynamicCall("CommConnect()")

		# OpenAPI+ Event
		self.kiwoom.OnEventConnect.connect(self.event_connect)
		self.kiwoom.OnReceiveTrData.connect(self.receive_tr_data)

	def market_combo_activated(self, text):
		if text == "코스피":
			self.sMarket = "0"		# kospi
			self.curMarketTable = kospiTable
		else:
			self.sMarket = "10"		# kosdaq
			self.curMarketTable = kosdaqTable

	def event_connect(self, err_code):
		if err_code == 0:
			self.statusBar().showMessage("Connected")
			self.JongMok_button.setEnabled(True)
			self.Update_button.setEnabled(True)
		else:
			self.statusBar().showMessage("Connection Failed (err:%d)" % err_code)

	def jongmok_button_clicked(self):
		self.data_mode = "insert"
		self.transaction = 0
		self.JongMok_button.setDisabled(True)
		self.JongMok_result.clear()
		self.print_header_line()

		ret = self.kiwoom.dynamicCall("GetCodeListByMarket(QString)", [self.sMarket])
		self.code_list = ret.split(';')
		if len(self.code_list) > 1:
			self.code_list = self.code_list[:-1] # remove last null item due to split(';')

		# emit signal to start insert
		self.c.codelist_work.emit()

	def update_button_clicked(self):
		self.data_mode = "update"
		self.transaction = 0
		self.Update_button.setDisabled(True)
		self.JongMok_result.clear()
		self.print_header_line()

		self.code_list = self.get_old_jongmok_in_db()
		if len(self.code_list) == 0:
			# Do nothing when all records are updated
			self.Update_button.setDisabled(False)
			return

		# emit signal to start update
		self.c.codelist_work.emit()

	def receive_tr_data(self, screen_no, rqname, trcode, recordname, prev_next, data_len, err_code, msg1, msg2):
		print("리시브로 들어옴 rqname:%s,err_code:%s, msg1=%s, msg2=%s"%(rqname, err_code, msg1, msg2))
		self.transaction = self.transaction - 1
		if err_code != "":
			# It seems we cannot avoid error 209 (too many transaction request error)
			print("ERROR: quit program")
			self.stock_con.close()
			self.close()

		rqstr = rqname.split('_')
		rqstr2 = rqstr[0].split('-')
		if rqstr2[0] == "opt10001req":
			code = rqstr[1]
			self.code_data[code] = ()
			for i in range(len(codeDataName)-1): # exclude 입력일
				data = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString",
										   trcode, recordname, 0, codeDataName[i])
				self.code_data[code] = self.code_data[code] + (data.strip(),)
			if self.code_data[code][0] == '':
				# exception: sometimes '' data is coming.
				return
			debug_print(self.code_data[code])
			self.print_data_line(self.code_data[code])
			if self.data_mode == "insert":
				self.insert_data_db(self.code_data[code])
			else:
				self.update_data_db(self.code_data[code])

	def print_header_line(self):
		header = ""
		for n in codeDataName:
			header = header + n + ":"
		header = header[:-1] # remove last ":"
		self.JongMok_result.append(header)

	def print_data_line(self, dtuple):
		data = ""
		for n in dtuple:
			data = data + n + ":"
		data = data[:-1] # remove last ":"
		self.JongMok_result.append(data)

	def insert_data_db(self, dtuple):
		values = "VALUES ("
		for i in range(len(dtuple)):
			values = values + "'" + dtuple[i] + "'"
			if i == len(dtuple) - 1:
				values = values + ", '" + self.today + "');"
			else:
				values = values + ", "

		insert_sql = "INSERT INTO " + self.curMarketTable + " " + values
		debug_print(insert_sql)
		self.stock_cur.execute(insert_sql)
		self.stock_con.commit()

	def update_data_db(self, dtuple):
		if len(dtuple) + 1 != len(codeDataName):
			print("ERROR: record field length is different: " + str(len(dtuple)))
			return
		set_str = "SET "
		for i in range(len(codeDataName)):
			if i == 0 or i == 1:
				# skip 종목코드 종목명
				continue
			set_str = set_str + codeDataName[i] + " = '" + dtuple[i] + "', "
			if i == len(dtuple) - 1:
				set_str = set_str + codeDataName[i+1] + " = '" + self.today + "'"
				break
		where = "WHERE 종목코드='" + dtuple[0] + "';"

		update_sql = "UPDATE " + self.curMarketTable + " " + set_str + " " + where
		debug_print(update_sql)
		self.stock_cur.execute(update_sql)
		self.stock_con.commit()

	def is_jongmok_in_db(self, code):
		search_sql = "SELECT * FROM " + self.curMarketTable + " WHERE 종목코드='" + code + "';"
		debug_print(search_sql)
		self.stock_cur.execute(search_sql)
		exist = self.stock_cur.fetchall()
		if len(exist) == 1:
			debug_print("DB 종목코드(" + code + "): 존재")
			return 1
		elif len(exist) == 0:
			return 0
		else:
			print("ERROR: multiple records for " + code + " count=" + str(len(exist)))
			return 1

	def get_old_jongmok_in_db(self):
		search_sql = "SELECT 종목코드 FROM " + self.curMarketTable + " WHERE 입력일!='" + self.today + "';"
		debug_print(search_sql)
		self.stock_cur.execute(search_sql)
		arr_tuple = self.stock_cur.fetchall()
		#debug_print(arr_tuple)
		old_list = []
		for i in range(len(arr_tuple)):
			if arr_tuple[i][0] != '':
				old_list.append(arr_tuple[i][0])
		debug_print("오래된 레코드: " + str(len(old_list)) + "건 존재")
		debug_print(old_list)
		return old_list

	def get_codelist(self):
		count = 0
		for x in self.code_list:
			if self.data_mode == "insert":
				# check 종목코드 exist in DB
				if self.is_jongmok_in_db(x) == 1:
					count = count + 1
					continue

			# SetInputValue
			self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "종목코드",  x)
			# CommRqData
			self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)",
									"opt10001req-"+ str(count) + "_" + x, "opt10001", 0, "0101")

			# this is to avoid error 200
			count = count + 1
			self.transaction = self.transaction + 1
			if self.transaction > 10:
				time.sleep(10)
			else:
				time.sleep(1)

		# enable JongMok & Update button
		self.JongMok_button.setDisabled(False)
		self.Update_button.setDisabled(False)

if __name__ == "__main__":
	app = QApplication(sys.argv)
	myWindow = Kiwoom()
	myWindow.show()
	app.exec_()
