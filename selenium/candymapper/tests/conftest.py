import pytest
import allure
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from pages.candymapper_page import CandyMapperPage
from allure_commons.types import AttachmentType


def pytest_addoption(parser):
    parser.addoption("--browser", action="store", default="chrome",
                     help="Type of supported Browser: chrome, firefox, edge, safari")
    parser.addoption("--headless", action="store_true", default=False)
    # parser.addoption("--base-url", action="store", default="http://localhost:3000")
    
@pytest.fixture(scope="function")
def browser(request):
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")    
    if request.config.getoption("--headless"):
        options.add_argument("--headless")    
    browser_type = request.config.getoption("--browser").lower()
    if browser_type == "chrome":
        driver = webdriver.Chrome(options)
    else:
        raise ValueError(f"Browser {browser_type} not supported")

    yield driver
    driver.quit()

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        driver = item.funcargs.get("browser")
        if driver:
            screenshot = driver.get_screenshot_as_png()
            allure.attach(
                screenshot,
                name="Screenshot on failure",
                attachment_type=AttachmentType.PNG
            )

@pytest.fixture
def candymapper_page(browser):
    return CandyMapperPage(browser)