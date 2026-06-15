# Setting up Playwright/Typescript example.

This example showcases how to use Playwright with Typescript for QA test automation.

# Installing requirements

**1. Install NodeJS**
    
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.5/install.sh | bash

    # in lieu of restarting the shell
    \. "$HOME/.nvm/nvm.sh"

    # Download and install Node.js:
    nvm install node

**2. Initialize Playwright***

    # Inside your project folder run:
    npm init playwright@latest

And follow instructions. Make sure you select Playwright as your base language, select "true" in Installing Playwright drivers

**3. Execute your test suite**

To begin with, you can test your installation by running:

    cd your_project folder
    npx playwright test

For this sample suite you can use the following commands:

    # Run all candymapper tests
    npx playwright test --project=CandyMapper

    # Run a specific test file
    npx playwright test CandyMapperAutomation.spec.ts --project=CandyMapper

    # Run with verbose output
    npx playwright test --project=CandyMapper --reporter=list

    # Run headed (see the browser)
    npx playwright test --project=CandyMapper --headed

    # Run a specific test by name
    npx playwright test --project=CandyMapper -g "should close popup"
