import { test, Browser, Page, expect } from '@playwright/test';
import { CandyMapperPage } from './Pages/CandyMapperPage';

test.describe('CandyMapper', () => {

    test('should close popup', async ({ page }) => {
        const candyMapper = new CandyMapperPage(page);
        await candyMapper.navigateCandyMapper();
        await candyMapper.closePopup();
        expect(await candyMapper.isPopupVisible()).toBe(false);
    });

    test('should fill and submit contact form', async ({ page }) => {
        const candyMapper = new CandyMapperPage(page);
        await candyMapper.navigateCandyMapper();
        await candyMapper.closePopup();
        await candyMapper.completeField('name');
        await candyMapper.completeField('last_name');
        await candyMapper.completeField('email');
        await candyMapper.completeField('phone');
        await candyMapper.completeField('message');
        await page.waitForTimeout(1000);
        const success = await candyMapper.clickButton();
        await expect(success).toBeVisible();
        await expect(success).toContainText('Thank you');
    });
});