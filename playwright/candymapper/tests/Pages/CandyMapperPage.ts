import { expect, type Locator, type Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class CandyMapperPage extends BasePage {
    // Add locators ghere
    private readonly PopupCloseIcon: Locator;
    private readonly PopupContainer: Locator;
    private readonly contactFirstName: Locator;
    private readonly contactLastName: Locator;
    private readonly contactEmail: Locator;
    private readonly contactPhone: Locator;
    private readonly contactMsg: Locator;
    private readonly submitButton: Locator;
    private readonly successMsg: Locator;
    private readonly errorMsg: Locator;
 
    constructor(page: Page) {
        super(page);
        this.PopupCloseIcon = page.locator('#popup-widget5912-close-icon');
        this.PopupContainer = page.locator('#popup-widget5912');
        this.contactFirstName = page.locator("input[id^='input'][data-aid='First Name']");
        this.contactLastName  = page.locator("input[id^='input'][data-aid='Last Name']");
        this.contactEmail     = page.locator("input[id^='input'][data-aid='CONTACT_FORM_EMAIL']");
        this.contactPhone     = page.locator("input[id^='input'][data-aid^='By entering a Phone Number']");
        this.contactMsg       = page.locator("textarea[placeholder='Message']");
        this.submitButton     = page.locator("button[type='submit']");
        this.successMsg       = page.locator("text=Thank you for your inquiry");
        this.errorMsg         = page.locator("text=Something went wrong");
    }
    
    async navigateCandyMapper(): Promise<this> {
        await this.navigateTo('https://candymapper.com/');
        return this;
    }

    async closePopup(): Promise<this> {
        await this.PopupContainer.waitFor({ state: 'visible', timeout: 15000 });
        await this.PopupCloseIcon.scrollIntoViewIfNeeded();
        await this.PopupCloseIcon.dispatchEvent('click');
        await this.PopupContainer.waitFor({ state: 'hidden', timeout: 10000 });
        return this;
    }

    async isPopupVisible(): Promise<boolean> {
        return this.PopupContainer.isVisible();
    }

    async completeField(field: 'last_name' | 'name' | 'email' | 'phone' | 'message'): Promise<this> {
    const fieldMap: Record<string, { locator: Locator; value: string }> = {
        last_name: { locator: this.contactLastName,  value: 'Robles' },
        name:      { locator: this.contactFirstName, value: 'Héctor' },
        email:     { locator: this.contactEmail,     value: 'hrobles@test.com' },
        phone:     { locator: this.contactPhone,     value: '5532514459' },
        message:   { locator: this.contactMsg,       value: 'Hello mate!' },
    };
    const { locator, value } = fieldMap[field];
    await this.safeType(locator, value);
    return this;
    }

    async clickButton(): Promise<Locator> {
        await this.submitButton.scrollIntoViewIfNeeded();
        await this.page.waitForTimeout(1000);
        
        await this.page.evaluate(() => {
            const badge = document.querySelector('.grecaptcha-badge') as HTMLElement;
            if (badge) badge.style.display = 'none';
        });
    
        // Back to native Playwright click
        //await this.page.screenshot({ path: 'before-click.png' });
        // First click focuses and triggers form validation JS
        await this.submitButton.click();
        await this.page.waitForTimeout(500);
        //await this.page.screenshot({ path: 'after-click.png' });
        // Second forced click submits - first click gets intercepted by page overlays
        await this.submitButton.click({force: true});
        console.log('Button clicked, waiting for response...');
    
        const result = await Promise.race([
            this.successMsg.waitFor({ state: 'visible', timeout: 20000 })
                .then(() => 'success' as const),
            this.errorMsg.waitFor({ state: 'visible', timeout: 20000 })
                .then(() => 'error' as const),
        ]);
    
        console.log(`Form submission result: ${result}`);
    
        if (result === 'error') {
            throw new Error('CandyMapper server error - retry the test');
        }
    
        return this.successMsg;
    }
}