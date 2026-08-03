import pytest
import allure
from selenium.common.exceptions import TimeoutException
#from selenium.webdriver.support.ui import WebDriverWait
#from selenium.webdriver.support import expected_conditions as EC

@allure.title("I can make login at heroku page basic auth link.")
@pytest.mark.herokuapp
def test_html_modal_login(heroku_page):
    with allure.step("Given I provide login credentials"):
        heroku_page.navigate_login("admin", "admin")
    with allure.step("I get a succesful login welcome message"):
        text_element = heroku_page.get_login_result(heroku_page.SUCCESS_LOGIN_MSG).text
        expected_text = "Congratulations! You must have the proper credentials."
        assert (text_element in expected_text), "No proper login credentials provided"

@allure.title("I can login using authentication form from heroku site.")
@pytest.mark.herokuapp
def test_form_login(heroku_page):
    user = "tomsmith"
    password = "SuperSecretPassword!"    
    with allure.step("Given I navigate to authentication form page"):
        heroku_page.navigate_heroku_site("login")
    with allure.step("When I access login text fields and click on login button"):
        heroku_page.navigate_login_site(user, password)
    with allure.step("Then I can see secured area message or invalid user message if incorrect creds are provided."):
        try:
            success = heroku_page.get_login_result(heroku_page.LOGIN_SUCCESS)
            assert "You logged into a secure area!" in success.text, "Incorrect credentials provided"
        except TimeoutException:
            error = heroku_page.get_login_result(heroku_page.LOGIN_ERROR)
            assert "Your username is invalid!" in error.text, "Please provide valid credentials"



