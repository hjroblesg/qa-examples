from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys

class BasePage:
    def __init__(self, driver):
        self.driver = driver

    def navigate_to(self, url):
        self.driver.get(url)

    def wait_for_element(self, locator, timeout=5):
        return WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located(locator)
        )
    
    def wait_for_element_presence(self, locator, timeout=5):
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
    
    def wait_for_clickable_element(self, locator, timeout=10):
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable(locator)
        )
    
    def is_element_visible(self, locator):
        try:
            return self.driver.find_element(*locator).is_displayed()
        except (NoSuchElementException, StaleElementReferenceException):
            return False

    def reload_page(self):
        self.driver.refresh()

    def _safe_send_keys(self, locator, value, retries=3):
        for attempt in range(retries):
            try:
                print(f"Attempt {attempt + 1} - locator: {locator}")
                field = self.wait_for_clickable_element(locator, timeout=10)
                print(f"Field found, current value: '{field.get_attribute('value')}'")
                field.click()
                print("Clicked field")
                field.clear()
                print(f"After clear, value: '{field.get_attribute('value')}'")
                if field.get_attribute("value") != "":
                    field.send_keys(Keys.CONTROL + "a")
                    field.send_keys(Keys.DELETE)
                    print(f"After CTRL+A/DELETE, value: '{field.get_attribute('value')}'")
                field.send_keys(value)
                print(f"After send_keys, value: '{field.get_attribute('value')}'")
                return
            except StaleElementReferenceException:
                print(f"Stale element on attempt {attempt + 1}, retrying...")
                if attempt == retries - 1:
                    raise