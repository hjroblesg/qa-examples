from selenium.webdriver.common.by import By
from .base_page import BasePage
from selenium.webdriver import ActionChains

class HerokuPage(BasePage):
    URL = "the-internet.herokuapp.com"
    SUCCESS_LOGIN_MSG = (
        By.XPATH,
        "//p[contains(text(), 'Congratulations! You must have the proper credentials.')]",
    )

    BASIC_AUTH_LINK = (
        By.XPATH,
        "//a[contains(text(), 'Basic Auth')]",
    )
    
    LOGIN_TXT_FIELD = (By.ID, "login")
    DOM_LOGIN_USR = (By.ID, "username")
    DOM_LOGIN_PASS = (By.ID, "password")
    LOGIN_BUTTON = (By.CSS_SELECTOR, "button[type='submit']")
    LOGIN_SUCCESS = (By.CSS_SELECTOR, "div.flash.success")
    LOGIN_ERROR = (By.CSS_SELECTOR, "div.flash.error")

    def navigate_heroku_site(self, site):
        self.base_page = f"https://{self.URL}/{site}"
        self.navigate_to(self.base_page)
    
    def navigate_login(self, user, password):
        self.base_page = f"{self.URL}/basic_auth"
        self.user = user
        self.password = password
        self.login_url = f"https://{self.user}:{self.password}@{self.base_page}"
        self.navigate_to(self.login_url)

    def navigate_login_site(self, user, password):
        login_user = self.wait_for_element(self.DOM_LOGIN_USR)
        login_password = self.wait_for_element(self.DOM_LOGIN_PASS)
        login_user.send_keys(user)
        login_password.send_keys(password)
        self.wait_for_element(self.LOGIN_BUTTON).click()
    
    def get_login_result(self, locator):
        result = self.wait_for_element(locator)
        return result

    def click_basicauth(self):
        self.click(self.BASIC_AUTH_LINK)
