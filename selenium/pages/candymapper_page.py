from selenium.webdriver.common.by import By
from .base_page import BasePage
from selenium.webdriver.common.action_chains import ActionChains
import time

class CandyMapperPage(BasePage):
    #POPUP_CHALLENGE = (By.CSS_SELECTOR, "#popup-widget5912-close-icon path") # for JS option
    POPUP_CHALLENGE = (By.ID, "popup-widget5912-close-icon")
    POPUP_CONTAINER = (By.ID, "popup-widget5912")
    CONTACT_FIRSTNAME = (By.CSS_SELECTOR, "input[id^='input'][data-aid='First Name']")
    CONTACT_LASTNAME = (By.CSS_SELECTOR, "input[id^='input'][data-aid='Last Name']")
    CONTACT_EMAIL = (By.CSS_SELECTOR, "input[id^='input'][data-aid='CONTACT_FORM_EMAIL']")
    CONTACT_PHONE = (By.CSS_SELECTOR, "input[id^='input'][data-aid^='By entering a Phone Number']")
    CONTACT_MSG = (By.CSS_SELECTOR, "textarea[placeholder='Message']")
    SUBMIT_BUTTON = (By.XPATH, "//button[@type='submit']")
    SUCCESS_MSG_LOCATOR = (By.XPATH, "//span[contains(text(),'Thank you for your inquiry! We will get back to yo')]")
    ERROR_MSG_LOCATOR = (By.XPATH, "//p[@role='alertdialog']")

    test_input = {"name": "Héctor", "last_name": "Robles",
                  "phone": "5532514459", "email": "hrobles@test.com",
                  "message": "Hello mate!"}

    def navigate_candymapper(self):
        self.navigate_to("https://candymapper.com/")
        return self

    def wait_for_popup(self):
        self.wait_for_element(self.POPUP_CONTAINER, timeout=10)
        element = self.wait_for_clickable_element(self.POPUP_CHALLENGE, timeout=10)
        return element
    
    def is_popup_visible(self):
        return self.is_element_visible(self.POPUP_CONTAINER)

    def close_popup(self):
        element = self.wait_for_popup()
        # Define action chains since popup button is not a button but an SVG element
        ActionChains(self.driver).move_to_element(element).click().perform()
        # JavaScript option:
        #self.driver.execute_script("arguments[0].dispatchEvent(new MouseEvent('click', {bubbles: true}))", element)
        return self

    def find_textbox(self, locator):
        return self.driver.find_element(*locator)
    
    def complete_field(self, text_field):
        if 'last_name' in text_field:
            locator = self.CONTACT_LASTNAME
            value = self.test_input['last_name']  
        elif 'name' in text_field:
            locator = self.CONTACT_FIRSTNAME
            value = self.test_input['name']          
        elif 'email' in text_field:
            locator = self.CONTACT_EMAIL
            value = self.test_input['email']
        elif 'phone' in text_field:
            locator = self.CONTACT_PHONE
            value = self.test_input['phone']            
        elif 'message' in text_field:
            locator = self.CONTACT_MSG
            value = self.test_input['message']
        else: 
            raise ValueError(f"Unknown field: {text_field}")
        
        self._safe_send_keys(locator, value) # Tricky problem here eith page re-rendering
        # The issue here must have been caused by a javascript listener managing state
        # a Wait is added in order to let the elemenDOM stabilize before reaching any elem/form in this case
        return self.wait_for_clickable_element(locator, timeout=10).get_attribute("value")
        #assert actual == value, f"Field '{text_field}' not filled correctly: expected '{value}', got '{actual}'"
        #return self        

    def get_field_value(self, locator):
        return self.wait_for_clickable_element(locator).get_attribute("value")

    def click_button(self):
        element = self.wait_for_clickable_element(self.SUBMIT_BUTTON, timeout=10)
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        self.driver.execute_script("document.querySelector('.grecaptcha-badge').style.display='none';")
        time.sleep(1)
        ActionChains(self.driver)\
            .move_to_element(element)\
            .pause(0.5)\
            .click()\
            .perform()
        return self.wait_for_element_presence(self.SUCCESS_MSG_LOCATOR, timeout=15)
    
    def find_mail_alert(self):
        return self.is_element_visible(self.ERROR_MSG_LOCATOR)