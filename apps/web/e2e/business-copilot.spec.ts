import {expect,test} from '@playwright/test';

test('Soundbox exposes business tools and answers weekly sales without a demo-response badge',async({page},testInfo)=>{
 await page.goto('/soundbox');
 await page.getByLabel('Spoken responses').uncheck();
 await page.getByLabel('Assistant language').selectOption('en-IN');
 await expect(page.getByRole('heading',{name:'Your shop, in one conversation'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'What sold well this week'})).toBeVisible();
 await expect(page.getByText('Move these goods before their expiry',{exact:true})).toBeVisible();
 await page.getByLabel('Merchant command').fill('What sold best last week?');
 await page.getByRole('button',{name:'Send command',exact:true}).click();
 await expect(page.getByText(/Top recorded item sales over 7 days/)).toBeVisible();
 await expect(page.getByText('DEMO RESPONSE',{exact:true})).toHaveCount(0);
 await page.getByRole('tab',{name:'Record a sale',exact:true}).click();
 await expect(page.getByLabel('Sale product',{exact:true})).toBeVisible();
 await page.getByLabel('Sale product',{exact:true}).selectOption('PRD-001');
 await page.getByRole('button',{name:'Add',exact:true}).click();
 await expect(page.getByRole('button',{name:'Confirm & record sale'})).toBeVisible();
 // The cart is reviewed and retained; this UI check deliberately does not record a purchase.
 await page.getByRole('tab',{name:'Inventory & expiry',exact:true}).click();
 await expect(page.getByText('Receive a stock batch',{exact:true})).toBeVisible();
 await expect(page.getByText('Suggested supplier reorders',{exact:true})).toBeVisible();
 await page.getByRole('tab',{name:'Udhar khata',exact:true}).click();
 await expect(page.getByText('Total outstanding customer credit',{exact:true})).toBeVisible();
 await page.getByRole('tab',{name:'Reports & expenses',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Next 7 days · revenue forecast'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Offer notifications by SMS'})).toBeVisible();
 await page.getByRole('tab',{name:'Business overview',exact:true}).click();
 await page.setViewportSize({width:390,height:844});
 await expect(page.locator('#business-copilot')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBeTruthy();
 await page.locator('#business-copilot').screenshot({path:testInfo.outputPath('business-copilot-mobile.png')});
});
