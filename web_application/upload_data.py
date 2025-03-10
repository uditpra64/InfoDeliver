import os
import time
import re
from datetime import datetime, date
from tkinter import messagebox
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from common.jobcan import JobcanAutomation
from attendance import const


class AttendanceAutomation(JobcanAutomation):
    def __init__(self, app, upload_attendance_path):
        super().__init__()
        self.app = app
        self.upload_attendance_path = upload_attendance_path

    def convert_date_to_japanese_format(self, date_input):
        try:
            if isinstance(date_input, str):
                date_object = datetime.strptime(date_input, "%Y-%m-%d").date()
            elif isinstance(date_input, date):
                date_object = date_input
            else:
                raise ValueError("入力は文字列またはdatetime.dateオブジェクトである必要があります。")
            return date_object.strftime("%Y年%m月%d日")
        except ValueError as e:
            return f"エラー: {str(e)}。YYYY-MM-DD形式の文字列またはdatetime.dateオブジェクトを入力してください。"

    def select_payment_date(self, payment_date):
        try:
            self._click_element("//div[contains(@class, 'Select-control')]")
            self._click_element(f"//div[contains(@class, 'Select-option') and contains(., '{payment_date}')]")
        except (TimeoutException, NoSuchElementException) as e:
            self._handle_error("支給日の選択に失敗しました。\n 選択した支給日を確認してください。")

    def navigate_to_attendance_page(self):
        try:
            self.login()
            self._wait_for_page_load()
            self.driver.get("https://payroll.jobcan.jp/employees/attendances")
            self._wait_for_page_load()
        except TimeoutException:
            self._handle_error("ページの読み込みがタイムアウトしました。")
        except Exception as e:
            self._handle_error("エラーが発生しました。", e)

    def click_csv_upload_button(self):
        try:
            self._click_element(
                "//div[contains(@class, 'Button__small') and contains(@class, 'Button__blue') and contains(text(), '勤怠項目CSVアップロード')]"
            )
        except TimeoutException:
            self._handle_error("'勤怠項目CSVアップロード'ボタンが見つかりませんでした。")
        except Exception as e:
            self._handle_error("ボタンのクリック中にエラーが発生しました。", e)

    def upload_csv(self):
        try:
            file_input = self._wait_for_element((By.CSS_SELECTOR, 'input[type="file"]'))
            file_input.send_keys(os.path.abspath(self.upload_attendance_path))

            initial_success_content = self._get_element_text(
                "div.ImportAttendanceCsvJobStatus__tasksSuccess--1RDlJ.ImportAttendanceCsvJobStatus__wrap--2YOof"
            )
            initial_error_content = self._get_element_text(
                "div.ImportAttendanceCsvJobStatus__tasksFailed--1KmGL.ImportAttendanceCsvJobStatus__wrap--2YOof"
            )

            self._click_element(
                "//div[contains(@class, 'Button__small') and contains(@class, 'Button__blue') and contains(@class, 'Button__widthWide') and contains(text(), 'アップロード')]"
            )

            result = self._wait_for_upload_completion(initial_success_content, initial_error_content)
            self.app.log_message(const.UPLOAD_ATTENDANCE_DATA_PROCESS, result)

            self._show_result_message(result)

        except TimeoutException:
            self._handle_error("ファイルアップロード要素が見つかりませんでした。")
        except Exception as e:
            self._handle_error("CSVアップロード中にエラーが発生しました。", e)

    def _wait_for_upload_completion(self, initial_success_content, initial_error_content, timeout=300):
        start_time = time.time()
        while True:
            current_success_content = self._get_element_text(
                "div.ImportAttendanceCsvJobStatus__tasksSuccess--1RDlJ.ImportAttendanceCsvJobStatus__wrap--2YOof"
            )
            current_error_content = self._get_element_text(
                "div.ImportAttendanceCsvJobStatus__tasksFailed--1KmGL.ImportAttendanceCsvJobStatus__wrap--2YOof"
            )

            if current_success_content != initial_success_content:
                return self._check_success_message(current_success_content)

            if current_error_content != initial_error_content:
                return self._check_error_message(current_error_content)

            if time.time() - start_time > timeout:
                return f"{timeout}秒経過しても、アップロード完了または失敗のメッセージが表示されませんでした。"

            time.sleep(0.1)

    def _check_success_message(self, content):
        if "勤怠CSVアップロードが完了しました" in content:
            return self._extract_latest_result(content)
        return None

    def _check_error_message(self, content):
        if "勤怠CSVアップロードが失敗しました" in content:
            return self._extract_latest_result(content)
        return None

    def _extract_latest_result(self, content):
        pattern = r"対象期間：.*?完了日時：\n\d{4}/\d{2}/\d{2} \d{2}:\d{2}(?:\n.*?(?=対象期間：|\Z))?"
        results = re.findall(pattern, content, re.DOTALL)
        if results:
            # 実行日時でソート
            results.sort(
                key=lambda x: re.search(r"実行日時：\n(\d{4}/\d{2}/\d{2} \d{2}:\d{2})", x).group(1), reverse=True
            )
            # 最新の結果を返す
            return results[0].strip()
        return content

    def run_automation(self):
        try:
            self.navigate_to_attendance_page()
            payment_date = self.convert_date_to_japanese_format(self.app.payment_date._date)
            self.select_payment_date(payment_date)
            self.click_csv_upload_button()
            self.upload_csv()
        finally:
            self.close()

    def _wait_for_element(self, locator, timeout=10):
        return WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located(locator))

    def _click_element(self, xpath, timeout=10):
        element = WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        element.click()

    def _wait_for_page_load(self, timeout=10):
        WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    def _get_element_text(self, css_selector):
        try:
            return self.driver.find_element(By.CSS_SELECTOR, css_selector).text
        except NoSuchElementException:
            return ""

    def _handle_error(self, message, exception=None):
        full_message = f"{message}: {exception}" if exception else message
        self.app.log_message(const.UPLOAD_ATTENDANCE_DATA_PROCESS, full_message)
        messagebox.showerror(const.MESSAGEBOX_ERROR_TITLE, full_message)
        self.close()

    def _show_result_message(self, result):
        if result is None:
            self.app.log_message(const.UPLOAD_ATTENDANCE_DATA_PROCESS, "アップロード結果を取得できませんでした。")
            messagebox.showerror(const.MESSAGEBOX_ERROR_TITLE, "アップロード結果を取得できませんでした。")
        elif "完了しました" in result:
            self.app.log_message(const.UPLOAD_ATTENDANCE_DATA_PROCESS, const.ATTENDANCE_UPLOAD_DONE_MESSAGE)
            messagebox.showinfo(const.MESSAGEBOX_COMPLETE_TITLE, const.ATTENDANCE_UPLOAD_DONE_MESSAGE)
        else:
            self.app.log_message(const.UPLOAD_ATTENDANCE_DATA_PROCESS, const.ATTENDANCE_UPLOAD_ERROR_MESSAGE)
            messagebox.showerror(const.MESSAGEBOX_ERROR_TITLE, const.ATTENDANCE_UPLOAD_ERROR_MESSAGE)
