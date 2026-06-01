import pytest
import allure
from selenium.common.exceptions import TimeoutException

@allure.title("Challenge test - Is Pop-Up Closed??")
@allure.feature("CandyMapper Pop-up SVG element challenge")
@pytest.mark.skip(reason="Not required right now")
def test_close_popup(candymapper_page):
    with allure.step("Given I navigate at candymapper home page and close the popup"):
        candymapper_page.navigate_candymapper().close_popup()
    with allure.step("Then, popup is not visible after clicking on the x button"):
        assert not candymapper_page.is_popup_visible(), "Popup should be hidden after clicking close"

@allure.title("Challenge test - Complete Form after pop-up closes.")
@allure.feature("CandyMapper Fill Contact Us Form")
@pytest.mark.candymapper
def test_fill_form(candymapper_page):
    with allure.step("Given I navigate at candymapper home page and close the popup"):
        candymapper_page.navigate_candymapper().close_popup()
    with allure.step("When I complete the form"):
        candymapper_page.complete_field('name')
        assert candymapper_page.get_field_value(candymapper_page.CONTACT_FIRSTNAME) == "Héctor"
        candymapper_page.complete_field('last_name')
        candymapper_page.complete_field('email')
        assert not candymapper_page.find_mail_alert()
        candymapper_page.complete_field('phone')
        candymapper_page.complete_field('message')
        # assert result.get_attribute("value") == "Robles"
        # error = candymapper_page.wait_for_element(self.ERROR_MSG_LOCATOR)
        # assert error.is_displayed()
        # candymapper_page.click_button()
    with allure.step("Then I click on the submit button and confirm form is submitted"):
        success = candymapper_page.click_button()
        assert success.is_displayed()
        assert "thank you" in success.text.lower()