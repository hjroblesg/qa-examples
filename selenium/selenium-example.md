# Setting Pytest/Selenium example

This example showcases how to use Slenium with Pytest, as well as Allure for reports.

# Installing requirements

It is recommended to create a virtual environment first, here you may install all the requirements that will be needed to execute this sample.
    
**1. Create virtual env**
    
    python3 -m venv seleniumEnv
    # Activate environment
    source seleniumEnv/bin/activate
**2. Install deps:**
    
    pip install selenium pytest allure-pytest webdriver-manager

    or you may also run an install from requirements file as:
    pip install -r requirements.txt

    If you want to locally serve allure reports:
    npn install allure
    then run:
    allure serve results_folder

**3. Execute test suite.**

    # Run all candymapper tests
    pytest -v -s -m candymapper

    # Run a specific test
    pytest -v -s tests/test_candymapper.py::test_close_popup
    pytest -v -s tests/test_candymapper.py::test_fill_form

    # Run with allure report generation
    pytest -v -s -m candymapper --alluredir=allure-results
