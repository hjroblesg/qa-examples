import { Page, Locator } from '@playwright/test';

export class BasePage {
    constructor(protected page: Page) {}

    async navigateTo(url: string): Promise<void> {
        await this.page.goto(url, { waitUntil: 'domcontentloaded' });
    }

    async waitForVisible(locator: Locator, timeout = 5000): Promise<Locator> {
        await locator.waitFor({ state: 'visible', timeout });
        return locator;
    }

    async safeType(locator: Locator, value: string, retries = 3): Promise<void> {
        for (let attempt = 1; attempt <= retries; attempt++) {
            try {
                await locator.waitFor({ state: 'visible', timeout: 10000 });
                await locator.click();
                await locator.fill('');
                await locator.fill(value);
                
                // Trigger input/change events so page JS registers the value
                await locator.dispatchEvent('input');
                await locator.dispatchEvent('change');
                
                const actual = await locator.inputValue();
                console.log(`Attempt ${attempt} - Expected: '${value}' | Got: '${actual}'`);
                if (actual === value) return;
    
                await locator.clear();
                await locator.pressSequentially(value, { delay: 50 });
                await locator.dispatchEvent('input');
                await locator.dispatchEvent('change');
                return;
            } catch (error) {
                console.log(`Attempt ${attempt} failed, retrying...`);
                if (attempt === retries) throw error;
            }
        }
    }
}